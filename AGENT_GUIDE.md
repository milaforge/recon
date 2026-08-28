# Agent Development Guide — Recon

**Purpose**: Enable consistent, non-duplicative feature development. Follow these patterns exactly.

---

## Golden Rules

1. **Use existing fixtures** — Never create test repos from scratch
2. **Follow detector protocol** — Implement `PathDetector` or `ContentDetector` interface
3. **Add tests at the right layer** — Unit → Integration → Semantic
4. **No new abstractions** — Extend, don't wrap
5. **Evidence over verdicts** — Detectors return matches, not classifications

---

## Adding a New Detector

### 1. Choose Detector Type

| Need | Type | Base Class |
|------|------|------------|
| Match file paths | `PathDetector` | `detectors/path.py` |
| Match diff content | `ContentDetector` | `detectors/content.py` |
| Both | Two detectors | — |

### 2. Implement the Protocol

**Path Detector** (`src/recon/detectors/my_detector.py`):

```python
import re
from dataclasses import dataclass
from re import Pattern

from ..models import FileChange, PathMatch


@dataclass(frozen=True, slots=True)
class MyPathDetector:
    patterns: tuple[Pattern[str], ...]

    @classmethod
    def from_patterns(cls, patterns: list[str] | tuple[str, ...]) -> "MyPathDetector":
        return cls(patterns=tuple(re.compile(p) for p in patterns))

    def detect(self, change: FileChange) -> tuple[PathMatch, ...]:
        matches: list[PathMatch] = []
        paths = {p for p in (change.old_path, change.new_path) if p}
        for path in paths:
            for pattern in self.patterns:
                if pattern.search(path):
                    matches.append(PathMatch(pattern=pattern.pattern, path=path))
        return tuple(matches)
```

**Content Detector** (`src/recon/detectors/my_detector.py`):

```python
import re
from dataclasses import dataclass
from re import Pattern

from ..models import ContentMatch, LineType


@dataclass(frozen=True, slots=True)
class MyContentDetector:
    patterns: tuple[Pattern[str], ...]

    @classmethod
    def from_patterns(cls, patterns: list[str] | tuple[str, ...]) -> "MyContentDetector":
        return cls(patterns=tuple(re.compile(p) for p in patterns))

    def detect(self, patch: str) -> tuple[ContentMatch, ...]:
        matches: list[ContentMatch] = []
        for line_number, raw_line in enumerate(patch.splitlines(), start=1):
            line_type, content = self._classify_line(raw_line)
            if line_type is None:
                continue
            for pattern in self.patterns:
                if pattern.search(content):
                    matches.append(ContentMatch(
                        pattern=pattern.pattern,
                        line=content,
                        line_type=line_type,
                        line_number=line_number,
                    ))
        return tuple(matches)

    @staticmethod
    def _classify_line(line: str) -> tuple[LineType | None, str]:
        if line.startswith("+++ ") or line.startswith("--- "):
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
```

### 3. Export in `detectors/__init__.py`

```python
from .path import PathDetector
from .content import ContentDetector
from .my_detector import MyPathDetector, MyContentDetector

__all__ = [
    "PathDetector",
    "ContentDetector",
    "MyPathDetector",
    "MyContentDetector",
]
```

### 4. Wire into CLI (`commands/search_exposure.py`)

Add pattern options:

```python
my_pattern: Annotated[
    list[str],
    typer.Option("-m", "--my-pattern", help="My custom pattern."),
] = [],
```

Build detector in `_build_detectors`:

```python
def _build_detectors(...):
    ...
    my_detector = MyContentDetector.from_patterns(my_pattern) if my_pattern else None
    return path_detector, content_detector, my_detector
```

Update scanner instantiation:

```python
scanner = ExposureScanner(
    path_detector=path_detector,
    content_detector=content_detector,
    my_detector=my_detector,  # Add to scanner
)
```

### 5. Update Scanner (`scanner.py`)

```python
@dataclass(frozen=True, slots=True)
class ExposureScanner:
    path_detector: PathDetector | None = field(default=None, kw_only=True)
    content_detector: ContentDetector | None = field(default=None, kw_only=True)
    my_detector: MyContentDetector | None = field(default=None, kw_only=True)

    def _scan_commit(self, commit_diff: CommitDiff) -> Iterator[Finding]:
        for file_diff in commit_diff.files:
            change = file_diff.change

            if self.path_detector:
                for match in self.path_detector.detect(change):
                    yield Finding.from_path_match(...)

            if self.content_detector:
                for match in self.content_detector.detect(file_diff.patch):
                    yield Finding.from_content_match(...)

            if self.my_detector:
                for match in self.my_detector.detect(file_diff.patch):
                    yield Finding.from_content_match(  # or from_path_match
                        match=match,
                        change=change,
                        commit_sha=commit_diff.commit.sha,
                        commit_subject=commit_diff.commit.subject,
                        author=commit_diff.commit.author,
                        timestamp=commit_diff.commit.timestamp,
                    )
```

---

## Writing Tests — Use Existing Fixtures

### Unit Tests (No Git)

**File**: `tests/test_my_detector.py`

```python
import pytest
from recon.detectors.my_detector import MyContentDetector
from recon.models.findings import ContentMatch, LineType


class TestMyContentDetector:
    def test_matches_my_pattern_in_addition(self):
        detector = MyContentDetector.from_patterns([r"MY_SECRET="])
        patch = "+MY_SECRET=value\n"
        matches = detector.detect(patch)
        assert len(matches) == 1
        assert matches[0].line_type == LineType.ADDITION
        assert matches[0].line == "MY_SECRET=value"

    def test_ignores_metadata(self):
        detector = MyContentDetector.from_patterns([r"diff"])
        patch = "diff --git a/b\n+diff = real\n"
        matches = detector.detect(patch)
        assert len(matches) == 1
        assert matches[0].line == "diff = real"
```

### Integration Tests (Real Git)

**File**: `tests/test_scanner.py` — Add to existing class

```python
def test_scanner_finds_my_pattern(self, git_repo: Path) -> None:
    from tests.fixtures.git_repo import write_file, commit

    write_file(git_repo, "config.env", "MY_SECRET=abc123\n")
    commit(git_repo, "Add my secret")

    findings = scan_repo(git_repo, my_patterns=[r"MY_SECRET="])
    assert len(findings) == 1
    assert findings[0].detector == "my"
    assert findings[0].evidence == "MY_SECRET=abc123"
```

### Semantic Tests (Real Scenarios)

**File**: `tests/test_historical_semantics.py` — Add to existing class

```python
class TestMyDetectorScenarios:
    def test_my_secret_lifecycle(self, git_repo: Path) -> None:
        """Test secret added → rotated → deleted."""
        from tests.fixtures.git_repo import write_file, commit, delete_file

        write_file(git_repo, "README.md", "# Project\n")
        commit(git_repo, "initial")

        write_file(git_repo, "secrets.env", "MY_SECRET=v1\n")
        commit(git_repo, "add secret")

        write_file(git_repo, "secrets.env", "MY_SECRET=v2\n")
        commit(git_repo, "rotate secret")

        delete_file(git_repo, "secrets.env")
        commit(git_repo, "remove secret")

        findings = scan_repo(git_repo, my_patterns=[r"MY_SECRET="])
        assert len(findings) == 3
        subjects = {f.commit_subject for f in findings}
        assert subjects == {"add secret", "rotate secret", "remove secret"}

    def test_my_secret_on_feature_branch_only(self, git_repo: Path) -> None:
        """Secret only exists on feature branch."""
        from tests.fixtures.git_repo import write_file, commit, create_branch, checkout

        write_file(git_repo, "README.md", "# Project\n")
        commit(git_repo, "initial")

        create_branch(git_repo, "feature")
        write_file(git_repo, "secret.env", "MY_SECRET=only_here\n")
        commit(git_repo, "add secret")
        checkout(git_repo, "main")

        findings_main = scan_repo(git_repo, my_patterns=[r"MY_SECRET="], refs=["main"])
        assert len(findings_main) == 0

        findings_feature = scan_repo(git_repo, my_patterns=[r"MY_SECRET="], refs=["feature"])
        assert len(findings_feature) == 1
```

---

## Using Scenario Builders

### Available Builders (`tests/fixtures/git_repo.py`)

| Builder | Returns | Use For |
|---------|---------|---------|
| `build_linear_history(repo)` | `list[str]` SHAs | Linear secret lifecycle |
| `build_branch_with_secret(repo)` | `(main_sha, feature_sha)` | Branch-isolated secrets |
| `build_shared_commit(repo)` | `(main_sha, feature_sha, shared_sha)` | Deduplication testing |
| `build_remote_with_branches(remote, working)` | `list[(branch, sha)]` | Fetch/remote testing |

### Example Usage

```python
def test_shared_commit_deduplication(self, git_repo: Path) -> None:
    from tests.fixtures.git_repo import build_shared_commit

    main_sha, feature_sha, shared_sha = build_shared_commit(git_repo)
    # shared_sha commit has SECRET=shared

    findings = scan_repo(git_repo, content_patterns=[r"SECRET="], refs=["main", "feature"])
    assert len(findings) == 1  # Deduplicated!
    assert findings[0].commit_sha == shared_sha
```

### Helper Functions (Direct Use)

```python
from tests.fixtures.git_repo import (
    write_file, commit, delete_file, rename_file,
    create_branch, checkout, run_git,
    get_head_sha, get_remote_branches,
    is_shallow, make_shallow, push_to_remote, clone_repo,
)
```

---

## Adding a New CLI Command

### 1. Create Command Module

`src/recon/commands/my_command.py`:

```python
import typer
from pathlib import Path

from recon.git import prepare_repository
from recon.git.traversal import iter_commit_diffs
from recon.detectors.path import PathDetector
from recon.detectors.content import ContentDetector
from recon.scanner import ExposureScanner
from recon.reporting.terminal import TerminalReporter
from recon.reporting.json import JSONReporter


app = typer.Typer(name="my_command", help="Description.")


@app.callback(invoke_without_command=True)
def my_command(
    ctx: typer.Context,
    # ... options ...
) -> None:
    # Reuse _resolve_refs, _build_detectors, _build_reporter from search_exposure.py
    # Or import them if shared
    pass
```

### 2. Register in CLI (`cli.py`)

```python
from .commands.my_command import app as my_command_app

app.add_typer(my_command_app, name="my-command")
```

### 3. Reuse Shared Logic

**Don't duplicate** `_resolve_refs`, `_build_detectors`, `_build_reporter`, `scan_repo` helper.

Create `commands/common.py` if needed:

```python
# commands/common.py
from recon.git import prepare_repository
from recon.git.traversal import iter_commit_diffs
from recon.detectors.path import PathDetector
from recon.detectors.content import ContentDetector
from recon.scanner import ExposureScanner
from recon.reporting.terminal import TerminalReporter
from recon.reporting.json import JSONReporter
from pathlib import Path
from typing import Annotated, list
import typer


def resolve_refs(all_refs: bool, interactive: bool, refs: list[str], cwd: Path) -> list[str]:
    # ... existing logic ...


def build_detectors(path_patterns: list[str], content_patterns: list[str]):
    # ... existing logic ...


def build_reporter(format: str):
    # ... existing logic ...


def run_scan(cwd: Path, refs: list[str], path_detector, content_detector) -> list[Finding]:
    prepare_repository(cwd=cwd)
    scanner = ExposureScanner(path_detector=path_detector, content_detector=content_detector)
    commits = iter_commit_diffs(refs, cwd=cwd)
    return list(scanner.scan(commits))
```

---

## Code Style Requirements

### Imports

```python
# Standard library first
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# Third party
import typer

# Local — use relative imports
from ..models import FileChange, PathMatch
from .base import PathDetector
```

### Dataclasses

```python
@dataclass(frozen=True, slots=True)
class MyClass:
    field1: str
    field2: int = 0
```

### Type Hints

```python
def my_func(patterns: list[str] | tuple[str, ...]) -> tuple[Pattern[str], ...]:
    ...
```

### Error Handling

```python
from recon.git.repository import GitError

try:
    prepare_repository(cwd=cwd)
except GitError as exc:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(1)
```

---

## Testing Checklist

Before submitting a detector:

- [ ] Unit tests in `tests/test_my_detector.py`
- [ ] Integration test in `tests/test_scanner.py`
- [ ] Semantic test in `tests/test_historical_semantics.py`
- [ ] Uses `build_linear_history` or `build_branch_with_secret` for scenarios
- [ ] Tests line type classification (addition/deletion/context)
- [ ] Tests metadata filtering (diff headers, hunk headers)
- [ ] Tests binary patch handling
- [ ] Tests empty patterns return empty
- [ ] Tests multiple patterns
- [ ] All existing tests still pass: `uv run pytest`

---

## Common Pitfalls to Avoid

| Pitfall | Correct Approach |
|---------|------------------|
| Creating temp Git repo in test | Use `git_repo` fixture |
| Mocking Git commands | Use real `git` via fixtures |
| Adding classification logic to detector | Return evidence only |
| Duplicating `scan_repo` helper | Import from test module or `commands/common.py` |
| New abstraction layer | Extend existing protocol |
| Skipping semantic tests | They catch real bugs |

---

## File Locations Quick Reference

| Task | File |
|------|------|
| New path detector | `src/recon/detectors/my_path.py` |
| New content detector | `src/recon/detectors/my_content.py` |
| Unit tests | `tests/test_my_detector.py` |
| Integration tests | `tests/test_scanner.py` |
| Semantic tests | `tests/test_historical_semantics.py` |
| Test fixtures | `tests/fixtures/git_repo.py` |
| CLI command | `src/recon/commands/my_command.py` |
| Shared CLI logic | `src/recon/commands/common.py` |
| Scanner orchestration | `src/recon/scanner.py` |
| Finding models | `src/recon/models/findings.py` |

---

## Running Checks

```bash
# Format
uv run ruff format src/ tests/

# Lint
uv run ruff check src/ tests/

# Type check
uv run basedpyright src/

# Tests
uv run pytest

# Tests with coverage
uv run pytest --cov=recon
```

---

## Architecture Decision Log

| Decision | Rationale |
|----------|-----------|
| Real Git in tests | Catches Git edge cases (renames, shallow, partial) |
| Evidence not verdicts | Prevents false confidence; enables classifiers |
| Protocols not base classes | Allows any implementation; easy testing |
| `frozen=True, slots=True` | Immutable, memory-efficient, fast |
| Lazy traversal | Memory-efficient for large repos |
| Deduplication at traversal | Single source of truth for commit identity |