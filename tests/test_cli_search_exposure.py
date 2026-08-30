"""Typer-level search command and exit-code tests."""

import json
from pathlib import Path

from typer.testing import CliRunner

from recon.cli import app
from tests.fixtures.git_repo import commit, create_branch, write_file

runner = CliRunner()


def _invoke(repo: Path, *args: str):
    return runner.invoke(app, ["search_exposure", "--repo", str(repo), *args])


def test_no_findings_terminal_exits_cleanly(git_repo: Path) -> None:
    write_file(git_repo, "README.md", "clean\n")
    commit(git_repo, "clean")
    result = _invoke(git_repo, "--generic")
    assert result.exit_code == 0
    assert "Scan summary: 0 finding(s)" in result.stdout


def test_json_stdout_is_parseable_and_secret_triggers_policy(git_repo: Path) -> None:
    raw = "SYNTHETIC-a8B7c6D5e4F3"
    write_file(git_repo, "config.env", f"API_KEY={raw}\n")
    commit(git_repo, "synthetic exposure")
    result = _invoke(git_repo, "--generic", "--format", "json", "HEAD")
    assert result.exit_code == 2
    document = json.loads(result.stdout)
    assert document["schema_version"] == "1.0"
    assert document["summary"]["classifications"]["secret"] == 1
    assert raw not in result.stdout


def test_show_raw_evidence_is_explicit_opt_in(git_repo: Path) -> None:
    raw = "SYNTHETIC-a8B7c6D5e4F3"
    write_file(git_repo, "config.env", f"API_KEY={raw}\\n")
    commit(git_repo, "synthetic exposure")

    terminal = _invoke(git_repo, "--generic", "--show-raw-evidence", "HEAD")
    json_result = _invoke(
        git_repo, "--generic", "--show-raw-evidence", "--format", "json", "HEAD"
    )

    assert terminal.exit_code == 2
    assert json_result.exit_code == 2
    assert raw in terminal.stdout
    assert raw in json_result.stdout


def test_generic_report_defaults_to_actionable_unique_findings(git_repo: Path) -> None:
    private_key = "a5" * 32
    replacement_key = "0" * 63 + "1"
    write_file(
        git_repo,
        "contracts/core.sol",
        "EIP20Interface token = EIP20Interface(underlying);\ntoken = token_;\n",
    )
    write_file(
        git_repo,
        "tronbox.js",
        f"privateKey: process.env.PRIVATE_KEY_MAINNET,\nprivateKey: '{private_key}',\n",
    )
    commit(git_repo, "add configuration")
    write_file(git_repo, "tronbox.js", f"privateKey: '{replacement_key}',\n")
    commit(git_repo, "rotate configuration")

    result = _invoke(git_repo, "--generic", "--show-raw-evidence", "HEAD")

    assert result.exit_code == 2
    assert "Scan summary: 3 finding(s)" in result.stdout
    assert result.stdout.count("ETHEREUM.PRIVATE_KEY MATCH") == 3
    assert "EIP20Interface(underlying)" not in result.stdout
    assert "token = token_" not in result.stdout
    assert "process.env.PRIVATE_KEY_MAINNET" not in result.stdout
    assert private_key in result.stdout
    assert replacement_key in result.stdout

    verbose = _invoke(git_repo, "--generic", "--include-non-actionable", "HEAD")
    assert "REFERENCE" in verbose.stdout
    assert "FALSE_POSITIVE" in verbose.stdout


def test_explicit_ref_and_all_refs_have_distinct_reachability(git_repo: Path) -> None:
    write_file(git_repo, "README.md", "clean\n")
    commit(git_repo, "base")
    create_branch(git_repo, "feature")
    write_file(git_repo, "config.env", "API_KEY=SYNTHETIC-a8B7c6D5e4F3\n")
    commit(git_repo, "feature exposure")

    explicit = _invoke(git_repo, "--generic", "main")
    all_refs = _invoke(git_repo, "--generic", "--all-refs")
    assert explicit.exit_code == 0
    assert all_refs.exit_code == 2


def test_invalid_regex_ref_and_format_are_invocation_errors(git_repo: Path) -> None:
    write_file(git_repo, "README.md", "clean\n")
    commit(git_repo, "base")
    assert _invoke(git_repo, "-g", "[").exit_code == 1
    assert _invoke(git_repo, "-g", "SECRET", "missing-ref").exit_code == 1
    assert _invoke(git_repo, "-g", "SECRET", "--format", "xml").exit_code == 1
