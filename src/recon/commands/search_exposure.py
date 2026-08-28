"""
CLI command for searching historical secret exposure.
"""

import typer
from typing import Annotated
from pathlib import Path

from recon.git import prepare_repository, get_local_remote_refs, get_local_tags
from recon.git.traversal import iter_commit_diffs
from recon.detectors.path import PathDetector
from recon.detectors.content import ContentDetector
from recon.scanner import ExposureScanner
from recon.reporting.terminal import TerminalReporter
from recon.reporting.json import JSONReporter


app = typer.Typer(
    name="search_exposure",
    help="Search Git history for exposed secrets and sensitive patterns.",
)


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
        import subprocess
        local_branches = [
            b for b in subprocess.run(
                ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
                cwd=cwd,
                capture_output=True, text=True
            ).stdout.splitlines() if b
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
    content_detector = ContentDetector.from_patterns(content_patterns) if content_patterns else None
    return path_detector, content_detector


def _build_reporter(format: str):
    """Build reporter instance from format string."""
    if format == "json":
        return JSONReporter()
    return TerminalReporter()


@app.callback(invoke_without_command=True)
def search_exposure(
    ctx: typer.Context,
    path_pattern: Annotated[
        list[str],
        typer.Option(
            "-p",
            "--path-pattern",
            help="Regex pattern to match against file paths (repeatable).",
        ),
    ] = [],
    content_pattern: Annotated[
        list[str],
        typer.Option(
            "-g",
            "--content-pattern",
            help="Regex pattern to match against diff content (repeatable).",
        ),
    ] = [],
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
        list[str],
        typer.Argument(
            help="Specific refs to scan (branches, tags, commits).",
        ),
    ] = [],
    format: Annotated[
        str,
        typer.Option(
            "-f",
            "--format",
            help="Output format: terminal or json.",
            case_sensitive=False,
        ),
    ] = "terminal",
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
    """
    if not path_pattern and not content_pattern:
        typer.echo("Error: At least one of -p/--path-pattern or -g/--content-pattern is required.", err=True)
        raise typer.Exit(1)

    cwd = repo if repo else Path.cwd()

    try:
        # Prepare repository (ensure complete, unshallow)
        prepare_repository(cwd=cwd)

        # Resolve refs to scan
        selected_refs = _resolve_refs(all_refs, interactive, refs, cwd=cwd)
        if not selected_refs:
            typer.echo("No refs to scan.")
            raise typer.Exit(0)

        typer.echo(f"Scanning {len(selected_refs)} ref(s)...")

        # Build detectors
        path_detector, content_detector = _build_detectors(path_pattern, content_pattern)

        # Build scanner
        scanner = ExposureScanner(
            path_detector=path_detector,
            content_detector=content_detector,
        )

        # Traverse commits and scan
        commits = iter_commit_diffs(selected_refs, cwd=cwd)
        findings = list(scanner.scan(commits))

        # Report findings
        reporter = _build_reporter(format)
        reporter.report(findings)

        typer.echo(f"\nDone. Found {len(findings)} match(es).")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)