import unittest

from giterator import Giterator

from tests.base import GiteratorTestCase, RepoWrapper


class TestGiterator(GiteratorTestCase):

    def test_100_linear_commits(self):
        with RepoWrapper() as repo:
            repo.write_file("file1.txt", "v1")
            repo.git_commit("Message 1")

            giterator = Giterator(repo.path)
            self.assertEqual(1, giterator.num_commits())

            repo.write_file("file1.txt", "v2")
            repo.git_commit("Message 2")

            repo.write_file("file2.txt", "v1")
            repo.git_commit("Message 3")

            giterator = Giterator(repo.path)
            self.assertEqual(3, giterator.num_commits())

            self.assertEqual("Message 1", giterator.first_commit().message)
            self.assertEqual("Message 3", giterator.last_commit().message)
            self.assertEqual("Message 2", giterator.last_commit("file1.txt").message)

            commits = list(giterator.iter_commits())
            self.assertEqual("Message 1", commits[0].message)
            self.assertEqual("Message 2", commits[1].message)
            self.assertEqual("Message 3", commits[2].message)

            self.assertCommitFiles(
                commits[0],
                {
                    "file1.txt": "v1",
                }
            )

    def test_200_branched_commits(self):
        with RepoWrapper() as repo:
            repo.git_set_branch("main")
            repo.write_file("file1.txt", "v1")
            repo.git_commit("m1")

            repo.git_set_branch("branch2")
            repo.write_file("file1.txt", "v2")
            repo.git_commit("m2")
            repo.write_file("file1.txt", "v3")
            repo.git_commit("m3")

            repo.git_set_branch("main")
            repo.write_file("file1.txt", "v4")
            repo.git_commit("m4")

            giterator = Giterator(repo.path, verbose=True)
            self.assertCommitMessages(
                ["m1", "m4"],
                giterator.iter_commits(),
            )
            self.assertCommitMessages(
                ["m1", "m2", "m3", "m4"],
                giterator.iter_commits(all=True),
            )
            self.assertCommitMessages(
                ["m1", "m2", "m3", "m4"],
                giterator.iter_commits(all=True, topo_order=True),
            )
            #for c in giterator.iter_commits(all=True):
            #    print(c.committer_date)