from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .detection import (
        Classification,
        ClassificationResult,
        DetectionContext,
        Evidence,
    )


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

    commit_sha: str
    commit_subject: str
    author: str
    timestamp: datetime

    old_path: str | None
    new_path: str | None

    source: "Evidence"
    classification_result: "ClassificationResult"

    @property
    def detector(self) -> str:
        return self.source.detector

    @property
    def pattern(self) -> str:
        return self.source.pattern or ""

    @property
    def evidence(self) -> str:
        """Return the display-safe evidence value."""
        return self.source.redacted_value

    @property
    def line_type(self) -> LineType | None:
        return self.source.line_type

    @property
    def line_number(self) -> int | None:
        return self.source.line_number

    @property
    def classification(self) -> "Classification":
        return self.classification_result.classification

    @classmethod
    def from_evidence(
        cls,
        *,
        context: "DetectionContext",
        source: "Evidence",
        classification: "ClassificationResult",
    ) -> "Finding":
        change = context.file_diff.change
        return cls(
            commit_sha=context.commit.sha,
            commit_subject=context.commit.subject,
            author=context.commit.author,
            timestamp=context.commit.timestamp,
            old_path=change.old_path,
            new_path=change.new_path,
            source=source,
            classification_result=classification,
        )
