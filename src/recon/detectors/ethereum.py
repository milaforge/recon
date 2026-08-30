"""Offline, context-aware detection of Ethereum private-key candidates."""

import re
from dataclasses import dataclass

from recon.models.detection import (
    Classification,
    ClassificationResult,
    DetectionContext,
    Evidence,
)
from recon.models.findings import LineType

from .generic import redact_secret

ETHEREUM_PRIVATE_KEY_DETECTOR_ID = "ethereum.private_key"

# Order of the secp256k1 generator. Ethereum private keys are integers in [1, n).
_SECP256K1_ORDER = int(
    "fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16
)
_MAX_LINE_LENGTH = 100_000
_PRIVATE_KEY_NAME = re.compile(
    r"(?ix)\b(?:ethereum|eth|wallet)?[_-]?(?:private[_-]?key|privatekey)\b"
)
_ASSIGNMENT = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9_-]*)\s*(?:=|:)\s*"
    r"(?P<quote>['\"]?)(?P<value>(?:0[xX])?[0-9A-Fa-f]+)(?P=quote)"
    r"(?=\s*(?:[,;#]|//|$))"
)


def _diff_lines(patch: str) -> tuple[tuple[LineType, int, str], ...]:
    lines: list[tuple[LineType, int, str]] = []
    for number, raw in enumerate(patch.splitlines(), 1):
        if raw.startswith(("+++ ", "--- ")):
            continue
        if raw.startswith("+"):
            lines.append((LineType.ADDITION, number, raw[1:]))
        elif raw.startswith("-"):
            lines.append((LineType.DELETION, number, raw[1:]))
        elif raw.startswith(" "):
            lines.append((LineType.CONTEXT, number, raw[1:]))
    return tuple(lines)


def _valid_private_key(candidate: str) -> bool:
    hexadecimal = candidate[2:] if candidate[:2].lower() == "0x" else candidate
    return (
        len(hexadecimal) == 64
        and hexadecimal.isascii()
        and all(character in "0123456789abcdefABCDEF" for character in hexadecimal)
        and 0 < int(hexadecimal, 16) < _SECP256K1_ORDER
    )


@dataclass(frozen=True, slots=True)
class EthereumPrivateKeyDetector:
    """Find structurally valid 32-byte values in explicit private-key assignments.

    Detection is entirely local and structural: it never derives an address, contacts
    a chain or service, or attempts to use candidate material.
    """

    name: str = ETHEREUM_PRIVATE_KEY_DETECTOR_ID

    def detect(self, context: DetectionContext) -> tuple[Evidence, ...]:
        evidence: list[Evidence] = []
        seen: set[tuple[LineType, int, str]] = set()
        for line_type, line_number, line in _diff_lines(context.file_diff.patch):
            if len(line) > _MAX_LINE_LENGTH:
                continue
            for match in _ASSIGNMENT.finditer(line):
                name = match.group("name")
                value = match.group("value")
                identity = (line_type, line_number, value.lower())
                if (
                    not _PRIVATE_KEY_NAME.fullmatch(name)
                    or not _valid_private_key(value)
                    or identity in seen
                ):
                    continue
                seen.add(identity)
                evidence.append(
                    Evidence(
                        detector=self.name,
                        kind="ethereum_private_key",
                        value=value,
                        redacted_value=redact_secret(value),
                        reason=(
                            "32-byte secp256k1 scalar found in an explicit "
                            "private-key assignment"
                        ),
                        line_type=line_type,
                        line_number=line_number,
                        source_line=line,
                    )
                )
        return tuple(evidence)


@dataclass(frozen=True, slots=True)
class EthereumPrivateKeyClassifier:
    """Classify evidence already constrained by the Ethereum detector."""

    def classify(
        self, evidence: Evidence, context: DetectionContext
    ) -> ClassificationResult:
        del context
        if evidence.detector != ETHEREUM_PRIVATE_KEY_DETECTOR_ID:
            return ClassificationResult(
                Classification.UNKNOWN, 0.0, "evidence belongs to another detector"
            )
        if evidence.kind != "ethereum_private_key" or not _valid_private_key(
            evidence.value
        ):
            return ClassificationResult(
                Classification.UNKNOWN,
                0.0,
                "evidence is not a structurally valid Ethereum private-key candidate",
            )
        return ClassificationResult(
            Classification.SECRET,
            0.99,
            "explicit private-key context contains a valid secp256k1 scalar",
        )
