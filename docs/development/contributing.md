# Contributor development guide

This guide covers the mechanics of changing Recon. The [architecture index](../architecture/README.md) explains how the system is structured.

## Set up development

Prerequisites: Python 3.13+, `uv`, and Git.

```bash
git clone <repo>
cd recon
uv sync
uv run pytest
```

Create a focused feature branch, write tests for the behavior, then run the checks before opening a pull request:

```bash
uv run pytest
uv run basedpyright src/
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Add a detector

1. Add `src/recon/detectors/<name>.py` implementing `PathDetector` for paths, `ContentDetector` for diff content, or both.
2. Export it from `src/recon/detectors/__init__.py`.
3. Add the detector’s pattern option and construction to `src/recon/commands/search_exposure.py`.
4. Pass it through `src/recon/scanner.py` and emit the matching evidence model.
5. Add unit coverage, then scanner and semantic coverage where Git history behavior matters.

Detectors return evidence (`PathMatch` or `ContentMatch`), not classifications. Follow the existing implementations in `src/recon/detectors/` and the [detector architecture](../architecture/detectors.md).

## Add a CLI command

1. Create `src/recon/commands/<name>.py`.
2. Reuse existing repository, scanning, and reporting helpers.
3. Register the command in `src/recon/cli.py`.
4. Test command behavior through the existing CLI and integration test patterns.

## Add tests

- **Unit:** `tests/test_<name>_detector.py`; pure detector behavior, no Git.
- **Integration:** `tests/test_scanner.py`; use the `git_repo` fixture.
- **Semantic:** `tests/test_historical_semantics.py`; exercise lifecycles, branches, merges, and deduplication.

Use the builders in `tests/fixtures/git_repo.py`. Do not create ad-hoc test repositories.

For broader implementation rules and repository conventions, see [AGENT_GUIDE.md](../../AGENT_GUIDE.md). The canonical machine-readable architecture and operating instructions are in [AGENTS.md](../../AGENTS.md).
