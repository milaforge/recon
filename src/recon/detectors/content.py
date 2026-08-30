"""
Answers does this path look interesting?

We want to preserve whether the match occurred in an addition or deletion. That distinction is useful for historical exposure.
"""

import re
from dataclasses import dataclass
from re import Pattern

from ..models import ContentMatch
from .diff_lines import iter_diff_lines


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

        for line_type, line_number, content in iter_diff_lines(patch):
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
