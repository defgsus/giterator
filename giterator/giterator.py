import datetime
import re
import sys
import tarfile
import subprocess
from pathlib import Path
from io import BytesIO, StringIO
from typing import Generator, List, Tuple, Optional, Sequence, Union, Iterable

from .helper import parse_datetime, decode, get_git_renaming
from .commit import Commit
from .file import File


class Giterator:
    GIT_COMMAND = "git"

    _RE_CHANGE_NUMSTATS = re.compile(r"^(-|\d+)\s(-|\d+)\s(.*)$")
    _RE_CHANGE_SUMMARY = re.compile(r"^([a-z]+) mode (\d\d\d\d\d\d) (.+)")
    _MAX_TOKEN_LENGTH = 64
    _LOG_INFOS = [
        ("%H", "hash"),
        ("%T", "tree_hash"),
        ("%P", "parent_hash", lambda s: s.split() if s.strip() else []),
        ("%an", "author"),
        ("%ae", "author_email"),
        ("%aI", "author_date", parse_datetime),
        ("%an", "committer"),
        ("%ae", "committer_email"),
        ("%aI", "committer_date", parse_datetime),
        ("%D", "ref_names", lambda s: s.split(", ") if s.strip() else []),
        ("%e", "encoding"),
    ]
    # something that should never appear in a git message
    _DELIMITER1 = "$$$1-GiTeRaToR" + "-dAtA" + "-dElImItEr-$$$"
    _DELIMITER2 = "\n$$$2-GiTeRaToR" + "-dAtA" + "-dElImItEr-$$$"

    class _GitProcess:
        def __init__(self, parent: "Giterator", args: Iterable[str]):
            self.parent = parent
            self.process: Optional[subprocess.Popen] = None
            self.args = self.parent._no_duplicate_args(self.parent.GIT_COMMAND, *args)

        def __enter__(self):
            self.parent._log(" ".join(self.args))
            self.process = subprocess.Popen(
                self.args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.parent.path
            )
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.process.kill()
            self.process.wait()

    def __init__(
            self,
            path: Union[str, Path],
            verbose: bool = False,
    ):
        """
        Create a Giterator around a directory containing a git repository.

        :param path: pathlike, directory of git repository
        :param verbose: bool, print the git commands before executing
        """
        self.verbose = bool(verbose)
        self.path = str(path)
        self._num_commits = None
        self._hashes = set()

    def num_commits(self, *filenames: str, all: bool = False) -> int:
        if self._num_commits is None:
            args = ["rev-list", "--count"]
            if all:
                args.append("--all")
            else:
                args.append("--branches")

            if filenames:
                args += ["--"] + list(filenames)

            output = self._git(*args)
            self._num_commits = int(output)

        return self._num_commits

    def first_commit(self, *filenames: Union[str, Path]) -> Optional[Commit]:
        for commit in self.iter_commits(*filenames, reverse=False):
            return commit

    def last_commit(self, *filenames: Union[str, Path]) -> Optional[Commit]:
        for commit in self.iter_commits(*filenames, reverse=True):
            return commit

    def diff(self, *hash: str) -> str:
        return self._git(*("diff", *hash))

    def iter_commits(
            self,
            *filenames: Union[str, Path],
            reverse: bool = False,
            author: Optional[Union[str, Iterable[str]]] = None,
            committer: Optional[Union[str, Iterable[str]]] = None,
            since: Optional[Union[str, datetime.date, datetime.datetime]] = None,
            until: Optional[Union[str, datetime.date, datetime.datetime]] = None,
            before: Optional[Union[str, datetime.date, datetime.datetime]] = None,
            after: Optional[Union[str, datetime.date, datetime.datetime]] = None,
            min_parents: Optional[int] = None,
            max_parents: Optional[int] = None,
            no_min_parents: Optional[int] = None,
            no_max_parents: Optional[int] = None,
            topo_order: bool = False,
            all: bool = False,
            offset: int = 0,
            count: int = 0,
            with_changes: bool = True,
    ) -> Generator[Commit, None, None]:
        """
        Yields a dictionary for every git log that is found
        in the given directory.

        The ``git log`` command is used to get all the commit data.

        :param filenames: optional filenames.
            Show only commits that are enough to explain how the files that match the specified paths came to be.

        :param author: optional list of regex patterns to filter the commits by author
        :param committer: optional list of regex patterns to filter the commits by committer

        :param reverse: bool
            If True iterate from newest to oldest commit

        :param min_parents: optional int (e.g. '2' means only list merge commits)
        :param max_parents: optional int (e.g. '1' means do not list merge commits)

        :param offset: int
            Skip these number of commits before yielding.
            (via `git log --skip` parameter)

        :param count: int
            If > 0 then stop after this number of commits.

        :param with_changes: bool
            Avoid generating/parsing the file changes of each commit.

        :return: generator of dict
        """
        git_cmd = [
            "log",
        ]
        if with_changes:
            git_cmd += [
                "--numstat",
                "--summary",
            ]
        git_cmd += [
            f"--pretty={self._DELIMITER1}%n"
            f"{'%n'.join(i[0] for i in self._LOG_INFOS)}"
            f"%n%B{self._DELIMITER2}",
        ]
        if all:
            git_cmd += ["--all"]

        if topo_order:
            git_cmd += ["--topo-order"]
        else:
            git_cmd += ["--date-order"]

        if not reverse:
            git_cmd.append("--reverse")

        for key, variable in (
                ("author", author),
                ("committer", committer),
        ):
            if variable:
                if isinstance(variable, str):
                    variable = [variable]
                for s in variable:
                    git_cmd.append(f"--{key}={s}")

        for key, variable in (
                ("since", since),
                ("until", until),
                ("before", before),
                ("after", after),
        ):
            if variable:
                if callable(getattr(variable, "isoformat", None)):
                    variable = variable.isoformat()
                git_cmd.append(f"--{key}={variable}")

        if min_parents:
            git_cmd.append(f"--min-parents={min_parents}")
        if max_parents:
            git_cmd.append(f"--max-parents={max_parents}")
        if no_min_parents:
            git_cmd.append(f"--no-min-parents={no_min_parents}")
        if no_max_parents:
            git_cmd.append(f"--no-max-parents={no_max_parents}")

        if filenames:
            git_cmd += ["--"] + [str(f) for f in filenames]

        with self._git_process(*git_cmd) as process:
            commit = dict()
            current_line = 0
            cur_count = 0
            while count <= 0 or (cur_count - offset) < count:
                line = process.process.stdout.readline()
                if not line:
                    break

                line = decode(line, ignore_errors=True).rstrip()

                # a new commit starts
                if line == self._DELIMITER1:
                    if commit:
                        if cur_count >= offset:
                            yield Commit(self, **commit)
                        cur_count += 1
                    commit = dict()
                    current_line = 0

                # commit message ended and changes (numstats) follow
                elif line == self._DELIMITER2[1:]:
                    commit["message"] = commit["message"].rstrip()
                    current_line = -1

                # digest each line
                else:
                    if 1 <= current_line <= len(self._LOG_INFOS):
                        log_info: Tuple = self._LOG_INFOS[current_line - 1]
                        value = line
                        if len(log_info) > 2:
                            value = log_info[2](value)
                        commit[log_info[1]] = value

                    elif current_line == len(self._LOG_INFOS) + 1:
                        commit["message"] = line.rstrip()
                    elif current_line > len(self._LOG_INFOS) + 1:
                        commit["message"] += "\n" + line.rstrip()

                    elif current_line == -1:
                        line = line.strip()
                        if not self._parse_changes(commit, line):
                            self._parse_summary(commit, line)

                if current_line >= 0:
                    current_line += 1

            if commit:
                if cur_count >= offset and (count <= 0 or (cur_count - offset) < count):
                    yield Commit(self, **commit)

    def iter_commits_consecutive(
            self,
            offset: int = 0,
            count: int = 0,
            branch_length: int = 100,
            branch_age: int = 100,
    ) -> Generator[Commit, None, None]:

        branches = []
        for commit in self.iter_commits(offset=offset, count=count):
            if not commit.parent_hash:
                branches.append([0, commit])

            else:
                added = False
                new_branches = []
                for branch in branches:
                    for parent_hash in commit.parent_hash:
                        if not added and parent_hash == branch[-1].hash:
                            branch.append(commit)
                            added = True
                            break

                    branch[0] += 1
                    if len(branch) - 1 > branch_length or branch[0] > branch_age:
                        yield from branch[1:]
                    else:
                        new_branches.append(branch)

                branches = new_branches

                if not added:
                    branches.append([0, commit])

        for branch in branches:
            yield from branch[1:]

    def iter_commit_hashes(
            self,
            *filenames: str,
            offset: int = 0,
            count: int = 0,
            topo_order: bool = False,
            all: bool = False,
    ) -> Generator[dict, None, None]:
        """
        Yield commit hashes of the repository

        :param offset: int
            Skip these number of commits before yielding.

        :param count: int
            If > 0 then stop after this number of commits.

        :return: generator of dict
            {
                "date": datetime,
                "hash": str,
                "tree_hash": str,
                "children_hash": [str],
                "parent_hash": [str],
            }
        """
        git_cmd = [
            "rev-list",
            "--children",
            "--reverse",
            "--pretty=%aI %T %P"
        ]
        if topo_order:
            git_cmd += ["--topo-order"]
        if all:
            if "--all" not in self._git_args:
                git_cmd.append("--all")
        else:
            if "--branches" not in self._git_args:
                git_cmd.append("--branches")

        if filenames:
            git_cmd += ["--"] + list(filenames)

        with self._git_process(*git_cmd) as process:
            commit = dict()
            cur_count = 0
            while count <= 0 or (cur_count - offset) < count:
                line = process.process.stdout.readline()
                if not line:
                    break

                line = decode(line, ignore_errors=False).split()

                if line[0] == "commit":
                    commit["hash"] = line[1]
                    commit["children_hash"] = line[2:]
                else:
                    commit["date"] = parse_datetime(line[0])
                    commit["tree_hash"] = line[1]
                    commit["parent_hash"] = line[2:]
                    yield commit
                    cur_count += 1
                    commit = dict()

    def iter_files(
            self,
            treeish: str,
            filenames: Optional[Iterable[str]] = None
    ) -> Generator[Tuple[BytesIO, tarfile.TarInfo], None, None]:
        """
        Iterates through all files at a commit or tree,
        by reading the tar output of `git archive`.

        :param treeish: str
        :param filenames: optional list of paths or filenames
        :return: generator of File
        """
        git_cmd = [
            "archive", "--format=tar", treeish,
        ]
        if filenames:
            git_cmd += list(filenames)

        with self._git_process(*git_cmd) as process:
            # TODO: would be nice if we could iterate through
            #   the files in the stdout stream but
            #   tarfile lib requires seekable streams
            #   so the whole tar-file has to be in memory
            tar_data = BytesIO(process.process.stdout.read())
            error_response = process.process.stderr.read()

        tar_data.seek(0)

        try:
            for tarinfo in tarfile.open(fileobj=tar_data):
                if tarinfo.isfile():
                    yield File(self, tar_data, tarinfo)

        except tarfile.ReadError:
            if not filenames:
                return
            raise tarfile.ReadError(error_response.decode("utf-8"))

    def _log(self, *args):
        if self.verbose:
            print(*args, file=sys.stderr)

    def _no_duplicate_args(self, *args: str) -> List[str]:
        ret_args = []
        arg_set = set()
        for arg in args:
            if arg not in arg_set:
                arg_set.add(arg)
                ret_args.append(arg)
        return ret_args

    def _git(self, *args: str) -> str:
        args = self._no_duplicate_args(self.GIT_COMMAND, *args)
        self._log(" ".join(args))
        output = subprocess.check_output(args, cwd=self.path)
        return output.decode("utf-8")

    def _git_process(self, *args: str) -> _GitProcess:
        return self._GitProcess(self, args)

    def _parse_changes(self, commit: dict, line: str) -> bool:
        change_match = self._RE_CHANGE_NUMSTATS.match(line)
        if not change_match:
            return False

        if "changes" not in commit:
            commit["changes"] = []

        additions, deletions, name = change_match.groups()

        # TODO: additions/deletions should be integer converted
        #   but might be "-" in case of binary files
        commit["changes"].append({
            "name": name,
            "type": "change",
            "additions": additions,
            "deletions": deletions,
        })

        rename = get_git_renaming(name)
        if rename:
            commit["changes"][-1].update({
                "name": rename[1],
                "old_name": rename[0],
                "type": "rename"
            })

    def _parse_summary(self, commit: dict, line: str) -> bool:
        if line.startswith("rename "):
            return True

        change_match = self._RE_CHANGE_SUMMARY.match(line.strip())
        if not change_match:
            return False

        type, mode, name = change_match.groups()

        #if commit.get("changes"):
        for ch in commit["changes"]:
            if ch["name"] == name:
                ch["type"] = type
                ch["mode"] = mode
                return True

        #if not commit.get("changes"):
        #    commit["changes"] = []

        raise AssertionError(
            f"Expected '{name}' in --netstat changes, but got only --summary '{line}'\ncommit: {commit}"
        )
