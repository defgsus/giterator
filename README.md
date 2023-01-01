## giterator

A python iterator through git commits.

Current development state: **very early**

Just started to make a reusable module from the source that was previously 
copied from one project to the next.


### Usage

```python
from giterator import Giterator

repo = Giterator(PATH_TO_REPO)

# loop through all commits in historical order
for commit in repo.iter_commits():
    # all infos attached
    print(commit.committer_date, commit.hash)
    # loop through all files that have changed in this commit
    for file in commit.iter_commit_files():
        print(file.name, file.content)
```

### Background

The `Giterator.iter_commits()` method returns a generator which internally uses the `git log` command. 
While the git stdout stream is read, new `Commit` objects are yielded one-by-one. 
So iterating through millions of commits does not generally lead to memory problems.

The `Giterator.iter_files()` method, which is the base for all other `iter_files` methods, 
**currently** needs to hold all files in memory. Maybe this can be optimized.
