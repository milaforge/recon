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

    def report(self, findings: list[Finding]) -> None:
        output = {
            "schema_version": self.SCHEMA_VERSION,
            "summary": _summary(findings),
            "findings": [self._finding_to_dict(f) for f in findings],
        }
        print(json.dumps(output, indent=2, default=self._json_serializer))

    def _finding_to_dict(self, finding: Finding) -> dict[str, object]:
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
            "pattern": finding.pattern,
            "evidence": _display_evidence(finding),
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


def _display_evidence(finding: Finding) -> str:
    """Defensively redact raw content emitted by compatibility detectors."""
    if finding.source.kind == "content":
        return redact_secret(finding.source.value)
    return finding.evidence


def _remediation(finding: Finding) -> str:
    if finding.classification.value == "secret":
        return "Rotate the credential, then remove it from reachable Git history."
    if finding.classification.value == "unknown":
        return "Review the redacted candidate and its commit context."
    return "No credential rotation is indicated; review or suppress if appropriate."
