"""CLI tests for current-change and full-history scan scopes."""

import json
from pathlib import Path

from typer.testing import CliRunner

from recon.cli import app
from tests.fixtures.git_repo import commit, write_file

runner = CliRunner()


def _scan(repo: Path, *args: str):
    return runner.invoke(app, ["scan", "--repo", str(repo), "--no-tui", *args])


def test_scan_defaults_to_current_changes(git_repo: Path) -> None:
    write_file(git_repo, "historical.env", "API_KEY=SYNTHETIC-a8B7c6D5e4F3\n")
    commit(git_repo, "historical exposure")

    clean = _scan(git_repo)
    assert clean.exit_code == 0
    assert "Scan summary: 0 finding(s)" in clean.stdout

    write_file(git_repo, "current.env", "API_KEY=SYNTHETIC-z8Y7x6W5v4U3\n")
    current = _scan(git_repo)
    assert current.exit_code == 2
    assert "staged changes" in current.stdout
    assert "current.env" in current.stdout


def test_scan_all_includes_history_and_keeps_json_parseable(git_repo: Path) -> None:
    write_file(git_repo, "historical.env", "API_KEY=SYNTHETIC-a8B7c6D5e4F3\n")
    commit(git_repo, "historical exposure")

    result = _scan(git_repo, "--all", "--format", "json")

    assert result.exit_code == 2
    document = json.loads(result.stdout)
    assert document["summary"]["classifications"]["secret"] == 1
    assert document["findings"][0]["commit_subject"] == "historical exposure"


def test_scan_rejects_tui_with_json(git_repo: Path) -> None:
    result = runner.invoke(
        app,
        ["scan", "--repo", str(git_repo), "--tui", "--format", "json"],
    )
    assert result.exit_code == 1
    assert "--tui cannot be combined" in result.stderr
