import unittest

from giterator import Giterator

from tests.base import GiteratorTestCase, RepoWrapper


class TestFiles(GiteratorTestCase):

    def test_100_read_file(self):
        with RepoWrapper() as repo:
            repo.write_file("file1.txt", "content1")
            repo.write_file("sub/file2.bin", b"content2")
            repo.git_commit("Message 1")

            giterator = Giterator(repo.path)
            self.assertEqual(1, giterator.num_commits())

            commits = list(giterator.iter_commits())
            self.assertEqual("Message 1", commits[0].message)
            self.assertCommitFiles(
                commits[0],
                {
                    "file1.txt": "content1",
                    "sub/file2.bin": b"content2",
                }
            )
