"""
Detector protocol — the abstraction that lets ExposureScanner compose
arbitrary detectors without knowing their concrete types.
"""

from typing import Protocol, TypeVar

from recon.models.diff import FileChange
from recon.models.findings import PathMatch, ContentMatch


T = TypeVar("T", covariant=True)


class Detector(Protocol[T]):
    """
    A detector consumes some input and returns matches.

    The scanner only knows about the `detect` method. Concrete detectors
    declare what input they accept via the type parameter.
    """

    def detect(self, value: T) -> tuple:
        ...


class PathDetector(Detector[FileChange], Protocol):
    """Detects matches against file paths in a change."""

    def detect(self, change: FileChange) -> tuple[PathMatch, ...]:
        ...


class ContentDetector(Detector[str], Protocol):
    """Detects matches against diff content (patch text)."""

    def detect(self, patch: str) -> tuple[ContentMatch, ...]:
        ...