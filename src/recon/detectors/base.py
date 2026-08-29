"""
Detector protocol — the abstraction that lets ExposureScanner compose
arbitrary detectors without knowing their concrete types.
"""

from collections.abc import Iterable
from typing import Protocol

from recon.models.detection import ClassificationResult, DetectionContext, Evidence


class Detector(Protocol):
    """
    A detector consumes a complete, immutable context and returns evidence.
    """

    name: str

    def detect(self, context: DetectionContext, /) -> Iterable[Evidence]: ...


class Classifier(Protocol):
    """Classifies one evidence item in its original detection context."""

    def classify(
        self, evidence: Evidence, context: DetectionContext, /
    ) -> ClassificationResult: ...
