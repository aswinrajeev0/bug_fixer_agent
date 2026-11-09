import time
from pathlib import Path
from typing import Optional
from rich.prompt import Confirm

from healcode.config import HealConfig
from healcode.core.state import HealingSessionState, IterationRecord
from healcode.runners import get_runner, BaseTestRunner
from healcode.analyzer.traceback_parser import TracebackParser, FailureDiagnosis
from healcode.analyzer.code_context import CodeContextExtractor
from healcode.agent.gemini_client import GeminiAgent
from healcode.agent.prompts import build_initial_heal_prompt, build_retry_heal_prompt
from healcode.sandbox.patcher import CodePatcher
from healcode.sandbox.git_manager import GitManager
from healcode.ui.console import console
from healcode.ui.views import (
    render_banner,
    render_test_failure,
    render_iteration_header,
    render_healing_proposal,
    render_diff,
    render_summary_report,
)

class HealingLoop:
    """Orchestrates the self-healing test-and-repair cycle."""

    def __init__(
        self,
        config: HealConfig,
        runner: Optional[BaseTestRunner] = None,
        agent: Optional[GeminiAgent] = None,
    ):
        self.config = config
        self.root_dir = Path(config.target_dir).resolve()
        self.runner = runner or get_runner(config.test_command, self.root_dir)
        self.agent = agent or GeminiAgent(api_key=config.gemini_api_key, model=config.model)
        self.parser = TracebackParser(self.root_dir)
        self.context_extractor = CodeContextExtractor(self.root_dir)
        self.patcher = CodePatcher(self.root_dir)
        self.git = GitManager(self.root_dir)

    def run(self, test_target: Optional[str] = None) -> HealingSessionState:
        render_banner()
        state = HealingSessionState(max_iterations=self.config.max_retries)

        # Step 1: Initial Test Run
        console.print("[bold cyan]► Executing initial test run...[/bold cyan]")
        with console.status("[cyan]Running test suite...[/cyan]"):
            initial_result = self.runner.run_tests(test_target)
        state.initial_test_result = initial_result
        state.initial_failures = initial_result.failures

        if initial_result.success:
            console.print(f"[bold green]✔ All tests passed![/bold green] ({initial_result.summary_line})")
            state.mark_completed(healed=True)
            render_summary_report(state)
            return state

        console.print(
            f"[bold red]✘ Test run failed:[/bold red] {initial_result.summary_line}"
        )

        # Step 2: Establish Safety Checkpoint
        if self.config.git_checkpoint and self.git.is_git_repo():
            console.print("[dim]Creating Git safety checkpoint...[/dim]")
            self.git.create_checkpoint("healcode-checkpoint")

        # Step 3: Healing Iteration Loop
        previous_hypothesis = ""
        previous_diff = ""
        last_diagnosis = None

        for iteration in range(1, self.config.max_retries + 1):
            state.current_iteration = iteration
            render_iteration_header(iteration, self.config.max_retries)

            # Get current primary failure
            active_failures = state.initial_failures
            if not active_failures:
                # Re-run to see current state
                res = self.runner.run_tests(test_target)
                if res.success:
                    state.mark_completed(healed=True)
                    break
                active_failures = res.failures

            primary_failure = active_failures[0]
            diagnosis = self.parser.parse(
                primary_failure.name,
                primary_failure.traceback or primary_failure.message or "",
            )
            last_diagnosis = diagnosis
            render_test_failure(diagnosis)

            # Build code context
            ctx = self.context_extractor.build_context(diagnosis)

            # Formulate prompt for Gemini
            if iteration == 1:
                culprit_path = (
                    ctx.culprit_file_context.relative_path
                    if ctx.culprit_file_context
                    else (diagnosis.culprit_frame.file_path if diagnosis.culprit_frame else "unknown")
                )
                culprit_content = (
                    ctx.culprit_file_context.full_content
                    if ctx.culprit_file_context
                    else ""
                )
                test_path = ctx.test_file_context.relative_path if ctx.test_file_context else ""
                test_content = ctx.test_file_context.full_content if ctx.test_file_context else ""

                prompt = build_initial_heal_prompt(
                    test_name=diagnosis.test_name,
                    error_type=diagnosis.error_type,
                    error_message=diagnosis.error_message,
                    traceback_snippet=diagnosis.raw_traceback,
                    culprit_file_path=culprit_path,
                    culprit_file_content=culprit_content,
                    test_file_path=test_path,
                    test_file_content=test_content,
                )
            else:
                # Read latest content of culprit file
                current_code = ""
                if ctx.culprit_file_context:
                    current_code = ctx.culprit_file_context.full_content

                prompt = build_retry_heal_prompt(
                    attempt_num=iteration,
                    previous_hypothesis=previous_hypothesis,
                    previous_diff=previous_diff,
                    new_error_type=diagnosis.error_type,
                    new_error_message=diagnosis.error_message,
                    new_traceback=diagnosis.raw_traceback,
                    current_files_content=current_code,
                )

            # Step 4: Ask Gemini for fix
            console.print("[bold cyan]► Synthesizing fix with Gemini...[/bold cyan]")
            with console.status("[bold cyan]Gemini analyzing bug and generating patch...[/bold cyan]"):
                try:
                    proposal = self.agent.generate_healing_proposal(prompt)
                except Exception as e:
                    console.print(f"[bold red]Gemini API error:[/bold red] {e}")
                    break

            render_healing_proposal(proposal)
            previous_hypothesis = proposal.fix_hypothesis

            # Step 5: Apply Patch & Validate Syntax
            console.print("[dim]Validating and applying proposed patches...[/dim]")
            patch_result = self.patcher.apply_patches(proposal.patches)

            if not patch_result.success:
                console.print(f"[bold red]Patch rejected:[/bold red] {patch_result.syntax_error}")
                # Save iteration record with error
                state.iterations.append(
                    IterationRecord(
                        iteration_number=iteration,
                        diagnosis=diagnosis,
                        proposal=proposal,
                        error_message=patch_result.syntax_error,
                        success=False,
                    )
                )
                continue

            previous_diff = patch_result.combined_diff
            state.last_diff = patch_result.combined_diff
            state.modified_files = patch_result.applied_files
            state.backups.update(patch_result.backups)

            render_diff(patch_result.combined_diff)

            # Step 6: Verify Fix with Test Suite
            console.print("[bold cyan]► Re-running test suite to verify fix...[/bold cyan]")
            with console.status("[cyan]Verifying fix with tests...[/cyan]"):
                verification = self.runner.run_tests(test_target)

            record = IterationRecord(
                iteration_number=iteration,
                diagnosis=diagnosis,
                proposal=proposal,
                diff=patch_result.combined_diff,
                test_result=verification,
                success=verification.success,
            )
            state.iterations.append(record)

            if verification.success:
                console.print(f"\n[bold green]✔ FIX VERIFIED! All tests passing![/bold green] ({verification.summary_line})")
                state.mark_completed(healed=True)
                break
            else:
                console.print(f"[yellow]⚠ Attempt {iteration} did not resolve all failures:[/yellow] {verification.summary_line}")
                state.initial_failures = verification.failures

        # Final outcome handling
        if state.is_healed:
            self._handle_successful_healing(state, last_diagnosis)
        else:
            self._handle_failed_healing(state)

        render_summary_report(state)
        return state

    def _handle_successful_healing(
        self, state: HealingSessionState, diagnosis: Optional[FailureDiagnosis]
    ) -> None:
        console.print("\n[bold green]══════════════ BUG HEALED SUCCESSFULLY ══════════════[/bold green]")
        
        # Git Auto-commit or Interactive Prompt
        if self.config.interactive:
            keep = Confirm.ask("Keep and commit these changes?", default=True)
            if keep and self.git.is_git_repo():
                test_name = diagnosis.test_name if diagnosis else "suite"
                msg = f"fix(autoheal): healed test failure in {test_name}\n\nAutomated fix by HealCode & Gemini"
                if self.git.commit_fix(msg, state.modified_files):
                    console.print(f"[bold green]✔ Committed changes to git:[/bold green] '{msg.splitlines()[0]}'")
                else:
                    console.print("[yellow]Changes kept in working directory (uncommitted).[/yellow]")
            elif not keep:
                console.print("[yellow]Rolling back changes upon user request...[/yellow]")
                self._rollback(state)
        elif self.config.auto_commit and self.git.is_git_repo():
            test_name = diagnosis.test_name if diagnosis else "suite"
            msg = f"fix(autoheal): healed test failure in {test_name}\n\nAutomated fix by HealCode & Gemini"
            self.git.commit_fix(msg, state.modified_files)
            console.print(f"[bold green]✔ Auto-committed fix to git:[/bold green] '{msg.splitlines()[0]}'")

    def _handle_failed_healing(self, state: HealingSessionState) -> None:
        console.print("\n[bold red]══════════════ HEALING ATTEMPTS EXHAUSTED ══════════════[/bold red]")
        console.print("[yellow]Rolling back all modifications to maintain repository integrity...[/yellow]")
        self._rollback(state)
        state.mark_completed(healed=False)

    def _rollback(self, state: HealingSessionState) -> None:
        if self.config.git_checkpoint and self.git.is_git_repo():
            self.git.rollback()
        else:
            self.patcher.rollback_patches(state.backups)
        console.print("[dim]Working directory restored cleanly.[/dim]")
