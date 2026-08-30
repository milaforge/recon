"""Tests for offline, Ethereum-aware private-key detection."""

from datetime import UTC, datetime

from recon.detectors.ethereum import (
    EthereumPrivateKeyClassifier,
    EthereumPrivateKeyDetector,
)
from recon.detectors.generic import GenericSecretClassifier, GenericSecretDetector
from recon.models import (
    ChangeStatus,
    Classification,
    Commit,
    CommitDiff,
    FileChange,
    FileDiff,
    LineType,
)
from recon.scanner import ExposureScanner

# Fixed, synthetic, non-production test vector. It has no external provenance and
# must never be used for an account or credential.
SYNTHETIC_PRIVATE_KEY = "a5" * 32


def _scan(patch: str, *, with_generic: bool = False):
    file_diff = FileDiff(
        FileChange(ChangeStatus.ADDED, new_path="synthetic-config.env"), patch
    )
    commit = Commit("e" * 40, "Test", datetime(2026, 1, 1, tzinfo=UTC), "test")
    detectors = (EthereumPrivateKeyDetector(),)
    classifiers = (EthereumPrivateKeyClassifier(),)
    if with_generic:
        detectors += (GenericSecretDetector(),)
        classifiers += (GenericSecretClassifier(),)
    return list(
        ExposureScanner(detectors, classifiers).scan(
            (CommitDiff(commit, (file_diff,)),)
        )
    )


def test_detects_prefixed_and_unprefixed_case_variants_and_redacts() -> None:
    for prefix in ("", "0x", "0X"):
        raw = prefix + SYNTHETIC_PRIVATE_KEY.upper()
        finding = _scan(f'+ETH_PRIVATE_KEY = "{raw}"\n')[0]
        assert finding.detector == "ethereum.private_key"
        assert finding.classification is Classification.SECRET
        assert finding.classification_result.confidence == 0.99
        assert finding.line_type is LineType.ADDITION
        assert raw not in finding.evidence
        assert finding.evidence.startswith("<redacted sha256:")


def test_rejects_invalid_scalars_and_malformed_values() -> None:
    order = "fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141"
    patches = (
        "+PRIVATE_KEY=" + "0" * 64 + "\n",
        "+PRIVATE_KEY=" + order + "\n",
        "+PRIVATE_KEY=" + "a5" * 31 + "\n",
        "+PRIVATE_KEY=" + "a5" * 32 + "00\n",
        "+PRIVATE_KEY=" + "g5" * 32 + "\n",
    )
    assert all(not _scan(patch) for patch in patches)


def test_rejects_addresses_hashes_and_transaction_ids_by_context() -> None:
    candidate = SYNTHETIC_PRIVATE_KEY
    assert not _scan(f"+address=0x{candidate[:40]}\n")
    assert not _scan(f"+transaction_hash=0x{candidate}\n")
    assert not _scan(f"+blockHash=0x{candidate}\n")
    assert not _scan(f"+PUBLIC_KEY=0x{candidate}\n")


def test_accepts_explicit_camel_and_wallet_contexts() -> None:
    findings = _scan(
        f"+privateKey=0x{SYNTHETIC_PRIVATE_KEY}\n"
        f"+wallet_private_key={SYNTHETIC_PRIVATE_KEY}\n"
    )
    assert len(findings) == 2


def test_duplicate_candidate_on_a_line_is_reported_once() -> None:
    findings = _scan(
        f"+PRIVATE_KEY={SYNTHETIC_PRIVATE_KEY}; PRIVATE_KEY={SYNTHETIC_PRIVATE_KEY}\n"
    )
    assert len(findings) == 1


def test_coexists_with_generic_detector_with_detector_specific_results() -> None:
    findings = _scan(f"+PRIVATE_KEY=0x{SYNTHETIC_PRIVATE_KEY}\n", with_generic=True)
    assert {finding.detector for finding in findings} == {
        "ethereum.private_key",
        "generic.secret",
    }
    assert all(finding.classification is Classification.SECRET for finding in findings)
    assert all(SYNTHETIC_PRIVATE_KEY not in finding.evidence for finding in findings)
