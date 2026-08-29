"""
Commit tests: metadata, reachable commits.
"""

from datetime import datetime
from pathlib import Path

import pytest

from recon.git.commits import (
    get_all_reachable_commits,
    get_commit,
    get_reachable_commits,
)
from recon.models.diff import Commit


class TestGetCommit:
    """Tests for commit metadata retrieval."""

    def test_get_commit_returns_correct_metadata(self, git_repo: Path) -> None:
        """get_commit should return correct commit metadata."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "a.txt", "a\n")
        sha = commit(git_repo, "Add a.txt")

        commit_obj = get_commit(sha, cwd=git_repo)

        assert isinstance(commit_obj, Commit)
        assert commit_obj.sha == sha
        assert commit_obj.author == "Test User <test@example.com>"
        assert isinstance(commit_obj.timestamp, datetime)
        assert commit_obj.subject == "Add a.txt"
        assert commit_obj.files == ()

    def test_get_commit_fails_for_invalid_sha(self, git_repo: Path) -> None:
        """get_commit should fail for invalid SHA."""
        with pytest.raises(RuntimeError, match="unknown revision|bad object|ambiguous argument"):
            get_commit("invalid_sha", cwd=git_repo)


class TestGetReachableCommits:
    """Tests for reachable commit enumeration."""

    def test_get_reachable_commits_returns_all_ancestors(self, git_repo: Path) -> None:
        """get_reachable_commits should return all commits reachable from a ref."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "a.txt", "a\n")
        sha_a = commit(git_repo, "A")

        write_file(git_repo, "b.txt", "b\n")
        sha_b = commit(git_repo, "B")

        write_file(git_repo, "c.txt", "c\n")
        sha_c = commit(git_repo, "C")

        commits = get_reachable_commits("HEAD", cwd=git_repo)

        # Should return all 3 commits, topological oldest first
        assert len(commits) == 3
        assert commits[0] == sha_a
        assert commits[1] == sha_b
        assert commits[2] == sha_c

    def test_get_reachable_commits_from_branch(self, git_repo: Path) -> None:
        """get_reachable_commits should work from branch refs."""
        from tests.fixtures.git_repo import checkout, commit, create_branch, write_file

        write_file(git_repo, "a.txt", "a\n")
        commit(git_repo, "A")

        write_file(git_repo, "b.txt", "b\n")
        commit(git_repo, "B")

        create_branch(git_repo, "feature")

        # Switch back to main before committing C
        checkout(git_repo, "main")

        write_file(git_repo, "c.txt", "c\n")
        commit(git_repo, "C")

        # feature branch should have A, B
        feature_commits = get_reachable_commits("feature", cwd=git_repo)
        assert len(feature_commits) == 2

        # main should have A, B, C
        main_commits = get_reachable_commits("main", cwd=git_repo)
        assert len(main_commits) == 3


class TestGetAllReachableCommits:
    """Tests for deduplicated reachable commits from multiple refs."""

    def test_get_all_reachable_commits_deduplicates(self, git_repo: Path) -> None:
        """get_all_reachable_commits should deduplicate shared commits."""
        from tests.fixtures.git_repo import build_shared_commit

        _main_sha, _feature_sha, _shared_sha = build_shared_commit(git_repo)

        commits = get_all_reachable_commits(["main", "feature"], cwd=git_repo)

        # Should have 4 unique commits (A, B, C, D), not 6
        assert len(commits) == 4

        # All commits should be unique
        assert len(set(commits)) == len(commits)

    def test_get_all_reachable_commits_empty_refs(self, git_repo: Path) -> None:
        """get_all_reachable_commits should return empty list for empty refs."""
        commits = get_all_reachable_commits([], cwd=git_repo)
        assert commits == []

    def test_get_all_reachable_commits_single_ref(self, git_repo: Path) -> None:
        """get_all_reachable_commits should work with single ref."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "a.txt", "a\n")
        sha = commit(git_repo, "A")

        commits = get_all_reachable_commits(["HEAD"], cwd=git_repo)
        assert len(commits) == 1
        assert commits[0] == sha

    def test_merge_history_is_topological_and_deduplicated(self, git_repo: Path) -> None:
        """Parents precede children and each merge ancestor appears once."""
        from tests.fixtures.git_repo import build_merge_history

        root, main, feature, merge = build_merge_history(git_repo)
        commits = get_all_reachable_commits(["main", "feature"], cwd=git_repo)

        assert len(commits) == len(set(commits)) == 4
        assert commits[0] == root
        assert commits[-1] == merge
        assert commits.index(main) < commits.index(merge)
        assert commits.index(feature) < commits.index(merge)

    def test_shared_tag_and_remote_ref_do_not_duplicate_commits(self, git_repo: Path) -> None:
        """Different ref namespaces still share one commit traversal."""
        from tests.fixtures.git_repo import commit, run_git, write_file

        write_file(git_repo, "root.txt", "root\n")
        root = commit(git_repo, "root")
        write_file(git_repo, "tip.txt", "tip\n")
        tip = commit(git_repo, "tip")
        run_git("tag", "release-test", tip, cwd=git_repo)
        run_git("update-ref", "refs/remotes/origin/main", tip, cwd=git_repo)

        commits = get_all_reachable_commits(
            ["main", "refs/tags/release-test", "refs/remotes/origin/main"],
            cwd=git_repo,
        )

        assert commits == [root, tip]

    def test_empty_repository_head_has_no_reachable_commits(self, git_repo: Path) -> None:
        assert get_all_reachable_commits(["HEAD"], cwd=git_repo) == []
