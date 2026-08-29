"""
Diff tests: file changes A/M/D/R/C, rename paths.
"""

from pathlib import Path

from recon.git.diff import (
    get_file_changes,
    get_file_diffs,
    get_file_patch,
    get_patch,
)
from recon.models.diff import ChangeStatus, FileChange, FileDiff


class TestGetFileChanges:
    """Tests for file change detection."""

    def test_get_file_changes_detects_added(self, git_repo: Path) -> None:
        """get_file_changes should detect added files."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "new.txt", "content\n")
        sha = commit(git_repo, "Add new.txt")

        changes = get_file_changes(sha, cwd=git_repo)

        assert len(changes) == 1
        change = changes[0]
        assert change.status == ChangeStatus.ADDED
        assert change.old_path is None
        assert change.new_path == "new.txt"

    def test_get_file_changes_detects_modified(self, git_repo: Path) -> None:
        """get_file_changes should detect modified files."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "file.txt", "original\n")
        commit(git_repo, "Initial")

        write_file(git_repo, "file.txt", "modified\n")
        sha = commit(git_repo, "Modify file.txt")

        changes = get_file_changes(sha, cwd=git_repo)

        assert len(changes) == 1
        change = changes[0]
        assert change.status == ChangeStatus.MODIFIED
        assert change.old_path == "file.txt"
        assert change.new_path == "file.txt"

    def test_get_file_changes_detects_deleted(self, git_repo: Path) -> None:
        """get_file_changes should detect deleted files."""
        from tests.fixtures.git_repo import commit, delete_file, write_file

        write_file(git_repo, "file.txt", "content\n")
        commit(git_repo, "Add file.txt")

        delete_file(git_repo, "file.txt")
        sha = commit(git_repo, "Delete file.txt")

        changes = get_file_changes(sha, cwd=git_repo)

        assert len(changes) == 1
        change = changes[0]
        assert change.status == ChangeStatus.DELETED
        assert change.old_path == "file.txt"
        assert change.new_path is None

    def test_get_file_changes_detects_rename(self, git_repo: Path) -> None:
        """get_file_changes should detect renamed files with both paths."""
        from tests.fixtures.git_repo import commit, rename_file, write_file

        write_file(git_repo, "old.txt", "content\n")
        commit(git_repo, "Add old.txt")

        rename_file(git_repo, "old.txt", "new.txt")
        sha = commit(git_repo, "Rename old.txt -> new.txt")

        changes = get_file_changes(sha, cwd=git_repo)

        assert len(changes) == 1
        change = changes[0]
        assert change.status == ChangeStatus.RENAMED
        assert change.old_path == "old.txt"
        assert change.new_path == "new.txt"

    def test_get_file_changes_detects_copy(self, git_repo: Path) -> None:
        """get_file_changes should handle copied files (if detected by Git)."""
        from tests.fixtures.git_repo import commit, run_git, run_shell, write_file

        write_file(git_repo, "source.txt", "content\n")
        commit(git_repo, "Add source.txt")

        # Copy file using shell cp and add
        run_shell("cp", "source.txt", "dest.txt", cwd=git_repo)
        run_git("add", "dest.txt", cwd=git_repo)
        sha = commit(git_repo, "Copy source.txt -> dest.txt")

        changes = get_file_changes(sha, cwd=git_repo)

        # Git only detects copies with -C flag in diff-tree; our implementation uses -C
        # This test verifies the framework handles COPIED status if detected
        copy_changes = [c for c in changes if c.status == ChangeStatus.COPIED]
        if copy_changes:
            change = copy_changes[0]
            assert change.old_path == "source.txt"
            assert change.new_path == "dest.txt"
        else:
            # If not detected as copy, it should be detected as added
            added_changes = [c for c in changes if c.status == ChangeStatus.ADDED]
            assert len(added_changes) >= 1

    def test_get_file_changes_multiple_files(self, git_repo: Path) -> None:
        """get_file_changes should handle multiple files in one commit."""
        from tests.fixtures.git_repo import commit, delete_file, write_file

        write_file(git_repo, "a.txt", "a\n")
        write_file(git_repo, "b.txt", "b\n")
        commit(git_repo, "Initial")

        write_file(git_repo, "c.txt", "c\n")      # Added
        write_file(git_repo, "a.txt", "a modified\n")  # Modified
        delete_file(git_repo, "b.txt")           # Deleted
        sha = commit(git_repo, "Multiple changes")

        changes = get_file_changes(sha, cwd=git_repo)

        assert len(changes) >= 3
        statuses = {c.status for c in changes}
        assert ChangeStatus.ADDED in statuses
        assert ChangeStatus.MODIFIED in statuses
        assert ChangeStatus.DELETED in statuses


class TestGetFilePatch:
    """Tests for file patch retrieval."""

    def test_get_file_patch_returns_diff_for_added(self, git_repo: Path) -> None:
        """get_file_patch should return diff for added file."""
        from recon.models.diff import ChangeStatus
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "new.txt", "hello\n")
        sha = commit(git_repo, "Add new.txt")

        change = FileChange(status=ChangeStatus.ADDED, new_path="new.txt")
        patch = get_file_patch(sha, change, cwd=git_repo)

        assert "hello" in patch
        assert "+++ b/new.txt" in patch

    def test_get_file_patch_returns_diff_for_modified(self, git_repo: Path) -> None:
        """get_file_patch should return diff for modified file."""
        from recon.models.diff import ChangeStatus
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "file.txt", "old\n")
        commit(git_repo, "Initial")

        write_file(git_repo, "file.txt", "new\n")
        sha = commit(git_repo, "Modify file.txt")

        change = FileChange(
            status=ChangeStatus.MODIFIED,
            old_path="file.txt",
            new_path="file.txt",
        )
        patch = get_file_patch(sha, change, cwd=git_repo)

        assert "-old" in patch
        assert "+new" in patch

    def test_get_file_patch_returns_diff_for_deleted(self, git_repo: Path) -> None:
        """get_file_patch should return diff for deleted file."""
        from recon.models.diff import ChangeStatus
        from tests.fixtures.git_repo import commit, delete_file, write_file

        write_file(git_repo, "file.txt", "content\n")
        commit(git_repo, "Add file.txt")

        delete_file(git_repo, "file.txt")
        sha = commit(git_repo, "Delete file.txt")

        change = FileChange(status=ChangeStatus.DELETED, old_path="file.txt")
        patch = get_file_patch(sha, change, cwd=git_repo)

        assert "-content" in patch

    def test_get_file_patch_uses_new_path_for_rename(self, git_repo: Path) -> None:
        """get_file_patch should use new path for renamed files."""
        from recon.models.diff import ChangeStatus
        from tests.fixtures.git_repo import commit, rename_file, write_file

        write_file(git_repo, "old.txt", "content\n")
        commit(git_repo, "Add old.txt")

        rename_file(git_repo, "old.txt", "new.txt")
        sha = commit(git_repo, "Rename")

        change = FileChange(
            status=ChangeStatus.RENAMED,
            old_path="old.txt",
            new_path="new.txt",
        )
        patch = get_file_patch(sha, change, cwd=git_repo)

        # Should show the rename or at least the content
        assert "content" in patch


class TestGetFileDiffs:
    """Tests for FileDiff object construction."""

    def test_get_file_diffs_returns_file_diffs(self, git_repo: Path) -> None:
        """get_file_diffs should return FileDiff objects with changes and patches."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "file.txt", "content\n")
        sha = commit(git_repo, "Add file.txt")

        diffs = get_file_diffs(sha, cwd=git_repo)

        assert len(diffs) == 1
        diff = diffs[0]
        assert isinstance(diff, FileDiff)
        assert diff.change.status == ChangeStatus.ADDED
        assert diff.change.new_path == "file.txt"
        assert "content" in diff.patch


class TestGetPatch:
    """Tests for complete commit patch."""

    def test_get_patch_returns_complete_patch(self, git_repo: Path) -> None:
        """get_patch should return complete textual patch for a commit."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "a.txt", "a\n")
        write_file(git_repo, "b.txt", "b\n")
        sha = commit(git_repo, "Add a and b")

        patch = get_patch(sha, cwd=git_repo)

        assert "a.txt" in patch
        assert "b.txt" in patch
        assert "+++ b/a.txt" in patch
        assert "+++ b/b.txt" in patch