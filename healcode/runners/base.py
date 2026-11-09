from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

class TestStatus(str, Enum):
    __test__ = False
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"

class TestCaseResult(BaseModel):
    __test__ = False
    name: str
    status: TestStatus
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    message: Optional[str] = None
    traceback: Optional[str] = None

class TestRunResult(BaseModel):
    __test__ = False
    success: bool
    exit_code: int
    duration_seconds: float = 0.0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    failures: List[TestCaseResult] = Field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""
    command: str = ""

    @property
    def total_tests(self) -> int:
        return self.passed_count + self.failed_count + self.error_count + self.skipped_count

    @property
    def summary_line(self) -> str:
        parts = []
        if self.passed_count:
            parts.append(f"{self.passed_count} passed")
        if self.failed_count:
            parts.append(f"{self.failed_count} failed")
        if self.error_count:
            parts.append(f"{self.error_count} errors")
        if self.skipped_count:
            parts.append(f"{self.skipped_count} skipped")
        return ", ".join(parts) if parts else "No tests collected"

class BaseTestRunner(ABC):
    """Abstract base class for test suite runners."""
    def __init__(self, work_dir: Path):
        self.work_dir = Path(work_dir)

    @abstractmethod
    def run_tests(self, target: Optional[str] = None) -> TestRunResult:
        """Run the test suite and return structured results."""
        pass
