import ast
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from healcode.analyzer.traceback_parser import FailureDiagnosis, StackFrame

class ScopeContext(BaseModel):
    scope_type: str  # "function", "class", or "module"
    name: str
    start_line: int
    end_line: int
    snippet: str

class FileContext(BaseModel):
    relative_path: str
    absolute_path: str
    full_content: str
    culprit_lines: List[int] = Field(default_factory=list)
    enclosing_scopes: List[ScopeContext] = Field(default_factory=list)
    is_test_file: bool = False

class DiagnosticContext(BaseModel):
    diagnosis: FailureDiagnosis
    culprit_file_context: Optional[FileContext] = None
    test_file_context: Optional[FileContext] = None
    related_files: Dict[str, FileContext] = Field(default_factory=dict)

class CodeContextExtractor:
    """Uses AST and file inspection to extract precise context around failure points."""

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir).resolve()

    def build_context(self, diagnosis: FailureDiagnosis) -> DiagnosticContext:
        culprit_ctx = None
        test_ctx = None
        related: Dict[str, FileContext] = {}

        # 1. Process frames
        for frame in diagnosis.frames:
            if frame.is_test_file and not test_ctx:
                test_ctx = self._extract_file_context(
                    frame.file_path,
                    culprit_line=frame.line_number,
                    is_test=True,
                )
            elif not frame.is_external_lib:
                f_ctx = self._extract_file_context(
                    frame.file_path,
                    culprit_line=frame.line_number,
                    is_test=frame.is_test_file,
                )
                if f_ctx:
                    related[f_ctx.relative_path] = f_ctx

        # 2. Determine culprit context
        if diagnosis.culprit_frame and not diagnosis.culprit_frame.is_test_file:
            culprit_ctx = self._extract_file_context(
                diagnosis.culprit_frame.file_path,
                culprit_line=diagnosis.culprit_frame.line_number,
                is_test=False,
            )

        # 3. If culprit frame was a test file (e.g. Assertion failure in test),
        # inspect test file imports to find the source code implementation being tested!
        if (not culprit_ctx or (culprit_ctx and culprit_ctx.is_test_file)) and test_ctx:
            imported_impl_ctx = self._find_tested_implementation(test_ctx, diagnosis)
            if imported_impl_ctx:
                culprit_ctx = imported_impl_ctx
                related[imported_impl_ctx.relative_path] = imported_impl_ctx

        return DiagnosticContext(
            diagnosis=diagnosis,
            culprit_file_context=culprit_ctx,
            test_file_context=test_ctx,
            related_files=related,
        )

    def _find_tested_implementation(
        self, test_ctx: FileContext, diagnosis: FailureDiagnosis
    ) -> Optional[FileContext]:
        """Finds the underlying source file tested by an assertion failure in a test."""
        try:
            tree = ast.parse(test_ctx.full_content)
        except SyntaxError:
            return None

        # Collect imported modules from local project
        candidate_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                candidate_modules.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    candidate_modules.append(alias.name)

        # Search for candidate files in root_dir or same directory as test
        test_dir = Path(test_ctx.absolute_path).parent
        for mod in candidate_modules:
            rel_mod_path = mod.replace(".", "/") + ".py"
            # Try relative to test dir
            path_near_test = test_dir / rel_mod_path
            path_in_root = self.root_dir / rel_mod_path

            target_path = None
            if path_near_test.exists():
                target_path = path_near_test
            elif path_in_root.exists():
                target_path = path_in_root

            if target_path and target_path.is_file():
                # Extract file context for this implementation file
                impl_ctx = self._extract_file_context(
                    str(target_path), culprit_line=1, is_test=False
                )
                if impl_ctx:
                    return impl_ctx

        return None

    def _extract_file_context(
        self, file_path_str: str, culprit_line: int, is_test: bool
    ) -> Optional[FileContext]:
        path = Path(file_path_str)
        if not path.is_absolute():
            path = (self.root_dir / path).resolve()

        if not path.exists() or not path.is_file():
            return None

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        try:
            rel_path = str(path.relative_to(self.root_dir))
        except ValueError:
            rel_path = str(path)

        scopes = self._find_enclosing_scopes(content, culprit_line)

        return FileContext(
            relative_path=rel_path,
            absolute_path=str(path),
            full_content=content,
            culprit_lines=[culprit_line] if culprit_line else [],
            enclosing_scopes=scopes,
            is_test_file=is_test,
        )

    def _find_enclosing_scopes(self, content: str, line_number: int) -> List[ScopeContext]:
        scopes: List[ScopeContext] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return scopes

        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", 0)
                end = getattr(node, "end_lineno", start)

                if start <= line_number <= end:
                    scope_type = "class" if isinstance(node, ast.ClassDef) else "function"
                    snippet_lines = lines[start - 1 : end]
                    snippet = "\n".join(
                        f"{start + i:4d} | {l}" for i, l in enumerate(snippet_lines)
                    )
                    scopes.append(
                        ScopeContext(
                            scope_type=scope_type,
                            name=node.name,
                            start_line=start,
                            end_line=end,
                            snippet=snippet,
                        )
                    )

        scopes.sort(key=lambda s: (s.end_line - s.start_line))
        return scopes
