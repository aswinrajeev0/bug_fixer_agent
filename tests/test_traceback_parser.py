from pathlib import Path
from healcode.analyzer.traceback_parser import TracebackParser

def test_parse_pytest_traceback(tmp_path):
    parser = TracebackParser(tmp_path)
    sample_traceback = """
    def test_divide():
>       assert divide(10, 0) == 0

tests/test_math.py:5: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def divide(a, b):
>       return a / b
E       ZeroDivisionError: division by zero

src/math.py:12: ZeroDivisionError
"""
    diagnosis = parser.parse("test_divide", sample_traceback)

    assert diagnosis.test_name == "test_divide"
    assert diagnosis.error_type == "ZeroDivisionError"
    assert "division by zero" in diagnosis.error_message
    assert diagnosis.culprit_frame is not None
    assert diagnosis.culprit_frame.file_path == "src/math.py"
    assert diagnosis.culprit_frame.line_number == 12
    assert diagnosis.culprit_frame.is_test_file is False

def test_parse_assertion_error(tmp_path):
    parser = TracebackParser(tmp_path)
    sample = """
    def test_val():
>       assert calculate(10) == 20
E       assert 10 == 20

tests/test_calc.py:8: AssertionError
"""
    diagnosis = parser.parse("test_val", sample)
    assert diagnosis.error_type == "AssertionError"
    assert "assert 10 == 20" in diagnosis.error_message
