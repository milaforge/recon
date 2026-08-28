"""
CommitDiff
    │
    ├── FileDiff
    │     ├── FileChange
    │     └── patch
    │
    ├── FileDiff
    │     ├── FileChange
    │     └── patch
    │
    └── FileDiff
          ├── FileChange
          └── patch

"""

from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class ChangeStatus(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"


@dataclass(frozen=True, slots=True)
class FileChange:
    """
    A file path change within a commit.

    old_path is populated for changes where a previous path exists.
    new_path is populated for changes where a resulting path exists.
    """

    status: ChangeStatus
    old_path: str | None = None
    new_path: str | None = None

    @property
    def path(self) -> str:
        """
        Return the most relevant path for this change.

        For additions and modifications this is the new path.
        For deletions this is the old path.
        """
        return self.new_path or self.old_path or ""


@dataclass(frozen=True, slots=True)
class FileDiff:
    change: FileChange
    patch: str


@dataclass(frozen=True, slots=True)
class Commit:
    """
    A Git commit.

    This represents Git metadata only. It does not imply that the
    commit contains a security finding.
    """

    sha: str
    author: str
    timestamp: datetime
    subject: str
    files: tuple[FileDiff, ...] = ()


@dataclass(frozen=True, slots=True)
class CommitDiff:
    """
    A commit together with its file changes and raw patch.

    The raw patch is intentionally preserved. Detectors should be able
    to inspect the original Git evidence without reconstructing it.
    """

    commit: Commit
    files: tuple[FileDiff, ...]
