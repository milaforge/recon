"""Parse source locations from unified Git diffs."""

import re
from collections.abc import Iterator

from recon.models.findings import LineType

_HUNK_HEADER = re.compile(
    r"^@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@"
)


def iter_diff_lines(patch: str) -> Iterator[tuple[LineType, int, str]]:
    """Yield changed and context lines with their source-file line number.

    Added and context lines refer to the new revision; deleted lines refer to
    the old revision.  Hunk-less synthetic patches retain their 1-based line
    positions, which keeps detector fixtures useful without inventing a file
    coordinate.
    """
    old_line: int | None = None
    new_line: int | None = None

    for patch_line, raw_line in enumerate(patch.splitlines(), start=1):
        hunk = _HUNK_HEADER.match(raw_line)
        if hunk:
            old_line = int(hunk["old"])
            new_line = int(hunk["new"])
            continue
        if raw_line.startswith(("+++ ", "--- ")):
            continue
        if raw_line.startswith("+"):
            line_number = new_line if new_line is not None else patch_line
            if new_line is not None:
                new_line += 1
            yield LineType.ADDITION, line_number, raw_line[1:]
        elif raw_line.startswith("-"):
            line_number = old_line if old_line is not None else patch_line
            if old_line is not None:
                old_line += 1
            yield LineType.DELETION, line_number, raw_line[1:]
        elif raw_line.startswith(" ") and old_line is not None and new_line is not None:
            yield LineType.CONTEXT, new_line, raw_line[1:]
            old_line += 1
            new_line += 1
