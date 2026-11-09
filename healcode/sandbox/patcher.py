import ast
import difflib
import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from healcode.agent.models import FilePatch

class PatchResult(BaseModel):
    success: bool
    applied_files: List[str] = Field(default_factory=list)
    diffs: Dict[str, str] = Field(default_factory=dict)
    combined_diff: str = ""
    syntax_error: Optional[str] = None
    backups: Dict[str, str] = Field(default_factory=dict)

class CodePatcher:
    """Safely applies patches, computes unified diffs, and validates syntax."""

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir).resolve()

    def generate_diff(self, original_text: str, new_text: str, file_path: str) -> str:
        orig_lines = original_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff)

    def validate_syntax(self, code: str, file_path: str) -> Optional[str]:
        """Validates Python syntax using AST. Returns error string if invalid."""
        if file_path.endswith(".py"):
            try:
                ast.parse(code, filename=file_path)
            except SyntaxError as e:
                return f"SyntaxError in {file_path} at line {e.lineno}, col {e.offset}: {e.msg}"
        return None

    def apply_patches(self, patches: List[FilePatch]) -> PatchResult:
        applied = []
        diffs = {}
        backups = {}

        # Step 1: Pre-validation of syntax across all files
        for patch in patches:
            syntax_err = self.validate_syntax(patch.new_content, patch.file_path)
            if syntax_err:
                return PatchResult(
                    success=False,
                    syntax_error=syntax_err,
                )

        # Step 2: Write files and compute diffs
        for patch in patches:
            target_path = (self.root_dir / patch.file_path).resolve()
            original_content = ""
            if target_path.exists():
                try:
                    original_content = target_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    original_content = ""

            # Store backup in memory for non-git fallback rollback
            backups[patch.file_path] = original_content

            diff = self.generate_diff(original_content, patch.new_content, patch.file_path)
            diffs[patch.file_path] = diff

            # Ensure parent directories exist
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(patch.new_content, encoding="utf-8")
            applied.append(patch.file_path)

        combined = "\n".join(d for d in diffs.values() if d.strip())
        return PatchResult(
            success=True,
            applied_files=applied,
            diffs=diffs,
            combined_diff=combined,
            backups=backups,
        )

    def rollback_patches(self, backups: Dict[str, str]) -> None:
        """Rollbacks files to their backed up state."""
        for rel_path, content in backups.items():
            target_path = (self.root_dir / rel_path).resolve()
            if not content:
                # Was a newly created file
                if target_path.exists():
                    target_path.unlink()
            else:
                target_path.write_text(content, encoding="utf-8")
