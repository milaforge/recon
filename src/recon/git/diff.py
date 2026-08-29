"""
This module will eventually feed both the path detector and content detector and answers <What changed>.
"""

from pathlib import Path

from recon.models.diff import (
    ChangeStatus,
    FileChange,
    FileDiff,
)

from .repository import run_git


def parse_change_status(status: str) -> ChangeStatus:
    """Parse Git diff-tree status into ChangeStatus enum."""
    code = status[0]
    if code == "A":
        return ChangeStatus.ADDED
    elif code == "M":
        return ChangeStatus.MODIFIED
    elif code == "D":
        return ChangeStatus.DELETED
    elif code == "R":
        return ChangeStatus.RENAMED
    elif code == "C":
        return ChangeStatus.COPIED
    else:
        return ChangeStatus.MODIFIED


def get_file_changes(commit: str, cwd: Path | str | None = None) -> list[FileChange]:
    """
    Return files changed by a commit.

    Rename/copy detection is enabled so that historical path movement
    is preserved.
    """
    output = run_git(
        "diff-tree",
        "-r",
        "--root",
        "-M",
        "-C",
        "--no-commit-id",
        "--name-status",
        "-z",
        commit,
        cwd=cwd,
    )

    fields = output.split("\x00")

    changes: list[FileChange] = []
    index = 0

    while index < len(fields):
        status = fields[index]

        if not status:
            index += 1
            continue

        index += 1

        code = status[0]
        change_status = parse_change_status(status)

        if code in {"R", "C"}:
            if index + 1 >= len(fields):
                break

            old_path = fields[index]
            new_path = fields[index + 1]

            index += 2

            changes.append(
                FileChange(
                    status=change_status,
                    old_path=old_path,
                    new_path=new_path,
                )
            )

        else:
            if index >= len(fields):
                break

            path = fields[index]
            index += 1

            if change_status == ChangeStatus.DELETED:
                changes.append(
                    FileChange(
                        status=change_status,
                        old_path=path,
                        new_path=None,
                    )
                )
            elif change_status == ChangeStatus.MODIFIED:
                changes.append(
                    FileChange(
                        status=change_status,
                        old_path=path,
                        new_path=path,
                    )
                )
            else:
                changes.append(
                    FileChange(
                        status=change_status,
                        old_path=None,
                        new_path=path,
                    )
                )

    return changes


def get_file_patch(
    commit: str,
    change: FileChange,
    cwd: Path | str | None = None,
) -> str:
    """
    Return the patch associated with one FileChange.

    For renames, use the new path when available.
    For deletions, use the old path.
    """

    path = change.path

    if not path:
        return ""

    return run_git(
        "show",
        "--format=",
        "--patch",
        "--find-renames",
        "--find-copies",
        commit,
        "--",
        path,
        cwd=cwd,
    )


def get_file_diffs(commit: str, cwd: Path | str | None = None) -> list[FileDiff]:
    """Build FileDiff objects for every changed file in a commit."""

    changes = get_file_changes(commit, cwd=cwd)

    return [
        FileDiff(
            change=change,
            patch=get_file_patch(commit, change, cwd=cwd),
        )
        for change in changes
    ]


def get_patch(commit: str, cwd: Path | str | None = None) -> str:
    """Return the complete textual patch for a commit."""
    return run_git(
        "show",
        "--format=",
        "--find-renames",
        "--find-copies",
        "--patch",
        commit,
        cwd=cwd,
    )

