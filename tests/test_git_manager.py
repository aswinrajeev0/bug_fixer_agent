import subprocess
from pathlib import Path
from healcode.sandbox.git_manager import GitManager

def test_git_manager_non_git_repo(tmp_path):
    gm = GitManager(tmp_path)
    assert gm.is_git_repo() is False
    assert gm.get_current_branch() is None
    assert gm.has_uncommitted_changes() is False

def test_git_manager_with_git_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True)

    gm = GitManager(tmp_path)
    assert gm.is_git_repo() is True

    # Create initial commit
    f = tmp_path / "init.txt"
    f.write_text("initial")
    subprocess.run(["git", "add", "init.txt"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), check=True)

    # Make uncommitted change
    f.write_text("modified")
    assert gm.has_uncommitted_changes() is True

    # Test rollback
    assert gm.rollback() is True
    assert f.read_text() == "initial"
    assert gm.has_uncommitted_changes() is False

    # Test commit_fix
    f.write_text("fixed")
    assert gm.commit_fix("fix bug", ["init.txt"]) is True
    assert gm.has_uncommitted_changes() is False
