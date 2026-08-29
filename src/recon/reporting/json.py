"""
JSON reporter for findings.
"""

import json
from datetime import datetime

from recon.models.findings import Finding


class JSONReporter:
    """Machine-readable JSON output for findings."""

    def report(self, findings: list[Finding]) -> None:
        output = [self._finding_to_dict(f) for f in findings]
        print(json.dumps(output, indent=2, default=self._json_serializer))

    def _finding_to_dict(self, finding: Finding) -> dict:
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
            "evidence": finding.evidence,
            "line_type": finding.line_type.value if finding.line_type else None,
            "line_number": finding.line_number,
            "classification": finding.classification.value,
            "confidence": finding.classification_result.confidence,
            "classification_reason": finding.classification_result.reason,
            "detection_reason": finding.source.reason,
        }

    def _json_serializer(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
