"""
Terminal reporter for findings.
"""

from recon.models.findings import Finding


class TerminalReporter:
    """Human-readable terminal output for findings."""

    def report(self, findings: list[Finding]) -> None:
        if not findings:
            print("No matches found.")
            return

        print(f"\n{'=' * 80}")
        print(f"FOUND {len(findings)} MATCH(ES)")
        print(f"{'=' * 80}\n")

        for i, finding in enumerate(findings, 1):
            self._print_finding(i, finding)

    def _print_finding(self, index: int, finding: Finding) -> None:
        print(f"[{index}] {finding.detector.upper()} MATCH")
        print(f"    Commit:     {finding.commit_sha[:12]} ({finding.commit_subject})")
        print(f"    Author:     {finding.author}")
        print(f"    Timestamp:  {finding.timestamp}")
        print(f"    Pattern:    {finding.pattern}")
        print(f"    Evidence:   {finding.evidence}")
        if finding.line_type:
            location = finding.line_type.value
            if finding.line_number is not None:
                location = f"{location}, line {finding.line_number}"
            print(f"    Diff line:  {location}")
        if finding.old_path or finding.new_path:
            if finding.old_path and finding.new_path and finding.old_path != finding.new_path:
                print(f"    Path:       {finding.old_path} -> {finding.new_path}")
            elif finding.old_path:
                print(f"    Path:       {finding.old_path} (deleted)")
            elif finding.new_path:
                print(f"    Path:       {finding.new_path} (added)")
        print()
