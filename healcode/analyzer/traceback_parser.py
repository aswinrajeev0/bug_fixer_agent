import os
import re
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

class StackFrame(BaseModel):
    file_path: str
    line_number: int
    function_name: Optional[str] = None
    code_line: Optional[str] = None
    is_test_file: bool = False
    is_external_lib: bool = False

class FailureDiagnosis(BaseModel):
    test_name: str
    error_type: str
    error_message: str
    frames: List[StackFrame] = Field(default_factory=list)
    culprit_frame: Optional[StackFrame] = None
    raw_traceback: str = ""

class TracebackParser:
    """Parses Python stack traces to isolate culprit frames and root causes."""

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir).resolve()

    def parse(self, test_name: str, traceback_text: str) -> FailureDiagnosis:
        lines = traceback_text.splitlines()
        frames: List[StackFrame] = []
        error_type = "UnknownError"
        error_message = ""

        # 1. Standard python traceback: File "path/to/file.py", line 123, in func_name
        standard_pattern = re.compile(
            r'File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<func>\w+))?'
        )
        # 2. Pytest style: path/to/file.py:123: [in func_name or Error]
        pytest_loc_pattern = re.compile(
            r'^(?P<file>[^\s:]+\.py):(?P<line>\d+):(?:\s*(?:in\s+(?P<func>\w+)|(?P<rest>[^\n]*)))?'
        )

        for i, line in enumerate(lines):
            m = standard_pattern.search(line) or pytest_loc_pattern.search(line.strip())
            if m:
                raw_file = m.group("file")
                line_no = int(m.group("line"))
                func = m.group("func") if "func" in m.groupdict() and m.group("func") else None

                code_snippet = None
                if i > 0 and lines[i - 1].strip().startswith(">"):
                    code_snippet = lines[i - 1].strip().lstrip("> ")
                elif i + 1 < len(lines) and lines[i + 1].strip().startswith(">"):
                    code_snippet = lines[i + 1].strip().lstrip("> ")

                is_test = self._is_test_path(raw_file)
                is_ext = self._is_external_path(raw_file)
                norm_file = self._normalize_path(raw_file)

                frames.append(
                    StackFrame(
                        file_path=norm_file,
                        line_number=line_no,
                        function_name=func,
                        code_line=code_snippet,
                        is_test_file=is_test,
                        is_external_lib=is_ext,
                    )
                )

        # Extract Error Type & Message
        # Check for pytest 'E ' error lines first
        e_lines = [l.strip()[2:].strip() for l in lines if l.strip().startswith("E ")]
        if e_lines:
            first_e = e_lines[0]
            err_match = re.match(r"^([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Failure)):\s*(.*)", first_e)
            if err_match:
                error_type = err_match.group(1)
                error_message = err_match.group(2).strip() or "\n".join(e_lines)
            elif first_e.startswith("assert "):
                error_type = "AssertionError"
                error_message = "\n".join(e_lines)
            else:
                error_type = "AssertionError"
                error_message = "\n".join(e_lines)
        else:
            # Fallback to reverse scan
            for line in reversed(lines):
                line_str = line.strip()
                err_match = re.match(r"^([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Failure)):\s*(.*)", line_str)
                if err_match:
                    error_type = err_match.group(1)
                    error_message = err_match.group(2).strip()
                    break
                elif "AssertionError" in line_str:
                    error_type = "AssertionError"
                    error_message = line_str
                    break

        # Identify culprit frame:
        # Prefer the deepest frame in project source code (not external, not test file)
        culprit = None
        for frame in reversed(frames):
            if not frame.is_external_lib and not frame.is_test_file:
                culprit = frame
                break

        # Fallback to deepest non-external frame (e.g. assertion in test file)
        if not culprit:
            for frame in reversed(frames):
                if not frame.is_external_lib:
                    culprit = frame
                    break

        if not culprit and frames:
            culprit = frames[-1]

        return FailureDiagnosis(
            test_name=test_name,
            error_type=error_type,
            error_message=error_message,
            frames=frames,
            culprit_frame=culprit,
            raw_traceback=traceback_text,
        )

    def _is_test_path(self, path_str: str) -> bool:
        p = path_str.lower().replace("\\", "/")
        return (
            "test" in p
            or p.endswith("_test.py")
            or p.startswith("test_")
            or "/test_" in p
        )

    def _is_external_path(self, path_str: str) -> bool:
        p = path_str.lower().replace("\\", "/")
        return (
            "site-packages" in p
            or "dist-packages" in p
            or ".venv" in p
            or "python3" in p
            or "lib/python" in p
        )

    def _normalize_path(self, path_str: str) -> str:
        try:
            p = Path(path_str)
            if p.is_absolute():
                try:
                    rel = p.relative_to(self.root_dir)
                    return str(rel).replace("\\", "/")
                except ValueError:
                    return str(p).replace("\\", "/")
            return str(p).replace("\\", "/")
        except Exception:
            return path_str.replace("\\", "/")
