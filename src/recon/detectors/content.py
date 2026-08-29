"""
Answers does this path look interesting?

We want to preserve whether the match occurred in an addition or deletion. That distinction is useful for historical exposure.
"""

import re
from dataclasses import dataclass
from re import Pattern

from ..models import ContentMatch, LineType


@dataclass(frozen=True, slots=True)
class ContentDetector:
    """Detect regex matches inside Git diff content."""

    patterns: tuple[Pattern[str], ...]

    @classmethod
    def from_patterns(
        cls,
        patterns: list[str] | tuple[str, ...],
    ) -> "ContentDetector":
        return cls(patterns=tuple(re.compile(pattern) for pattern in patterns))

    def detect(
        self,
        patch: str,
    ) -> tuple[ContentMatch, ...]:
        """Return all regex matches found in the patch."""
        matches: list[ContentMatch] = []

        for line_number, raw_line in enumerate(
            patch.splitlines(),
            start=1,
        ):
            line_type, content = self._classify_line(raw_line)

            # Ignore Git metadata such as:
            #
            # diff --git
            # index
            # ---
            # +++
            #
            # We only care about actual patch lines.
            if line_type is None:
                continue

            for pattern in self.patterns:
                if pattern.search(content):
                    matches.append(
                        ContentMatch(
                            pattern=pattern.pattern,
                            line=content,
                            line_type=line_type,
                            line_number=line_number,
                        )
                    )

        return tuple(matches)

    @staticmethod
    def _classify_line(
        line: str,
    ) -> tuple[LineType | None, str]:
        """
        Classify a unified-diff line.

        Returns (None, ...) for diff metadata.
        """
        if line.startswith(("+++ ", "--- ")):
            return None, line

        if line.startswith("@@"):
            return None, line

        if line.startswith("+"):
            return LineType.ADDITION, line[1:]

        if line.startswith("-"):
            return LineType.DELETION, line[1:]

        if line.startswith(" "):
            return LineType.CONTEXT, line[1:]

        return None, line
