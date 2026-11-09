import subprocess
import time
from pathlib import Path
from typing import List, Optional

class GitManager:
    """Manages Git checkpoints, rollbacks, and commits for safe autonomous healing."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = Path(repo_dir).resolve()
        self._checkpoint_stash: Optional[str] = None
        self._initial_branch: Optional[str] = None

    def _run_git(self, args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + args,
            cwd=str(self.repo_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def is_git_repo(self) -> bool:
        res = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return res.returncode == 0 and res.stdout.strip() == "true"

    def get_current_branch(self) -> Optional[str]:
        if not self.is_git_repo():
            return None
        res = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return res.stdout.strip() if res.returncode == 0 else None

    def has_uncommitted_changes(self) -> bool:
        if not self.is_git_repo():
            return False
        res = self._run_git(["status", "--porcelain"])
        return bool(res.stdout.strip())

    def create_checkpoint(self, label: str = "healcode-checkpoint") -> bool:
        """Saves current state so it can be rolled back reliably."""
        if not self.is_git_repo():
            return False

        self._initial_branch = self.get_current_branch()
        timestamp = int(time.time())
        stash_msg = f"{label}-{timestamp}"

        # Stash untracked and tracked files
        res = self._run_git(["stash", "push", "-u", "-m", stash_msg])
        if res.returncode == 0:
            self._checkpoint_stash = stash_msg
            # Pop stash back into working directory so agent works on current state
            self._run_git(["stash", "apply"])
            return True
        return False

    def rollback(self) -> bool:
        """Restores working tree back to clean state before changes."""
        if not self.is_git_repo():
            return False

        # Discard modifications and untracked files
        self._run_git(["restore", "."])
        self._run_git(["clean", "-fd"])
        return True

    def commit_fix(self, message: str, files: Optional[List[str]] = None) -> bool:
        """Stages files and creates a git commit."""
        if not self.is_git_repo():
            return False

        if files:
            add_res = self._run_git(["add"] + files)
        else:
            add_res = self._run_git(["add", "-A"])

        if add_res.returncode != 0:
            return False

        commit_res = self._run_git(["commit", "-m", message])
        return commit_res.returncode == 0

    def create_fix_branch(self, branch_name: str) -> bool:
        """Creates and switches to a dedicated healing branch."""
        if not self.is_git_repo():
            return False
        res = self._run_git(["checkout", "-b", branch_name])
        return res.returncode == 0
