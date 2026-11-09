from typing import List, Optional
from pydantic import BaseModel, Field

class FilePatch(BaseModel):
    file_path: str = Field(description="Relative path of the file to modify or create")
    description: str = Field(description="Summary of changes in this file")
    new_content: str = Field(description="The complete, updated file content with the fix applied")
    is_new_file: bool = Field(default=False, description="True if this is a newly created file (e.g. new test)")

class HealingProposal(BaseModel):
    root_cause_analysis: str = Field(
        description="Detailed explanation of why the failure or bug occurred"
    )
    fix_hypothesis: str = Field(
        description="The reasoned strategy to fix the bug without introducing regressions"
    )
    patches: List[FilePatch] = Field(
        description="List of file modifications to resolve the failure"
    )
    regression_test_code: Optional[str] = Field(
        default=None,
        description="Optional new pytest test case to verify this bug remains fixed in the future",
    )
    confidence_score: float = Field(
        default=0.9,
        description="Confidence between 0.0 and 1.0 that this completely fixes the bug",
    )
    risk_assessment: str = Field(
        default="Low",
        description="Risk of unintended side effects or breaking changes",
    )
