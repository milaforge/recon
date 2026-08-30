"""
CLI command for searching historical secret exposure.
"""

import re
from pathlib import Path
from typing import Annotated

import typer

from recon.detectors.compat import RegexContentDetector, RegexPathDetector
from recon.detectors.content import ContentDetector
from recon.detectors.ethereum import (
    EthereumPrivateKeyClassifier,
    EthereumPrivateKeyDetector,
)
from recon.detectors.generic import GenericSecretClassifier, GenericSecretDetector
from recon.detectors.path import PathDetector
from recon.git import (
    GitError,
    IncompleteRepositoryError,
    get_local_remote_refs,
    get_local_tags,
    get_remotes,
    prepare_repository,
    repository_root,
    run_git,
)
from recon.git.traversal import iter_commit_diffs
from recon.reporting.json import JSONReporter
from recon.reporting.navigation import github_repository_url
from recon.reporting.terminal import TerminalReporter
from recon.scanner import ExposureScanner

app = typer.Typer(
    name="search_exposure",
    help="Search Git history for exposed secrets and sensitive patterns.",
)

EXIT_CLEAN = 0
EXIT_INVALID = 1
EXIT_POLICY_FINDINGS = 2
EXIT_INCOMPLETE = 3


def _resolve_refs(
    all_refs: bool,
    interactive: bool,
    refs: list[str],
    cwd: Path | None = None,
) -> list[str]:
    """Resolve which refs to scan."""
    if refs:
        return refs

    if all_refs:
        # All local branches, remote-tracking branches, and tags
        local_branches = [
            branch
            for branch in run_git(
                "for-each-ref", "--format=%(refname:short)", "refs/heads/", cwd=cwd
            ).splitlines()
            if branch
        ]
        remote_refs = get_local_remote_refs(cwd=cwd)
        tags = get_local_tags(cwd=cwd)
        return local_branches + remote_refs + tags

    if interactive:
        # For now, default to HEAD
        typer.echo("Interactive ref selection not yet implemented. Using HEAD.")
        return ["HEAD"]

    # Default: current HEAD
    return ["HEAD"]


def _build_detectors(
    path_patterns: list[str],
    content_patterns: list[str],
) -> tuple[PathDetector | None, ContentDetector | None]:
    """Build detector instances from pattern lists."""
    path_detector = PathDetector.from_patterns(path_patterns) if path_patterns else None
    content_detector = (
        ContentDetector.from_patterns(content_patterns) if content_patterns else None
    )
    return path_detector, content_detector


def _build_reporter(
    format: str,
    *,
    show_raw_evidence: bool,
    repository_root: Path | None = None,
    github_repository: str | None = None,
):
    """Build reporter instance from format string."""
    if format == "json":
        return JSONReporter(show_raw_evidence=show_raw_evidence)
    return TerminalReporter(
        show_raw_evidence=show_raw_evidence,
        repository_root=repository_root,
        github_repository=github_repository,
    )


def _github_repository(cwd: Path) -> str | None:
    """Find the first configured GitHub remote without contacting the network."""
    remotes = get_remotes(cwd=cwd)
    ordered_remotes = sorted(remotes, key=lambda remote: remote != "origin")
    for remote in ordered_remotes:
        remote_url = run_git("remote", "get-url", remote, cwd=cwd).strip()
        github_url = github_repository_url(remote_url)
        if github_url:
            return github_url
    return None


@app.callback(invoke_without_command=True)
def search_exposure(
    ctx: typer.Context,
    path_pattern: Annotated[
        list[str] | None,
        typer.Option(
            "-p",
            "--path-pattern",
            help="Regex pattern to match against file paths (repeatable).",
        ),
    ] = None,
    content_pattern: Annotated[
        list[str] | None,
        typer.Option(
            "-g",
            "--content-pattern",
            help="Regex pattern to match against diff content (repeatable).",
        ),
    ] = None,
    generic: Annotated[
        bool,
        typer.Option(
            "--generic",
            help="Use the built-in generic credential detector and classifier.",
        ),
    ] = False,
    all_refs: Annotated[
        bool,
        typer.Option(
            "-a",
            "--all-refs",
            help="Scan all local branches, remote-tracking branches, and tags.",
        ),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option(
            "-i",
            "--interactive",
            help="Interactively select refs to scan.",
        ),
    ] = False,
    refs: Annotated[
        list[str] | None,
        typer.Argument(
            help="Specific refs to scan (branches, tags, commits).",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "-f",
            "--format",
            help="Output format: terminal or json.",
            case_sensitive=False,
        ),
    ] = "terminal",
    show_raw_evidence: Annotated[
        bool,
        typer.Option(
            "--show-raw-evidence",
            help="Include unredacted matched content in the report. Handle output as sensitive.",
        ),
    ] = False,
    include_non_actionable: Annotated[
        bool,
        typer.Option(
            "--include-non-actionable",
            help="Also report references and classified false positives.",
        ),
    ] = False,
    repo: Annotated[
        Path | None,
        typer.Option(
            "--repo",
            help="Path to Git repository (default: current directory).",
        ),
    ] = None,
) -> None:
    """
    Search Git history for exposed secrets and sensitive patterns.

    Examples:
        recon search_exposure -g 'PRIVATE_KEY='
        recon search_exposure -p '\\.env$' -g 'API_KEY='
        recon search_exposure -a -p '\\.env$' -g 'PRIVATE_KEY=' -g 'MNEMONIC'
        recon search_exposure --generic --show-raw-evidence
    """
    path_patterns = path_pattern or []
    content_patterns = content_pattern or []
    selected_ref_args = refs or []

    format = format.lower()
    if format not in {"terminal", "json"}:
        typer.echo("Error: --format must be 'terminal' or 'json'.", err=True)
        raise typer.Exit(EXIT_INVALID)

    if not path_patterns and not content_patterns and not generic:
        typer.echo(
            "Error: Use --generic or provide a path/content pattern.",
            err=True,
        )
        raise typer.Exit(1)

    cwd = repo if repo else Path.cwd()

    try:
        # Prepare repository (ensure complete, unshallow)
        prepare_repository(cwd=cwd)

        # Resolve refs to scan
        selected_refs = _resolve_refs(all_refs, interactive, selected_ref_args, cwd=cwd)
        if not selected_refs:
            typer.echo("No refs to scan.")
            raise typer.Exit(0)

        typer.echo(
            f"Scanning {len(selected_refs)} ref(s)...", err=format.lower() == "json"
        )

        # Build detectors
        path_detector, content_detector = _build_detectors(
            path_patterns, content_patterns
        )

        # Build scanner
        detectors = []
        if path_detector is not None:
            detectors.append(RegexPathDetector(path_detector))
        if content_detector is not None:
            detectors.append(RegexContentDetector(content_detector))
        classifiers = []
        if generic:
            detectors.extend((EthereumPrivateKeyDetector(), GenericSecretDetector()))
            classifiers.extend(
                (EthereumPrivateKeyClassifier(), GenericSecretClassifier())
            )
        scanner = ExposureScanner(
            detectors=tuple(detectors), classifiers=tuple(classifiers)
        )

        # Traverse commits and scan
        commits = iter_commit_diffs(selected_refs, cwd=cwd)
        findings = list(scanner.scan(commits))
        reported_findings = (
            findings
            if include_non_actionable
            else [
                finding
                for finding in findings
                if finding.classification.value in {"secret", "unknown"}
            ]
        )

        # Report findings
        root = repository_root(cwd=cwd)
        reporter = _build_reporter(
            format,
            show_raw_evidence=show_raw_evidence,
            repository_root=root if format == "terminal" else None,
            github_repository=_github_repository(cwd) if format == "terminal" else None,
        )
        reporter.report(reported_findings)

        policy_findings = [
            finding for finding in findings if finding.classification.value == "secret"
        ]
        typer.echo(
            f"Done. Reported {len(reported_findings)} finding(s)"
            f"; suppressed {len(findings) - len(reported_findings)} non-actionable candidate(s).",
            err=format.lower() == "json",
        )
        if policy_findings:
            raise typer.Exit(EXIT_POLICY_FINDINGS)

    except IncompleteRepositoryError as e:
        typer.echo(f"Incomplete scan: {e}", err=True)
        raise typer.Exit(EXIT_INCOMPLETE)
    except (GitError, OSError, re.error) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(EXIT_INVALID)
