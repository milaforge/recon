from dataclasses import dataclass
from .diff import Commit, FileChange
from enum import Enum


class MatchType(str, Enum):
    PATH = "path"
    CONTENT = "content"


class LineType(str, Enum):
    ADDITION = "addition"
    DELETION = "deletion"
    CONTEXT = "context"


@dataclass(frozen=True, slots=True)
class PathMatch:
    """Evidence that a regex matched a Git path."""

    pattern: str
    path: str


@dataclass(frozen=True, slots=True)
class ContentMatch:
    """Evidence that a regex matched content in a Git diff."""

    pattern: str
    line: str
    line_type: LineType
    line_number: int | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    """
    A normalized security-reconnaissance finding.

    A finding records evidence. It deliberately does not claim that
    the matched content is definitely a secret.
    """

    detector: str

    commit_sha: str
    commit_subject: str
    author: str
    timestamp: str

    old_path: str | None
    new_path: str | None

    pattern: str
    evidence: str

    @classmethod
    def from_path_match(
        cls,
        *,
        match: PathMatch,
        change: FileChange,
        commit_sha: str,
        commit_subject: str,
        author: str,
        timestamp: str,
    ) -> "Finding":
        return cls(
            detector="path",
            commit_sha=commit_sha,
            commit_subject=commit_subject,
            author=author,
            timestamp=timestamp,
            old_path=change.old_path,
            new_path=change.new_path,
            pattern=match.pattern,
            evidence=match.path,
        )

    @classmethod
    def from_content_match(
        cls,
        *,
        match: ContentMatch,
        change: FileChange,
        commit_sha: str,
        commit_subject: str,
        author: str,
        timestamp: str,
    ) -> "Finding":
        return cls(
            detector="content",
            commit_sha=commit_sha,
            commit_subject=commit_subject,
            author=author,
            timestamp=timestamp,
            old_path=change.old_path,
            new_path=change.new_path,
            pattern=match.pattern,
            evidence=match.line,
        )
