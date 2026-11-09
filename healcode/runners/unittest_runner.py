import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional
from healcode.runners.base import BaseTestRunner, TestCaseResult, TestRunResult, TestStatus

class UnittestRunner(BaseTestRunner):
    """Executes python -m unittest suites and extracts failures."""

    def __init__(self, work_dir: Path, custom_args: Optional[List[str]] = None):
        super().__init__(work_dir)
        self.custom_args = custom_args or []

    def run_tests(self, target: Optional[str] = None) -> TestRunResult:
        cmd = [sys.executable, "-m", "unittest", "-v"]
        if self.custom_args:
            cmd.extend(self.custom_args)
        if target:
            cmd.append(target)
        elif not self.custom_args:
            cmd.extend(["discover", "-s", "."])

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
        combined = stdout + "\n" + stderr
        exit_code = proc.returncode

        passed, failed, error = self._parse_counts(combined)
        failures = self._parse_failures(combined)

        return TestRunResult(
            success=(exit_code == 0),
            exit_code=exit_code,
            duration_seconds=round(duration, 3),
            passed_count=passed,
            failed_count=failed,
            error_count=error,
            skipped_count=0,
            failures=failures,
            raw_stdout=stdout,
            raw_stderr=stderr,
            command=" ".join(cmd),
        )

    def _parse_counts(self, output: str) -> tuple[int, int, int]:
        # Unittest output line: Ran X tests in Ys
        total = 0
        failed = 0
        error = 0

        m_ran = re.search(r"Ran\s+(\d+)\s+tests?", output)
        if m_ran:
            total = int(m_ran.group(1))

        m_failures = re.search(r"failures=(\d+)", output)
        if m_failures:
            failed = int(m_failures.group(1))

        m_errors = re.search(r"errors=(\d+)", output)
        if m_errors:
            error = int(m_errors.group(1))

        passed = max(0, total - (failed + error))
        return passed, failed, error

    def _parse_failures(self, output: str) -> List[TestCaseResult]:
        failures: List[TestCaseResult] = []
        # Pattern: ======================================================================
        # FAIL: test_add (test_math.TestMath)
        blocks = re.split(r"={50,}\n", output)
        for block in blocks:
            header_match = re.search(r"^(FAIL|ERROR):\s+([^\n]+)", block.strip())
            if header_match:
                kind = header_match.group(1)
                name = header_match.group(2)
                status = TestStatus.FAILED if kind == "FAIL" else TestStatus.ERROR

                # Look for file path and line number
                file_path = None
                line_no = None
                m_loc = re.findall(r'File "([^"]+)", line (\d+)', block)
                if m_loc:
                    file_path, line_str = m_loc[-1]
                    line_no = int(line_str)

                # Last non-empty line as message
                lines = [line.strip() for line in block.splitlines() if line.strip()]
                msg = lines[-1] if lines else ""

                failures.append(
                    TestCaseResult(
                        name=name,
                        status=status,
                        file_path=file_path,
                        line_number=line_no,
                        message=msg,
                        traceback=block.strip(),
                    )
                )

        return failures
