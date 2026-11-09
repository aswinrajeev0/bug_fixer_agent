from pathlib import Path
from healcode.sandbox.patcher import CodePatcher
from healcode.agent.models import FilePatch

def test_generate_diff(tmp_path):
    patcher = CodePatcher(tmp_path)
    old = "def foo():\n    return 1\n"
    new = "def foo():\n    return 2\n"
    diff = patcher.generate_diff(old, new, "foo.py")
    assert "-    return 1" in diff
    assert "+    return 2" in diff

def test_validate_syntax(tmp_path):
    patcher = CodePatcher(tmp_path)
    valid_code = "def add(a, b):\n    return a + b\n"
    assert patcher.validate_syntax(valid_code, "test.py") is None

    invalid_code = "def add(a, b:\n    return a + b\n"
    err = patcher.validate_syntax(invalid_code, "test.py")
    assert err is not None
    assert "SyntaxError" in err

def test_apply_and_rollback_patches(tmp_path):
    patcher = CodePatcher(tmp_path)
    target_file = tmp_path / "hello.py"
    target_file.write_text("print('hello')\n")

    patch = FilePatch(
        file_path="hello.py",
        description="Update greeting",
        new_content="print('hello world')\n",
    )

    result = patcher.apply_patches([patch])
    assert result.success is True
    assert target_file.read_text() == "print('hello world')\n"
    assert "+print('hello world')" in result.combined_diff

    # Test rollback
    patcher.rollback_patches(result.backups)
    assert target_file.read_text() == "print('hello')\n"
