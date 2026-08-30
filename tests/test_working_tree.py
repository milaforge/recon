"""Working-tree scanner input tests."""

from pathlib import Path

from recon.git import get_working_tree_diffs
from tests.fixtures.git_repo import commit, run_git, write_file


def test_collects_staged_unstaged_and_untracked_changes(git_repo: Path) -> None:
    write_file(git_repo, "tracked.txt", "base\n")
    commit(git_repo, "base")
    write_file(git_repo, "staged.env", "API_KEY=staged-value\n")
    (git_repo / "tracked.txt").write_text("API_KEY=unstaged-value\n")
    (git_repo / "untracked.env").write_text("API_KEY=untracked-value\n")

    diffs = get_working_tree_diffs(git_repo)

    assert [diff.commit.subject for diff in diffs] == [
        "staged changes",
        "unstaged changes",
        "untracked changes",
    ]
    assert "staged-value" in diffs[0].files[0].patch
    assert "unstaged-value" in diffs[1].files[0].patch
    assert "untracked-value" in diffs[2].files[0].patch


def test_untracked_files_respect_gitignore(git_repo: Path) -> None:
    write_file(git_repo, ".gitignore", "ignored.env\n")
    commit(git_repo, "ignore local secrets")
    (git_repo / "ignored.env").write_text("API_KEY=ignored-value\n")
    (git_repo / "visible.env").write_text("API_KEY=visible-value\n")

    diffs = get_working_tree_diffs(git_repo)
    paths = [file.change.path for diff in diffs for file in diff.files]

    assert paths == ["visible.env"]
    assert run_git("check-ignore", "ignored.env", cwd=git_repo).strip() == "ignored.env"


def test_scans_repository_before_its_first_commit(git_repo: Path) -> None:
    (git_repo / "initial.env").write_text("API_KEY=initial-value\n")

    diffs = get_working_tree_diffs(git_repo)

    assert diffs[0].commit.sha == "0" * 40
    assert diffs[0].commit.subject == "untracked changes"
    assert "initial-value" in diffs[0].files[0].patch
