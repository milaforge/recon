"""Adapters that expose the original regex matchers through the new contract."""

from dataclasses import dataclass

from recon.models.detection import DetectionContext, Evidence

from .content import ContentDetector
from .path import PathDetector


@dataclass(frozen=True, slots=True)
class RegexPathDetector:
    """Adapt path-regex matches to first-class evidence."""

    matcher: PathDetector
    name: str = "path"

    def detect(self, context: DetectionContext) -> tuple[Evidence, ...]:
        return tuple(
            Evidence(
                detector=self.name,
                kind="path",
                value=match.path,
                redacted_value=match.path,
                pattern=match.pattern,
                reason="file path matched a user-supplied regular expression",
            )
            for match in self.matcher.detect(context.file_diff.change)
        )


@dataclass(frozen=True, slots=True)
class RegexContentDetector:
    """Adapt content-regex matches to first-class evidence."""

    matcher: ContentDetector
    name: str = "content"

    def detect(self, context: DetectionContext) -> tuple[Evidence, ...]:
        return tuple(
            Evidence(
                detector=self.name,
                kind="content",
                value=match.line,
                redacted_value=match.line,
                pattern=match.pattern,
                line_type=match.line_type,
                line_number=match.line_number,
                reason="diff content matched a user-supplied regular expression",
            )
            for match in self.matcher.detect(context.file_diff.patch)
        )
