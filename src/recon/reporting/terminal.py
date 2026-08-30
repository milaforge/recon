"""
Terminal reporter for findings.
"""

from recon.models.findings import Finding

from .json import _display_evidence, _remediation, _summary


class TerminalReporter:
    """Human-readable terminal output for findings."""

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
        print(f"[{index}] {finding.detector.upper()} MATCH")
        print(f"    Commit:     {finding.commit_sha[:12]} ({finding.commit_subject})")
        print(f"    Author:     {finding.author}")
        print(f"    Timestamp:  {finding.timestamp}")
        print(f"    Pattern:    {finding.pattern}")
        print(f"    Evidence:   {_display_evidence(finding)}")
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
        if finding.old_path or finding.new_path:
            if (
                finding.old_path
                and finding.new_path
                and finding.old_path != finding.new_path
            ):
                print(f"    Path:       {finding.old_path} -> {finding.new_path}")
            elif finding.old_path:
                print(f"    Path:       {finding.old_path} (deleted)")
            elif finding.new_path:
                print(f"    Path:       {finding.new_path} (added)")
        print()
