from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
from healcode.ui.console import console
from healcode.analyzer.traceback_parser import FailureDiagnosis
from healcode.agent.models import HealingProposal
from healcode.core.state import HealingSessionState

def render_banner() -> None:
    text = """
    ╔╗ ╦ ╦╔═╗  ╔═╗╦═╗╔═╗╔═╗╦═╗
    ╠╩╗║ ║║ ╦  ╠╣ ╠╦╝║ ║║╣ ╠╦╝
    ╚═╝╚═╝╚═╝  ╚  ╩╚═╚═╝╚═╝╩╚═
    ⚡ Self-Healing Bug Fixer & Test Agent ⚡
    """
    console.print(Panel(Align.center(text), style="bold cyan", border_style="bright_blue"))

def render_test_failure(diagnosis: FailureDiagnosis) -> None:
    content = Text()
    content.append("Failed Test: ", style="bold red")
    content.append(f"{diagnosis.test_name}\n", style="bold white")
    content.append("Error: ", style="bold yellow")
    content.append(f"{diagnosis.error_type}: {diagnosis.error_message}\n\n", style="white")

    if diagnosis.culprit_frame:
        content.append("Suspected Culprit Location:\n", style="bold cyan")
        content.append(f"  File: {diagnosis.culprit_frame.file_path}:{diagnosis.culprit_frame.line_number}\n", style="cyan")
        if diagnosis.culprit_frame.function_name:
            content.append(f"  Function: {diagnosis.culprit_frame.function_name}()\n", style="bright_black")
        if diagnosis.culprit_frame.code_line:
            content.append(f"  Line: {diagnosis.culprit_frame.code_line}\n", style="italic")

    console.print(Panel(content, title="[bold red]Test Failure Detected[/bold red]", border_style="red"))

def render_iteration_header(attempt: int, max_attempts: int) -> None:
    console.print(f"\n[bold magenta]─── Healing Iteration {attempt}/{max_attempts} ───[/bold magenta]\n")

def render_healing_proposal(proposal: HealingProposal) -> None:
    content = Text()
    content.append("Root Cause Analysis:\n", style="bold yellow")
    content.append(f"{proposal.root_cause_analysis}\n\n", style="white")

    content.append("Fix Hypothesis:\n", style="bold green")
    content.append(f"{proposal.fix_hypothesis}\n\n", style="white")

    content.append(f"Confidence: ", style="bold cyan")
    conf_pct = int(proposal.confidence_score * 100)
    color = "green" if conf_pct >= 80 else ("yellow" if conf_pct >= 50 else "red")
    content.append(f"{conf_pct}%", style=f"bold {color}")
    content.append(f"  |  Risk: ", style="bold cyan")
    content.append(f"{proposal.risk_assessment}\n", style="bold white")

    console.print(Panel(content, title="[bold cyan]Gemini Diagnosis & Proposed Fix[/bold cyan]", border_style="cyan"))

def render_diff(diff_text: str, title: str = "Proposed Changes (Diff)") -> None:
    if not diff_text.strip():
        console.print("[dim]No textual diff detected.[/dim]")
        return
    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=f"[bold green]{title}[/bold green]", border_style="green"))

def render_summary_report(state: HealingSessionState) -> None:
    table = Table(title="Healing Session Summary", border_style="bright_blue")
    table.add_column("Property", style="bold cyan")
    table.add_column("Value", style="white")

    status_style = "bold green" if state.is_healed else "bold red"
    status_text = "HEALED" if state.is_healed else "UNRESOLVED"

    table.add_row("Final Status", f"[{status_style}]{status_text}[/{status_style}]")
    table.add_row("Total Iterations", str(state.current_iteration))
    table.add_row("Initial Failures", str(len(state.initial_failures)))
    table.add_row("Files Modified", ", ".join(state.modified_files) if state.modified_files else "None")
    table.add_row("Duration", f"{state.total_duration_seconds:.2f}s")

    console.print("\n")
    console.print(table)
