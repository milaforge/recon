"""Build scanner inputs from changes that have not been committed."""

from datetime import UTC, datetime
from pathlib import Path

from recon.models import ChangeStatus, Commit, CommitDiff, FileChange, FileDiff

from .diff import parse_change_status
from .repository import GitError, get_git_config, run_git


def get_working_tree_diffs(cwd: Path | str | None = None) -> list[CommitDiff]:
    """Return staged, unstaged, and non-ignored untracked changes as scan inputs."""
    try:
        head = run_git("rev-parse", "HEAD", cwd=cwd).strip()
    except GitError:
        # An initial working tree has no commit yet, but is still useful to scan.
        head = "0" * 40
    author = get_git_config("user.name", cwd=cwd) or "Working tree"
    now = datetime.now(UTC)
    results: list[CommitDiff] = []

    for subject, cached in (("staged changes", True), ("unstaged changes", False)):
        args = ["diff"]
        if cached:
            args.append("--cached")
        args.extend(("--name-status", "-z"))
        changes = _parse_changes(run_git(*args, cwd=cwd))
        files = tuple(
            FileDiff(change, _tracked_patch(change, cached=cached, cwd=cwd))
            for change in changes
        )
        if files:
            results.append(CommitDiff(Commit(head, author, now, subject), files))

    untracked = run_git("ls-files", "--others", "--exclude-standard", "-z", cwd=cwd)
    files = tuple(
        _untracked_diff(path, cwd=cwd) for path in untracked.split("\x00") if path
    )
    if files:
        results.append(
            CommitDiff(Commit(head, author, now, "untracked changes"), files)
        )
    return results


def _parse_changes(output: str) -> list[FileChange]:
    fields = output.split("\x00")
    changes: list[FileChange] = []
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index]
        index += 1
        change_status = parse_change_status(status)
        if status[0] in {"R", "C"}:
            old_path, new_path = fields[index : index + 2]
            index += 2
        else:
            path = fields[index]
            index += 1
            old_path = (
                path
                if change_status in {ChangeStatus.MODIFIED, ChangeStatus.DELETED}
                else None
            )
            new_path = path if change_status is not ChangeStatus.DELETED else None
        changes.append(FileChange(change_status, old_path, new_path))
    return changes


def _tracked_patch(change: FileChange, *, cached: bool, cwd: Path | str | None) -> str:
    args = ["diff"]
    if cached:
        args.append("--cached")
    args.extend(("--patch", "--find-renames", "--", change.path))
    return run_git(*args, cwd=cwd)


def _untracked_diff(path: str, cwd: Path | str | None) -> FileDiff:
    root = Path(cwd or ".")
    content = (root / path).read_text(errors="replace").splitlines()
    patch = "\n".join(
        (
            f"diff --git a/{path} b/{path}",
            "new file mode 100644",
            "--- /dev/null",
            f"+++ b/{path}",
            f"@@ -0,0 +1,{len(content)} @@",
            *(f"+{line}" for line in content),
        )
    )
    return FileDiff(FileChange(ChangeStatus.ADDED, new_path=path), f"{patch}\n")
