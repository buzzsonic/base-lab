from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "push_data_branch.sh"


def git(directory: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=directory, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


class DataBranchPushTests(unittest.TestCase):
    def test_rebases_disjoint_remote_update_before_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, seed, first, second, verify = [root / name for name in ("remote.git", "seed", "first", "second", "verify")]
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE)
            git(root, "clone", str(remote), str(seed))
            for directory in (seed,):
                git(directory, "config", "user.name", "test")
                git(directory, "config", "user.email", "test@example.com")
            (seed / "seed.txt").write_text("seed\n")
            git(seed, "add", "seed.txt")
            git(seed, "commit", "-m", "seed")
            git(seed, "branch", "-M", "data")
            git(seed, "push", "-u", "origin", "data")
            git(root, "clone", "--branch", "data", str(remote), str(first))
            git(root, "clone", "--branch", "data", str(remote), str(second))
            for directory in (first, second):
                git(directory, "config", "user.name", "test")
                git(directory, "config", "user.email", "test@example.com")
            (first / "first.txt").write_text("first\n")
            git(first, "add", "first.txt")
            git(first, "commit", "-m", "first")
            (second / "second.txt").write_text("second\n")
            git(second, "add", "second.txt")
            git(second, "commit", "-m", "second")
            git(second, "push", "origin", "HEAD:data")
            subprocess.run(["bash", str(SCRIPT), "data", "3"], cwd=first, check=True)
            git(root, "clone", "--branch", "data", str(remote), str(verify))
            self.assertTrue((verify / "first.txt").exists())
            self.assertTrue((verify / "second.txt").exists())


if __name__ == "__main__":
    unittest.main()
