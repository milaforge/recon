"""Scan current Git changes, with optional full-history coverage."""

import re
import sys
from itertools import chain
from pathlib import Path
from typing import Annotated

import typer

from recon.commands.search_exposure import (
    EXIT_INCOMPLETE,
    EXIT_INVALID,
    EXIT_POLICY_FINDINGS,
    _github_repository,
    _resolve_refs,
)
from recon.detectors.ethereum import (
    EthereumPrivateKeyClassifier,
    EthereumPrivateKeyDetector,
)
from recon.detectors.generic import GenericSecretClassifier, GenericSecretDetector
from recon.git import (
    GitError,
    IncompleteRepositoryError,
    fetch_all,
    get_working_tree_diffs,
    prepare_repository,
    repository_root,
)
from recon.git.traversal import iter_commit_diffs
from recon.reporting.interactive import InteractiveReporter
from recon.reporting.json import JSONReporter
from recon.reporting.terminal import TerminalReporter
from recon.scanner import ExposureScanner


def scan(
    all_history: Annotated[
        bool,
        typer.Option(
            "-a",
            "--all",
            help="Fetch remotes and scan current changes plus all reachable history.",
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option("-f", "--format", help="Output format: terminal or json."),
    ] = "terminal",
    tui: Annotated[
        bool | None,
        typer.Option(
            "--tui/--no-tui",
            help="Enable or disable the interactive report (default: enabled in a TTY).",
        ),
    ] = None,
    repo: Annotated[
        Path | None,
        typer.Option(
            "--repo", help="Path to Git repository (default: current directory)."
        ),
    ] = None,
) -> None:
    """Scan staged, unstaged, and non-ignored untracked changes for secrets."""
    output_format = format.lower()
    if output_format not in {"terminal", "json"}:
        typer.echo("Error: --format must be 'terminal' or 'json'.", err=True)
        raise typer.Exit(EXIT_INVALID)

    tui_enabled = output_format == "terminal" and (
        tui if tui is not None else sys.stdin.isatty() and sys.stdout.isatty()
    )
    if tui and output_format == "json":
        typer.echo("Error: --tui cannot be combined with --format json.", err=True)
        raise typer.Exit(EXIT_INVALID)

    cwd = repo or Path.cwd()
    try:
        prepare_repository(cwd=cwd)
        current = get_working_tree_diffs(cwd=cwd)
        commits = iter(current)
        scanned_refs = 0
        if all_history:
            fetch_all(cwd=cwd)
            refs = _resolve_refs(True, False, [], cwd=cwd)
            scanned_refs = len(refs)
            commits = chain(commits, iter_commit_diffs(refs, cwd=cwd))

        detectors = []
        detectors.extend((EthereumPrivateKeyDetector(), GenericSecretDetector()))
        classifiers = []
        classifiers.extend((EthereumPrivateKeyClassifier(), GenericSecretClassifier()))
        scanner = ExposureScanner(tuple(detectors), tuple(classifiers))
        findings = list(scanner.scan(commits))
        reported = (
            findings
            if tui_enabled
            else [
                finding
                for finding in findings
                if finding.classification.value in {"secret", "unknown"}
            ]
        )

        root = repository_root(cwd=cwd)
        if output_format == "json":
            reporter = JSONReporter()
        elif tui_enabled:
            reporter = InteractiveReporter(
                repository_root=root,
                github_repository=_github_repository(cwd),
            )
        else:
            reporter = TerminalReporter(
                repository_root=root,
                github_repository=_github_repository(cwd),
            )
        reporter.report(reported)

        scope = "current changes"
        if all_history:
            scope += f" and all history across {scanned_refs} ref(s)"
        typer.echo(f"Done. Scanned {scope}.", err=output_format == "json")
        if any(f.classification.value == "secret" for f in findings):
            raise typer.Exit(EXIT_POLICY_FINDINGS)
    except IncompleteRepositoryError as exc:
        typer.echo(f"Incomplete scan: {exc}", err=True)
        raise typer.Exit(EXIT_INCOMPLETE)
    except (GitError, OSError, re.error) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(EXIT_INVALID)
