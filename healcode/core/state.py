import time
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from healcode.runners.base import TestCaseResult, TestRunResult
from healcode.analyzer.traceback_parser import FailureDiagnosis
from healcode.agent.models import HealingProposal

class IterationRecord(BaseModel):
    iteration_number: int
    diagnosis: Optional[FailureDiagnosis] = None
    proposal: Optional[HealingProposal] = None
    diff: str = ""
    test_result: Optional[TestRunResult] = None
    success: bool = False
    error_message: Optional[str] = None

class HealingSessionState(BaseModel):
    start_time: float = Field(default_factory=time.time)
    total_duration_seconds: float = 0.0
    initial_test_result: Optional[TestRunResult] = None
    initial_failures: List[TestCaseResult] = Field(default_factory=list)
    iterations: List[IterationRecord] = Field(default_factory=list)
    current_iteration: int = 0
    max_iterations: int = 3
    is_healed: bool = False
    modified_files: List[str] = Field(default_factory=list)
    last_diff: str = ""
    backups: Dict[str, str] = Field(default_factory=dict)

    def mark_completed(self, healed: bool) -> None:
        self.is_healed = healed
        self.total_duration_seconds = time.time() - self.start_time
