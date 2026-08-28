from collections.abc import Iterable, Iterator
from pathlib import Path

from recon.models.diff import CommitDiff

from .commits import get_all_reachable_commits, get_commit_diff


def iter_commit_diffs(
    refs: Iterable[str],
    cwd: Path | str | None = None,
) -> Iterator[CommitDiff]:
    """
    Lazily traverse all commits reachable from the supplied refs.

    Duplicate commits reachable from multiple refs are returned once.
    """

    commits = get_all_reachable_commits(refs, cwd=cwd)

    for sha in commits:
        yield get_commit_diff(sha, cwd=cwd)
