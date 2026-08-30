"""Conservative, offline detection and classification of generic credentials."""

import hashlib
import re
from dataclasses import dataclass

from recon.models.detection import (
    Classification,
    ClassificationResult,
    DetectionContext,
    Evidence,
)
from recon.models.findings import LineType

from .diff_lines import iter_diff_lines

_MAX_LINE_LENGTH = 100_000
GENERIC_SECRET_DETECTOR_ID = "generic.secret"
_CREDENTIAL_NAME = re.compile(
    r"(?ix)(?<![a-z0-9_])(?:api[_-]?key|access[_-]?key|client[_-]?secret|"
    r"private[_-]?key|password|passwd|secret|auth[_-]?token|token)(?![a-z0-9_])"
)
_ASSIGNMENT = re.compile(
    rf"(?P<name>{_CREDENTIAL_NAME.pattern.replace('(?ix)', '')})\s*(?:=|:)\s*(?P<value>.+?)\s*$",
    re.IGNORECASE | re.VERBOSE,
)
_PEM_BEGIN = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----")
_PEM_END = re.compile(r"-----END (?:[A-Z0-9]+ )?PRIVATE KEY-----")
_ENV_REFERENCE = re.compile(
    r"(?ix)(?:os\.getenv\s*\(|getenv\s*\(|process\.env\b|"
    r"env(?:iron)?\s*\[|\$\{[A-Z_][A-Z0-9_]*\})"
)
_PLACEHOLDER = re.compile(
    r"(?ix)^(?:[\"']?)(?:example|sample|placeholder|changeme|replace[_ -]?me|"
    r"your[_ -]?(?:key|secret|token|password)|dummy|fake|test|todo|none|null|"
    r"<[^>]+>|x{4,}|\*{4,})(?:[\"']?)$"
)
_NON_PRODUCTION_PATH = re.compile(
    r"(?i)(?:^|/)(?:docs?|examples?|samples?|fixtures?|tests?|__tests__)(?:/|$)"
)
_GENERATED_PATH = re.compile(
    r"(?i)(?:\.min\.(?:js|css)$|(?:^|/)(?:dist|build|vendor)/|"
    r"(?:^|/)(?:package-lock\.json|uv\.lock|poetry\.lock)$)"
)
_SOURCE_CODE_PATH = re.compile(
    r"(?i)\.(?:c|cc|cpp|cs|go|java|js|jsx|php|py|rb|rs|sol|swift|ts|tsx)$"
)


def redact_secret(value: str) -> str:
    """Return a deterministic correlation token without revealing ``value``."""
    digest = hashlib.sha256(value.encode()).hexdigest()[:12]
    return f"<redacted sha256:{digest} length:{len(value)}>"


@dataclass(frozen=True, slots=True)
class GenericSecretDetector:
    """Find credential assignments and private-key PEM material in text diffs."""

    name: str = GENERIC_SECRET_DETECTOR_ID

    def detect(self, context: DetectionContext) -> tuple[Evidence, ...]:
        evidence: list[Evidence] = []
        lines = iter_diff_lines(context.file_diff.patch)
        pem_start: tuple[LineType, int, list[str]] | None = None

        for line_type, line_number, line in lines:
            if len(line) > _MAX_LINE_LENGTH:
                continue

            if pem_start is not None:
                start_type, start_number, block = pem_start
                if line_type is start_type:
                    block.append(line)
                    if _PEM_END.search(line):
                        value = "\n".join(block)
                        evidence.append(
                            Evidence(
                                detector=self.name,
                                kind="private_key_pem",
                                value=value,
                                redacted_value=redact_secret(value),
                                reason="private-key PEM boundaries were found",
                                line_type=start_type,
                                line_number=start_number,
                                source_line=value,
                            )
                        )
                        pem_start = None
                    continue
                pem_start = None

            if _PEM_BEGIN.search(line):
                pem_start = (line_type, line_number, [line])
                continue

            match = _ASSIGNMENT.search(line)
            if match:
                raw_value = match.group("value").strip().rstrip(",;").strip()
                quoted = (
                    len(raw_value) >= 2
                    and raw_value[0] == raw_value[-1]
                    and raw_value[0] in "\"'`"
                )
                value = raw_value[1:-1] if quoted else raw_value
                kind = (
                    "credential_expression"
                    if not quoted
                    and _SOURCE_CODE_PATH.search(context.file_diff.change.path)
                    else "credential_literal"
                )
                evidence.append(
                    Evidence(
                        detector=self.name,
                        kind=kind,
                        value=value,
                        redacted_value=redact_secret(value),
                        reason=f"value assigned to credential-like name {match.group('name')!r}",
                        line_type=line_type,
                        line_number=line_number,
                        source_line=line,
                    )
                )
        return tuple(evidence)


@dataclass(frozen=True, slots=True)
class GenericSecretClassifier:
    """Make conservative decisions about generic detector evidence."""

    def classify(
        self, evidence: Evidence, context: DetectionContext
    ) -> ClassificationResult:
        if evidence.detector != GENERIC_SECRET_DETECTOR_ID:
            return ClassificationResult(
                Classification.UNKNOWN, 0.0, "evidence belongs to another detector"
            )

        path = context.file_diff.change.path
        if _ENV_REFERENCE.search(evidence.value):
            return ClassificationResult(
                Classification.REFERENCE,
                0.98,
                "value is an environment-variable lookup rather than credential material",
            )
        if evidence.kind == "credential_expression":
            return ClassificationResult(
                Classification.FALSE_POSITIVE,
                0.98,
                "unquoted source-code expression is not credential material",
            )
        if _PLACEHOLDER.fullmatch(evidence.value.strip()):
            return ClassificationResult(
                Classification.FALSE_POSITIVE, 0.98, "value is an obvious placeholder"
            )
        if _NON_PRODUCTION_PATH.search(path):
            return ClassificationResult(
                Classification.FALSE_POSITIVE,
                0.9,
                "candidate occurs in documentation, an example, or a test fixture",
            )
        if _GENERATED_PATH.search(path):
            return ClassificationResult(
                Classification.FALSE_POSITIVE,
                0.85,
                "candidate occurs in a generated file",
            )
        if evidence.kind == "private_key_pem":
            return ClassificationResult(
                Classification.SECRET,
                0.99,
                "complete private-key PEM material was found",
            )

        value = evidence.value
        character_classes = sum(
            bool(pattern.search(value))
            for pattern in (
                re.compile(r"[a-z]"),
                re.compile(r"[A-Z]"),
                re.compile(r"\d"),
                re.compile(r"[^\w\s]"),
            )
        )
        if (
            len(value) >= 12
            and character_classes >= 2
            and not any(c.isspace() for c in value)
        ):
            return ClassificationResult(
                Classification.SECRET,
                0.85,
                "credential-like assignment contains a non-placeholder, high-specificity value",
            )
        return ClassificationResult(
            Classification.UNKNOWN,
            0.25,
            "credential-like assignment is too ambiguous for a secret verdict",
        )
