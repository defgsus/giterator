import os
import shutil
import tempfile
import secrets
import subprocess
import unittest
import time
from pathlib import Path
from typing import Union, Optional, Iterable, Dict

from giterator import Giterator, Commit


class RepoWrapper:

    def __init__(self):
        self.path = Path(tempfile.gettempdir()) / "py-giterator" / secrets.token_hex(20)

    def __enter__(self):
        os.makedirs(self.path, exist_ok=True)
        self.git("init")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        shutil.rmtree(self.path)

    def write_file(self, name: Union[str, Path], content: Optional[Union[str, bytes]] = None):
        name = Path(name)
        assert not name.is_absolute(), f"'name' must be a relative path, got '{name}'"
        full_name = self.path / name
        os.makedirs(full_name.parent, exist_ok=True)

        mode = "wb" if isinstance(content, bytes) else "w"

        with open(full_name, mode) as fp:
            if content:
                fp.write(content)

    def git(self, *args: str):
        """Call git in the repo directory with arguments"""
        subprocess.check_call(
            ("git", ) + args,
            cwd=self.path,
        )

    def git_commit(self, message: str, files: Optional[Iterable[str]] = None):
        if files:
            self.git("add", *files)
        else:
            self.git("add", ".")
        self.git("commit", f"-m{message}")
        # git does not store the millisecs in the commit date
        # so we make sure each
        time.sleep(1.1)

    def git_set_branch(self, name: str):
        try:
            self.git("checkout", name)
        except subprocess.SubprocessError:
            self.git("checkout", "-b", name)


class GiteratorTestCase(unittest.TestCase):

    def assertCommitMessages(self, messages: Iterable[str], commits: Iterable[Commit]):
        messages = list(messages)
        commits = list(commits)
        self.assertEqual(len(messages), len(commits), f"Expected {len(messages)} commits")
        commit_messages = [c.message for c in commits]
        self.assertEqual(messages, commit_messages)

    def assertCommitFiles(self, commit: Commit, expected_files: Dict[str, Union[str, bytes]]):
        files = list(commit.iter_commit_files())
        files_map = {
            f.name: f
            for f in files
        }
        done_set = set()
        for expected_filename, expected_content in expected_files.items():
            self.assertIn(expected_filename, files_map)
            file = files_map[expected_filename]

            if isinstance(expected_content, str):
                content = file.text()
            else:
                content = file.content

            self.assertEqual(expected_content, content, f"\nIn {commit} {file}")
            done_set.add(expected_filename)

        missing_set = set(files_map.keys()) - done_set

        self.assertFalse(missing_set, f"\nIn {commit}")

