"""Tests for the detector -> evidence -> classification -> finding contract."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from recon.models import (
    ChangeStatus,
    Classification,
    ClassificationResult,
    Commit,
    CommitDiff,
    DetectionContext,
    Evidence,
    FileChange,
    FileDiff,
    LineType,
)
from recon.scanner import ExposureScanner


def _commit_diff() -> CommitDiff:
    file_diff = FileDiff(
        change=FileChange(ChangeStatus.ADDED, new_path="synthetic.env"),
        patch="+TOKEN=synthetic-value\n",
    )
    commit = Commit(
        sha="a" * 40,
        author="Test User <test@example.com>",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        subject="synthetic evidence",
        files=(file_diff,),
    )
    return CommitDiff(commit=commit, files=(file_diff,))


class TwoEvidenceDetector:
    name = "test.multiple"

    def detect(self, context: DetectionContext) -> tuple[Evidence, ...]:
        del context
        return (
            Evidence(
                detector=self.name,
                kind="assignment",
                value="synthetic-value",
                redacted_value="synthetic…[15]",
                reason="synthetic candidate",
                line_type=LineType.ADDITION,
                line_number=1,
            ),
            Evidence(
                detector=self.name,
                kind="path",
                value="synthetic.env",
                redacted_value="synthetic.env",
                reason="synthetic path",
            ),
        )


class UnknownClassifier:
    def classify(
        self, evidence: Evidence, context: DetectionContext
    ) -> ClassificationResult:
        del evidence, context
        return ClassificationResult(Classification.UNKNOWN, 0.2, "insufficient data")


class ReferenceClassifier:
    def classify(
        self, evidence: Evidence, context: DetectionContext
    ) -> ClassificationResult:
        del evidence, context
        return ClassificationResult(Classification.REFERENCE, 0.9, "known reference")


def test_contract_models_are_immutable() -> None:
    commit_diff = _commit_diff()
    context = DetectionContext(commit_diff.commit, commit_diff.files[0])
    evidence = TwoEvidenceDetector().detect(context)[0]

    with pytest.raises(FrozenInstanceError):
        evidence.reason = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        context.commit = commit_diff.commit  # type: ignore[misc]


def test_scanner_traces_each_evidence_through_classifier_precedence() -> None:
    scanner = ExposureScanner(
        detectors=(TwoEvidenceDetector(),),
        classifiers=(UnknownClassifier(), ReferenceClassifier()),
    )

    findings = list(scanner.scan((_commit_diff(),)))

    assert len(findings) == 2
    assert all(finding.detector == "test.multiple" for finding in findings)
    assert all(
        finding.classification is Classification.REFERENCE for finding in findings
    )
    assert findings[0].source.line_type is LineType.ADDITION
    assert findings[0].source.line_number == 1
    assert findings[0].evidence == "synthetic…[15]"
    assert findings[0].source.value == "synthetic-value"


def test_scanner_defaults_to_unknown_without_classifiers() -> None:
    finding = next(
        ExposureScanner(detectors=(TwoEvidenceDetector(),)).scan((_commit_diff(),))
    )

    assert finding.classification is Classification.UNKNOWN
    assert finding.classification_result.confidence == 0.0


def test_detector_id_must_be_stable() -> None:
    class InvalidDetector(TwoEvidenceDetector):
        name = "expected.id"

        def detect(self, context: DetectionContext) -> tuple[Evidence, ...]:
            evidence = super().detect(context)[0]
            return (
                Evidence(
                    detector="different.id",
                    kind=evidence.kind,
                    value=evidence.value,
                    redacted_value=evidence.redacted_value,
                    reason=evidence.reason,
                ),
            )

    with pytest.raises(ValueError, match="stable name"):
        list(ExposureScanner(detectors=(InvalidDetector(),)).scan((_commit_diff(),)))


def test_classification_confidence_is_bounded() -> None:
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        ClassificationResult(Classification.SECRET, 1.1, "invalid")
