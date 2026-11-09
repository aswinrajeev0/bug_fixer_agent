import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional
from healcode.runners.base import BaseTestRunner, TestCaseResult, TestRunResult, TestStatus

class PytestRunner(BaseTestRunner):
    """Executes pytest suites and extracts granular failure reports."""

    def __init__(self, work_dir: Path, custom_args: Optional[List[str]] = None):
        super().__init__(work_dir)
        self.custom_args = custom_args or []

    def run_tests(self, target: Optional[str] = None) -> TestRunResult:
        cmd = [sys.executable, "-m", "pytest", "-v", "--color=no"]
        if self.custom_args:
            cmd.extend(self.custom_args)
        if target:
            cmd.append(target)

        start_time = time.perf_counter()
        proc = subprocess.run(
            cmd,
            cwd=str(self.work_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        duration = time.perf_counter() - start_time

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode

        # Parse counts and test results
        passed, failed, error, skipped = self._parse_summary_counts(stdout)
        failures = self._parse_failures(stdout)

        # Check if pytest found no tests (pytest exit code 5 is NO_TESTS_COLLECTED)
        if exit_code == 5 or ("collected 0 items" in stdout and exit_code != 0):
            error = 1
            hint = "Pytest discovered 0 tests. By default, pytest only scans files matching 'test_*.py' or '*_test.py'."
            try:
                non_standard = [p.name for p in self.work_dir.glob("test*.py") if not p.name.startswith("test_")]
                if non_standard:
                    hint += f" Did you mean to target '{non_standard[0]}'? Run: healcode scan {non_standard[0]}"
            except Exception:
                pass
            failures.append(
                TestCaseResult(
                    name="NoTestsFoundError",
                    status=TestStatus.ERROR,
                    message=hint,
                    traceback=f"NoTestsFoundError: {hint}\n",
                )
            )
        # In case counts were not matched by regex (e.g. fatal syntax error during collection)
        elif exit_code != 0 and failed == 0 and error == 0:
            error = 1
            if not failures:
                failures.append(
                    TestCaseResult(
                        name="TestCollectionOrExecutionError",
                        status=TestStatus.ERROR,
                        message="Pytest exited with non-zero status during collection or execution",
                        traceback=stdout + "\n" + stderr
                    )
                )

        return TestRunResult(
            success=(exit_code == 0),
            exit_code=exit_code,
            duration_seconds=round(duration, 3),
            passed_count=passed,
            failed_count=failed,
            error_count=error,
            skipped_count=skipped,
            failures=failures,
            raw_stdout=stdout,
            raw_stderr=stderr,
            command=" ".join(cmd),
        )

    def _parse_summary_counts(self, output: str) -> tuple[int, int, int, int]:
        """Extracts passed, failed, error, skipped from pytest terminal summary."""
        passed = failed = error = skipped = 0
        tail = "\n".join(output.strip().splitlines()[-15:])

        m_passed = re.search(r"(\d+)\s+passed", tail)
        if m_passed:
            passed = int(m_passed.group(1))

        m_failed = re.search(r"(\d+)\s+failed", tail)
        if m_failed:
            failed = int(m_failed.group(1))

        m_error = re.search(r"(\d+)\s+error", tail)
        if m_error:
            error = int(m_error.group(1))

        m_skipped = re.search(r"(\d+)\s+skipped", tail)
        if m_skipped:
            skipped = int(m_skipped.group(1))

        return passed, failed, error, skipped

    def _parse_failures(self, output: str) -> List[TestCaseResult]:
        """Parses individual test failures with messages and tracebacks."""
        failures: List[TestCaseResult] = []

        # Match:
        # ____________________ test_name ____________________
        # block content
        # (until next header ___ or === or end of string)
        pattern = re.compile(r'_{3,}\s*([^\n]+?)\s*_{3,}\n(.*?)(?=\n_{3,}|\n={3,}|\Z)', re.DOTALL)
        matches = pattern.findall(output)

        for test_name, block in matches:
            test_name = test_name.strip()
            block = block.strip()

            file_path = None
            line_no = None
            m_loc = re.findall(r'([^\s:]+\.py):(\d+):', block)
            if m_loc:
                file_path, line_str = m_loc[-1]
                try:
                    line_no = int(line_str)
                except ValueError:
                    pass

            # Extract error message
            err_lines = [
                line[2:].strip() for line in block.splitlines() if line.startswith("E ")
            ]
            message = "\n".join(err_lines) if err_lines else ""

            failures.append(
                TestCaseResult(
                    name=test_name,
                    status=TestStatus.FAILED,
                    file_path=file_path,
                    line_number=line_no,
                    message=message,
                    traceback=block,
                )
            )

        # Fallback to short test summary info if no failure sections were found
        if not failures:
            summary_matches = re.findall(
                r"FAILED\s+([^\s:]+\.py)::([^\s\-]+)(?:\s+-\s+(.+))?", output
            )
            for file_path, test_name, msg in summary_matches:
                failures.append(
                    TestCaseResult(
                        name=f"{file_path}::{test_name}",
                        status=TestStatus.FAILED,
                        file_path=file_path,
                        message=msg or "Test failed",
                        traceback=output,
                    )
                )

        return failures
