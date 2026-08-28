# Contributing to Recon

## Quick Start: Adding a New Detector

### 1. Create Detector Module

```bash
# src/recon/detectors/my_detector.py
```

Use the template from `QUICK_REFERENCE.md` — implement `PathDetector` or `ContentDetector` protocol.

### 2. Export Detector

```python
# src/recon/detectors/__init__.py
from .my_detector import MyPathDetector, MyContentDetector

__all__ = [
    "PathDetector",
    "ContentDetector",
    "MyPathDetector",
    "MyContentDetector",
]
```

### 3. Add CLI Option

```python
# src/recon/commands/search_exposure.py
my_pattern: Annotated[
    list[str],
    typer.Option("-m", "--my-pattern", help="My custom pattern (repeatable)."),
] = [],
```

Update `_build_detectors()` to instantiate your detector.

### 4. Wire Into Scanner

```python
# src/recon/scanner.py
@dataclass(frozen=True, slots=True)
class ExposureScanner:
    my_detector: MyContentDetector | None = field(default=None, kw_only=True)

    def _scan_commit(self, commit_diff: CommitDiff) -> Iterator[Finding]:
        # ... existing detectors ...
        if self.my_detector:
            for match in self.my_detector.detect(file_diff.patch):
                yield Finding.from_content_match(...)
```

### 5. Write Tests (Use Existing Fixtures)

| Layer | File | Fixture |
|-------|------|---------|
| Unit | `tests/test_my_detector.py` | Pure functions, no Git |
| Integration | `tests/test_scanner.py` | `git_repo` fixture |
| Semantic | `tests/test_historical_semantics.py` | `build_linear_history`, `build_branch_with_secret` |

**Never create test repos from scratch** — use `tests/fixtures/git_repo.py` builders.

### 6. Run Checks

```bash
uv run pytest
uv run basedpyright src/
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

---

## Development Workflow

### Prerequisites

- Python 3.13+
- `uv` package manager
- Git

### Setup

```bash
git clone <repo>
cd recon
uv sync
uv run pytest  # Verify tests pass
```

### Making Changes

1. **Create feature branch**: `git checkout -b feat/my-detector`
2. **Follow patterns** in `AGENT_GUIDE.md` and `QUICK_REFERENCE.md`
3. **Write tests first** (TDD) — use existing fixtures
4. **Run checks** before commit
5. **Submit PR**

### Code Style

- `frozen=True, slots=True` dataclasses
- Relative imports within `src/recon/`
- Type hints on all public functions
- Protocols over base classes
- Evidence, not verdicts (detectors return matches)

---

## Test Guidelines

### Use Scenario Builders

```python
from tests.fixtures.git_repo import (
    build_linear_history,      # Secret lifecycle
    build_branch_with_secret,  # Branch isolation
    build_shared_commit,       # Deduplication
)
```

### Test Layers

| Test File | Purpose | Git? |
|-----------|---------|------|
| `test_*_detector.py` | Pure detector logic | No |
| `test_scanner.py` | End-to-end pipeline | Yes |
| `test_historical_semantics.py` | Real-world scenarios | Yes |

### Semantic Test Patterns

```python
# Secret lifecycle
def test_my_secret_lifecycle(self, git_repo):
    build_linear_history(git_repo)
    findings = scan_repo(git_repo, my_patterns=[r"MY_SECRET="])
    assert len(findings) >= 4

# Branch isolation
def test_my_branch_isolation(self, git_repo):
    main_sha, feature_sha = build_branch_with_secret(git_repo)
    findings_main = scan_repo(git_repo, my_patterns=[r"MY_SECRET="], refs=["main"])
    assert len(findings_main) == 0
```

---

## Architecture Principles

1. **Real Git in tests** — No mocks, catches edge cases
2. **Evidence over verdicts** — Detectors return matches; classification is separate
3. **Lazy, deduplicated traversal** — Memory efficient, correct for merges
4. **Protocols not inheritance** — Easy to test, extend, replace
5. **No new abstractions** — Extend existing patterns

---

## Adding a New CLI Command

1. Create `src/recon/commands/my_command.py`
2. Reuse shared logic from `commands/common.py` (or create it)
3. Register in `src/recon/cli.py`
4. Follow existing command patterns

---

## Documentation

- Update `AGENTS.md` for structural changes
- Update `docs/architecture/` for architectural changes
- Update `docs/mission/` for product direction changes

---

## Questions?

- Check `AGENT_GUIDE.md` for detailed patterns
- Check `QUICK_REFERENCE.md` for copy-paste templates
- Check `docs/architecture/` for system design