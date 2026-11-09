from healcode.runners.base import BaseTestRunner, TestCaseResult, TestRunResult, TestStatus
from healcode.runners.pytest_runner import PytestRunner
from healcode.runners.unittest_runner import UnittestRunner

def get_runner(name: str, work_dir) -> BaseTestRunner:
    name_lower = name.lower()
    if "pytest" in name_lower:
        return PytestRunner(work_dir)
    elif "unittest" in name_lower:
        return UnittestRunner(work_dir)
    else:
        # Default to pytest
        return PytestRunner(work_dir)

__all__ = [
    "BaseTestRunner",
    "TestCaseResult",
    "TestRunResult",
    "TestStatus",
    "PytestRunner",
    "UnittestRunner",
    "get_runner",
]
