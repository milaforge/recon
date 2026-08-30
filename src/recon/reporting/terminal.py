"""
Terminal reporter for findings.
"""

import sys
from pathlib import Path

from recon.models.findings import Finding

from .json import _display_evidence, _path_and_change_type, _remediation, _summary
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
        print("RECON SCAN REPORT")
        print("=" * 72)
        print(f"Scan summary: {summary['total']} finding(s)")
        print(
            "  "
            f"Secrets: {counts['secret']}  |  Unknown: {counts['unknown']}  |  "
            f"References: {counts['reference']}  |  False positives: {counts['false_positive']}"
        )
        if self._show_raw_evidence:
            print("  WARNING: Raw evidence is visible; treat this output as sensitive.")
        if not findings:
            print("\nNo reportable exposures found.")
            return
        print()

        for i, finding in enumerate(findings, 1):
            self._print_finding(i, len(findings), finding)

    def _print_finding(self, index: int, total: int, finding: Finding) -> None:
        targets = navigation_targets(
            finding,
            repository_root=self._repository_root,
            github_repository=self._github_repository,
        )
        classification = finding.classification.value.upper()
        print("-" * 72)
        print(f"[{index}/{total}] {classification} · {finding.detector.upper()} MATCH")
        print()
        print("  LOCATION")
        path, change_type = _path_and_change_type(finding)
        if path is not None:
            linked_path = _link(targets.path_url, path, self._enable_hyperlinks)
            line_suffix = f":{finding.line_number}" if finding.line_number else ""
            print(f"    Path:       {linked_path}{line_suffix}")
        if finding.line_type:
            print(
                f"    Diff:       {finding.line_type.value} in {change_type or 'unknown'} file"
            )

        print("\n  COMMIT")
        commit = f"{finding.commit_sha[:12]} ({finding.commit_subject})"
        print(
            f"    Commit:     {_link(targets.commit_url, commit, self._enable_hyperlinks)}"
        )
        print(f"    Author:     {finding.author}")
        print(f"    Timestamp:  {finding.timestamp}")
        print("\n  EVIDENCE")
        if finding.pattern:
            print(f"    Pattern:    {finding.pattern}")
        print(
            "    Evidence:   "
            f"{_display_evidence(finding, show_raw_evidence=self._show_raw_evidence)}"
        )
        print("\n  ASSESSMENT")
        print(
            f"    Result:     {classification} "
            f"({finding.classification_result.confidence:.0%} confidence)"
        )
        print(f"    Reason:     {finding.classification_result.reason}")
        print(f"    Action:     {_remediation(finding)}")
        print()


def _link(url: str | None, label: str, enabled: bool) -> str:
    """Return an OSC 8 hyperlink or a copyable URL for redirected output."""
    if url is None:
        return label
    if not enabled:
        return f"{label} ({url})"
    return f"\x1b]8;;{url}\x1b\\{label}\x1b]8;;\x1b\\"
