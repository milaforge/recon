"""
Answers does this diff contain interesting content?
"""

import re
from dataclasses import dataclass
from re import Pattern

from ..models import FileChange, PathMatch


@dataclass(frozen=True, slots=True)
class PathDetector:
    """Detect regex matches against Git file paths."""

    patterns: tuple[Pattern[str], ...]

    @classmethod
    def from_patterns(
        cls,
        patterns: list[str] | tuple[str, ...],
    ) -> "PathDetector":
        return cls(patterns=tuple(re.compile(pattern) for pattern in patterns))

    def detect(self, change: FileChange) -> tuple[PathMatch, ...]:
        """Return all regex matches found in a file change's paths."""
        matches: list[PathMatch] = []

        paths = {
            path for path in (change.old_path, change.new_path) if path is not None
        }

        for path in paths:
            for pattern in self.patterns:
                if pattern.search(path):
                    matches.append(
                        PathMatch(
                            pattern=pattern.pattern,
                            path=path,
                        )
                    )

        return tuple(matches)
