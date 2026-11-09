import os
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.panel import Panel

from healcode.config import HealConfig
from healcode.core.loop import HealingLoop
from healcode.runners import get_runner
from healcode.analyzer.traceback_parser import TracebackParser
from healcode.sandbox.git_manager import GitManager
from healcode.reporting.report_generator import ReportGenerator
from healcode.watcher import DirectoryWatcher
from healcode.ui.console import console
from healcode.ui.views import render_banner, render_test_failure

app = typer.Typer(
    name="healcode",
    help="⚡ Self-Healing Bug Fixer & Test Agent powered by Google Gemini ⚡",
    add_completion=False,
)

@app.command()
def heal(
    target: Optional[str] = typer.Argument(
        None, help="Specific test file or test target (e.g. tests/test_calc.py::test_add)"
    ),
    model: str = typer.Option(
        "gemini-3.6-flash", "--model", "-m", help="Google Gemini model identifier"
    ),
    max_retries: int = typer.Option(
        3, "--max-retries", "-r", help="Maximum healing attempts per test failure"
    ),
    test_cmd: str = typer.Option(
        "pytest", "--test-cmd", "-c", help="Test runner command (pytest, unittest)"
    ),
    dir: Path = typer.Option(
        Path.cwd(), "--dir", "-d", help="Target repository directory"
    ),
    auto_commit: bool = typer.Option(
        False, "--auto-commit", help="Automatically commit verified fixes to Git"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/--non-interactive", help="Prompt before applying or committing changes"
    ),
    git_checkpoint: bool = typer.Option(
        True, "--git-checkpoint/--no-git-checkpoint", help="Enable git safety checkpointing"
    ),
    report: Optional[str] = typer.Option(
        None, "--report", help="Save diagnostic report ('md', 'html', or 'both')"
    ),
):
    """Run test suite and autonomously heal any failing tests."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel(
                "[bold red]GEMINI_API_KEY is missing![/bold red]\n\n"
                "Please export your Gemini API key:\n"
                "  [cyan]export GEMINI_API_KEY=\"your-api-key\"[/cyan] (Linux/macOS)\n"
                "  [cyan]$env:GEMINI_API_KEY=\"your-api-key\"[/cyan] (PowerShell)\n\n"
                "Or add it to a [bold].env[/bold] file in the workspace.",
                title="Configuration Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    config = HealConfig(
        gemini_api_key=api_key,
        model=model,
        max_retries=max_retries,
        test_command=test_cmd,
        target_dir=dir,
        git_checkpoint=git_checkpoint,
        auto_commit=auto_commit,
        interactive=interactive,
        report_format=report,
    )

    loop = HealingLoop(config)
    state = loop.run(target)

    # Generate diagnostic report if requested
    if report:
        report_fmt = report.lower()
        if report_fmt in ("md", "both"):
            md_path = dir / "healcode-report.md"
            ReportGenerator.generate_markdown(state, md_path)
            console.print(f"[bold green]✔ Saved Markdown report to:[/bold green] {md_path}")
        if report_fmt in ("html", "both"):
            html_path = dir / "healcode-report.html"
            ReportGenerator.generate_html(state, html_path)
            console.print(f"[bold green]✔ Saved HTML report to:[/bold green] {html_path}")

    if not state.is_healed and state.initial_test_result and not state.initial_test_result.success:
        raise typer.Exit(code=1)

@app.command()
def scan(
    target: Optional[str] = typer.Argument(
        None, help="Specific test file or target to scan"
    ),
    test_cmd: str = typer.Option(
        "pytest", "--test-cmd", "-c", help="Test runner command (pytest, unittest)"
    ),
    dir: Path = typer.Option(
        Path.cwd(), "--dir", "-d", help="Target repository directory"
    ),
):
    """Diagnose test failures and pinpoint culprit code without modifying files."""
    render_banner()
    console.print(f"[bold cyan]Scanning tests using {test_cmd} in {dir}...[/bold cyan]\n")

    runner = get_runner(test_cmd, dir)
    parser = TracebackParser(dir)

    with console.status("[cyan]Running test suite...[/cyan]"):
        result = runner.run_tests(target)

    if result.success:
        console.print(f"[bold green]✔ All tests passing![/bold green] ({result.summary_line})")
        return

    console.print(f"[bold red]✘ Found {len(result.failures)} test failures:[/bold red]\n")
    for failure in result.failures:
        diag = parser.parse(failure.name, failure.traceback or failure.message or "")
        render_test_failure(diag)

@app.command()
def watch(
    target: Optional[str] = typer.Argument(
        None, help="Specific test file or target to run on change"
    ),
    test_cmd: str = typer.Option(
        "pytest", "--test-cmd", "-c", help="Test runner command (pytest, unittest)"
    ),
    dir: Path = typer.Option(
        Path.cwd(), "--dir", "-d", help="Target repository directory"
    ),
    auto_heal: bool = typer.Option(
        True, "--auto-heal/--no-auto-heal", help="Automatically trigger healing loop on failure"
    ),
    model: str = typer.Option(
        "gemini-3.6-flash", "--model", "-m", help="Google Gemini model identifier"
    ),
):
    """Watch directory for Python file changes and automatically test & heal in the background."""
    api_key = os.getenv("GEMINI_API_KEY")
    config = HealConfig(
        gemini_api_key=api_key,
        model=model,
        test_command=test_cmd,
        target_dir=dir,
    )
    watcher = DirectoryWatcher(dir)
    watcher.watch(config=config, auto_heal=auto_heal, test_target=target)

@app.command()
def info():
    """Display environment configuration and agent diagnostic status."""
    render_banner()
    api_key = os.getenv("GEMINI_API_KEY")
    masked_key = (api_key[:6] + "..." + api_key[-4:]) if api_key else "[bold red]Not Configured[/bold red]"

    git = GitManager(Path.cwd())
    is_git = git.is_git_repo()
    branch = git.get_current_branch() if is_git else "N/A"

    console.print(Panel(
        f"[bold cyan]Gemini API Key:[/bold cyan] {masked_key}\n"
        f"[bold cyan]Default Model:[/bold cyan] gemini-3.6-flash (with automatic resilient failover)\n"
        f"[bold cyan]Git Repository:[/bold cyan] {'Yes' if is_git else 'No'} (Branch: {branch})\n"
        f"[bold cyan]Python Version:[/bold cyan] {sys.version.split()[0]}\n"
        f"[bold cyan]Working Directory:[/bold cyan] {Path.cwd()}",
        title="HealCode System Info",
        border_style="cyan"
    ))

@app.command()
def install_hook(
    mode: str = typer.Option("scan", "--mode", "-m", help="Hook behavior: 'scan' (block push) or 'heal' (auto-fix)"),
    dir: Path = typer.Option(Path.cwd(), "--dir", "-d", help="Target git repository"),
):
    """Install a Git pre-push hook to prevent pushing broken tests."""
    git_dir = dir / ".git"
    if not git_dir.exists():
        console.print("[bold red]Not a git repository. Run 'git init' first.[/bold red]")
        raise typer.Exit(code=1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "pre-push"

    if mode == "heal":
        script_body = (
            "#!/bin/sh\n"
            "echo \"⚡ [HealCode] Verifying tests before git push...\"\n"
            "healcode heal --non-interactive --auto-commit\n"
            "if [ $? -ne 0 ]; then\n"
            "    echo \"❌ [HealCode] Tests failed and could not be auto-resolved. Push cancelled.\"\n"
            "    exit 1\n"
            "fi\n"
        )
    else:
        script_body = (
            "#!/bin/sh\n"
            "echo \"🔍 [HealCode] Scanning tests before git push...\"\n"
            "healcode scan\n"
            "if [ $? -ne 0 ]; then\n"
            "    echo \"❌ [HealCode] Failing tests detected! Push blocked.\"\n"
            "    echo \"💡 Run 'healcode heal' to automatically fix the bugs.\"\n"
            "    exit 1\n"
            "fi\n"
        )

    hook_file.write_text(script_body, encoding="utf-8")
    try:
        # Make executable on Unix/Linux/macOS
        hook_file.chmod(0o755)
    except Exception:
        pass

    console.print(
        f"[bold green]✔ Successfully installed Git pre-push hook in:[/bold green] {hook_file} (Mode: {mode})"
    )

def main():
    app()

if __name__ == "__main__":
    main()
