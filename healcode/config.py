from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()

class HealConfig(BaseModel):
    """Configuration settings for the HealCode Self-Healing Agent."""
    gemini_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    model: str = Field(
        default_factory=lambda: os.getenv("HEALCODE_MODEL", "gemini-3.6-flash")
    )
    max_retries: int = Field(default=3, description="Maximum healing attempts before giving up")
    test_command: str = Field(default="pytest", description="Test suite command to execute")
    target_dir: Path = Field(default_factory=Path.cwd, description="Target repository or directory")
    git_checkpoint: bool = Field(default=True, description="Enable git safety checkpoint & rollbacks")
    auto_commit: bool = Field(default=False, description="Automatically commit verified fixes")
    interactive: bool = Field(default=True, description="Prompt user for confirmation before applying")
    generate_tests: bool = Field(default=False, description="Synthesize and save dedicated regression test cases")
    report_format: Optional[str] = Field(default=None, description="Generate diagnostic report ('md', 'html', or 'both')")
    report_output: Optional[Path] = Field(default=None, description="Custom path for diagnostic report")
    verbose: bool = Field(default=False, description="Enable verbose diagnostic logs")

    def validate_api_key(self) -> None:
        if not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set it in your environment or in a .env file."
            )
