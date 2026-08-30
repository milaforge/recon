"""
JSON reporter for findings.
"""

import json
from datetime import datetime

from recon.detectors.generic import redact_secret
from recon.models.findings import Finding


class JSONReporter:
    """Machine-readable JSON output for findings."""

    SCHEMA_VERSION = "1.0"

    def __init__(self, *, show_raw_evidence: bool = False) -> None:
        self._show_raw_evidence = show_raw_evidence

    def report(self, findings: list[Finding]) -> None:
        output = {
            "schema_version": self.SCHEMA_VERSION,
            "summary": _summary(findings),
            "findings": [self._finding_to_dict(f) for f in findings],
        }
        print(json.dumps(output, indent=2, default=self._json_serializer))

    def _finding_to_dict(self, finding: Finding) -> dict[str, object]:
        path, change_type = _path_and_change_type(finding)
        return {
            "detector": finding.detector,
            "commit_sha": finding.commit_sha,
            "commit_subject": finding.commit_subject,
            "author": finding.author,
            "timestamp": finding.timestamp.isoformat()
            if isinstance(finding.timestamp, datetime)
            else finding.timestamp,
            "old_path": finding.old_path,
            "new_path": finding.new_path,
            "path": path,
            "change_type": change_type,
            "pattern": finding.pattern,
            "evidence": _display_evidence(
                finding, show_raw_evidence=self._show_raw_evidence
            ),
            "evidence_redacted": not self._show_raw_evidence
            and finding.source.redacted_value != finding.source.value,
            "line_type": finding.line_type.value if finding.line_type else None,
            "line_number": finding.line_number,
            "classification": finding.classification.value,
            "confidence": finding.classification_result.confidence,
            "classification_reason": finding.classification_result.reason,
            "detection_reason": finding.source.reason,
            "remediation": _remediation(finding),
        }

    def _json_serializer(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _summary(findings: list[Finding]) -> dict[str, object]:
    classifications = {
        name: 0 for name in ("secret", "reference", "false_positive", "unknown")
    }
    for finding in findings:
        classifications[finding.classification.value] += 1
    return {"total": len(findings), "classifications": classifications}


def _display_evidence(finding: Finding, *, show_raw_evidence: bool = False) -> str:
    """Return raw evidence only when the caller has explicitly opted in."""
    if show_raw_evidence:
        return finding.source.source_line or finding.source.value

    # Defensively redact raw content emitted by compatibility detectors.
    if finding.source.kind == "content":
        return redact_secret(finding.source.value)
    return finding.evidence


def _remediation(finding: Finding) -> str:
    if finding.classification.value == "secret":
        return "Rotate the credential, then remove it from reachable Git history."
    if finding.classification.value == "unknown":
        return "Review the redacted candidate and its commit context."
    return "No credential rotation is indicated; review or suppress if appropriate."


def _path_and_change_type(finding: Finding) -> tuple[str | None, str | None]:
    """Return an unambiguous display path and Git change type."""
    old_path, new_path = finding.old_path, finding.new_path
    if old_path and new_path:
        if old_path != new_path:
            return f"{old_path} -> {new_path}", "renamed"
        return new_path, "modified"
    if new_path:
        return new_path, "added"
    if old_path:
        return old_path, "deleted"
    return None, None
