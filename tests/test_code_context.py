from pathlib import Path
from healcode.analyzer.code_context import CodeContextExtractor
from healcode.analyzer.traceback_parser import FailureDiagnosis, StackFrame

def test_ast_scope_extraction(tmp_path):
    code_file = tmp_path / "module.py"
    code_file.write_text(
        "def helper():\n"
        "    return 42\n\n"
        "class Calculator:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n"
    )

    extractor = CodeContextExtractor(tmp_path)
    # Line 5 is 'return a + b' inside Calculator.add
    diag = FailureDiagnosis(
        test_name="test_dummy",
        error_type="AssertionError",
        error_message="failed",
        culprit_frame=StackFrame(
            file_path="module.py",
            line_number=5,
            function_name="add",
            is_test_file=False,
        ),
    )
    ctx = extractor.build_context(diag)
    assert ctx.culprit_file_context is not None
    assert len(ctx.culprit_file_context.enclosing_scopes) >= 1
    names = [s.name for s in ctx.culprit_file_context.enclosing_scopes]
    assert "add" in names
