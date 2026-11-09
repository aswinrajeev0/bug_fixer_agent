import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from healcode.config import HealConfig
from healcode.core.loop import HealingLoop
from healcode.runners import get_runner
from healcode.analyzer.traceback_parser import TracebackParser
from healcode.ui.console import console
from healcode.ui.views import render_banner, render_test_failure

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    ".idea",
    ".vscode",
}

class DirectoryWatcher:
    """Monitors repository for Python file modifications and triggers test & heal cycles."""

    def __init__(self, target_dir: Path, poll_interval: float = 1.0):
        self.target_dir = Path(target_dir).resolve()
        self.poll_interval = poll_interval
        self._snapshot: Dict[Path, float] = {}

    def _should_ignore(self, path: Path) -> bool:
        parts = path.parts
        return any(ignored in parts for ignored in IGNORED_DIRS)

    def _get_mtimes(self) -> Dict[Path, float]:
        mtimes: Dict[Path, float] = {}
        for p in self.target_dir.rglob("*.py"):
            if not self._should_ignore(p) and p.is_file():
                try:
                    mtimes[p] = p.stat().st_mtime
                except (OSError, FileNotFoundError):
                    pass
        return mtimes

    def scan_for_changes(self) -> List[Path]:
        current = self._get_mtimes()
        changed: List[Path] = []

        if not self._snapshot:
            self._snapshot = current
            return []

        for p, mtime in current.items():
            if p not in self._snapshot or self._snapshot[p] != mtime:
                changed.append(p)

        self._snapshot = current
        return changed

    def watch(
        self,
        config: HealConfig,
        auto_heal: bool = True,
        test_target: Optional[str] = None,
    ) -> None:
        render_banner()
        console.print(
            f"[bold cyan]👀 HealCode Watcher active on: [white]{self.target_dir}[/white][/bold cyan]"
        )
        console.print(
            f"[dim]Monitoring .py file saves (Auto-heal: {'ON' if auto_heal else 'OFF'}). Press Ctrl+C to stop.[/dim]\n"
        )

        # Initial baseline snapshot
        self._snapshot = self._get_mtimes()
        runner = get_runner(config.test_command, self.target_dir)

        try:
            while True:
                time.sleep(self.poll_interval)
                changed_files = self.scan_for_changes()

                if changed_files:
                    file_names = ", ".join(f.name for f in changed_files[:3])
                    if len(changed_files) > 3:
                        file_names += f" and {len(changed_files) - 3} more"

                    console.print(
                        f"\n[bold yellow]► Change detected in:[/bold yellow] [bold white]{file_names}[/bold white]"
                    )
                    console.print("[dim]Executing test suite...[/dim]")

                    result = runner.run_tests(test_target)
                    if result.success:
                        console.print(
                            f"[bold green]✔ All tests passing![/bold green] ({result.summary_line})"
                        )
                    else:
                        console.print(
                            f"[bold red]✘ Test failure detected:[/bold red] {result.summary_line}"
                        )
                        if auto_heal:
                            console.print("[bold magenta]⚡ Launching autonomous healing cycle...[/bold magenta]")
                            loop = HealingLoop(config)
                            loop.run(test_target)
                        else:
                            parser = TracebackParser(self.target_dir)
                            for failure in result.failures:
                                diag = parser.parse(
                                    failure.name, failure.traceback or failure.message or ""
                                )
                                render_test_failure(diag)

                    console.print("\n[dim]👀 Resuming watch...[/dim]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Watcher stopped by user.[/yellow]")
