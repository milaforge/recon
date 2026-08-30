from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from recon.detectors.base import Classifier, Detector
from recon.models.detection import (
    Classification,
    ClassificationResult,
    DetectionContext,
    Evidence,
)
from recon.models.diff import CommitDiff
from recon.models.findings import Finding, LineType


@dataclass(frozen=True, slots=True)
class ExposureScanner:
    """Compose arbitrary detectors and classifiers into normalized findings."""

    detectors: tuple[Detector, ...] = ()
    classifiers: tuple[Classifier, ...] = ()

    def scan(self, commits: Iterable[CommitDiff]) -> Iterator[Finding]:
        for commit_diff in commits:
            for file_diff in commit_diff.files:
                context = DetectionContext(
                    commit=commit_diff.commit,
                    file_diff=file_diff,
                )
                evidence_owners: dict[tuple[LineType, int, str], str] = {}
                for detector in self.detectors:
                    for evidence in detector.detect(context):
                        self._validate_evidence(detector, evidence)
                        identity = self._evidence_identity(evidence)
                        owner = evidence_owners.get(identity) if identity else None
                        if owner is not None and owner != evidence.detector:
                            continue
                        if identity is not None:
                            evidence_owners.setdefault(identity, evidence.detector)
                        yield Finding.from_evidence(
                            context=context,
                            source=evidence,
                            classification=self._classify(evidence, context),
                        )

    def _classify(
        self, evidence: Evidence, context: DetectionContext
    ) -> ClassificationResult:
        fallback: ClassificationResult | None = None
        for classifier in self.classifiers:
            result = classifier.classify(evidence, context)
            if fallback is None:
                fallback = result
            if result.classification is not Classification.UNKNOWN:
                return result
        return fallback or ClassificationResult(
            classification=Classification.UNKNOWN,
            confidence=0.0,
            reason="no classifier made a determination",
        )

    @staticmethod
    def _validate_evidence(detector: Detector, evidence: Evidence) -> None:
        if evidence.detector != detector.name:
            raise ValueError(
                "evidence detector ID must match the detector's stable name"
            )

    @staticmethod
    def _evidence_identity(evidence: Evidence) -> tuple[LineType, int, str] | None:
        """Identify the same candidate emitted by ordered, overlapping detectors."""
        if evidence.line_type is None or evidence.line_number is None:
            return None
        return evidence.line_type, evidence.line_number, evidence.value.casefold()
