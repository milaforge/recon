"""
Detector protocol — the abstraction that lets ExposureScanner compose
arbitrary detectors without knowing their concrete types.
"""

from typing import Protocol, TypeVar

from recon.models.diff import FileChange
from recon.models.findings import ContentMatch, PathMatch

T_contra = TypeVar("T_contra", contravariant=True)


class Detector(Protocol[T_contra]):
    """
    A detector consumes some input and returns matches.

    The scanner only knows about the `detect` method. Concrete detectors
    declare what input they accept via the type parameter.
    """

    def detect(self, value: T_contra, /) -> tuple:
        ...


class PathDetector(Detector[FileChange], Protocol):
    """Detects matches against file paths in a change."""

    def detect(self, value: FileChange, /) -> tuple[PathMatch, ...]:
        ...


class ContentDetector(Detector[str], Protocol):
    """Detects matches against diff content (patch text)."""

    def detect(self, value: str, /) -> tuple[ContentMatch, ...]:
        ...
