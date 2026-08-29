"""Immutable contracts for detection and classification."""

from dataclasses import dataclass
from enum import StrEnum

from .diff import Commit, FileDiff
from .findings import LineType


@dataclass(frozen=True, slots=True)
class DetectionContext:
    """The commit and file diff presented to every detector and classifier."""

    commit: Commit
    file_diff: FileDiff


@dataclass(frozen=True, slots=True)
class Evidence:
    """A detector candidate, including its safe display representation."""

    detector: str
    kind: str
    value: str
    redacted_value: str
    reason: str
    pattern: str | None = None
    line_type: LineType | None = None
    line_number: int | None = None


class Classification(StrEnum):
    """A bounded claim made about a piece of evidence."""

    SECRET = "secret"
    REFERENCE = "reference"
    FALSE_POSITIVE = "false_positive"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """A classifier decision with an explicit confidence and explanation."""

    classification: Classification
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
