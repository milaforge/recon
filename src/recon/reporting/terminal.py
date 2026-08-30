"""
Terminal reporter for findings.
"""

import sys
from pathlib import Path

from recon.models.findings import Finding

from .json import _display_evidence, _remediation, _summary
from .navigation import navigation_targets


class TerminalReporter:
    """Human-readable terminal output for findings."""

    def __init__(
        self,
        *,
        show_raw_evidence: bool = False,
        repository_root: Path | None = None,
        github_repository: str | None = None,
        enable_hyperlinks: bool | None = None,
    ) -> None:
        self._show_raw_evidence = show_raw_evidence
        self._repository_root = repository_root
        self._github_repository = github_repository
        self._enable_hyperlinks = (
            sys.stdout.isatty() if enable_hyperlinks is None else enable_hyperlinks
        )

    def report(self, findings: list[Finding]) -> None:
        summary = _summary(findings)
        counts = summary["classifications"]
        assert isinstance(counts, dict)
        print(
            f"Scan summary: {summary['total']} finding(s) — "
            f"SECRET {counts['secret']}, REFERENCE {counts['reference']}, "
            f"FALSE_POSITIVE {counts['false_positive']}, UNKNOWN {counts['unknown']}"
        )
        if not findings:
            return
        print()

        for i, finding in enumerate(findings, 1):
            self._print_finding(i, finding)

    def _print_finding(self, index: int, finding: Finding) -> None:
        targets = navigation_targets(
            finding,
            repository_root=self._repository_root,
            github_repository=self._github_repository,
        )
        print(f"[{index}] {finding.detector.upper()} MATCH")
        commit = f"{finding.commit_sha[:12]} ({finding.commit_subject})"
        print(f"    Commit:     {_link(targets.commit_url, commit, self._enable_hyperlinks)}")
        print(f"    Author:     {finding.author}")
        print(f"    Timestamp:  {finding.timestamp}")
        print(f"    Pattern:    {finding.pattern}")
        print(
            "    Evidence:   "
            f"{_display_evidence(finding, show_raw_evidence=self._show_raw_evidence)}"
        )
        print(
            f"    Result:     {finding.classification.value.upper()} "
            f"({finding.classification_result.confidence:.0%} confidence)"
        )
        print(f"    Reason:     {finding.classification_result.reason}")
        print(f"    Action:     {_remediation(finding)}")
        if finding.line_type:
            location = finding.line_type.value
            if finding.line_number is not None:
                location = f"{location}, line {finding.line_number}"
            print(f"    Diff line:  {location}")
        path: str | None = None
        if finding.old_path or finding.new_path:
            if (
                finding.old_path
                and finding.new_path
                and finding.old_path != finding.new_path
            ):
                path = f"{finding.old_path} -> {finding.new_path}"
            elif finding.old_path:
                path = f"{finding.old_path} (deleted)"
            elif finding.new_path:
                path = f"{finding.new_path} (added)"
        if path is not None:
            print(f"    Path:       {_link(targets.path_url, path, self._enable_hyperlinks)}")
        print()


def _link(url: str | None, label: str, enabled: bool) -> str:
    """Return an OSC 8 hyperlink or a copyable URL for redirected output."""
    if url is None:
        return label
    if not enabled:
        return f"{label} ({url})"
    return f"\x1b]8;;{url}\x1b\\{label}\x1b]8;;\x1b\\"
