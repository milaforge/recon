"""Unit and reporting tests for conservative generic secret detection."""

from datetime import UTC, datetime

from recon.detectors.generic import (
    GenericSecretClassifier,
    GenericSecretDetector,
    redact_secret,
)
from recon.models import (
    ChangeStatus,
    Classification,
    Commit,
    CommitDiff,
    FileChange,
    FileDiff,
)
from recon.reporting.json import JSONReporter
from recon.reporting.terminal import TerminalReporter
from recon.scanner import ExposureScanner

RAW = "SYNTHETIC-a8B7c6D5e4F3"


def _scan(patch: str, path: str = "config.env"):
    file_diff = FileDiff(FileChange(ChangeStatus.ADDED, new_path=path), patch)
    commit = Commit("a" * 40, "Test", datetime(2026, 1, 1, tzinfo=UTC), "test")
    scanner = ExposureScanner(
        detectors=(GenericSecretDetector(),), classifiers=(GenericSecretClassifier(),)
    )
    return list(scanner.scan((CommitDiff(commit, (file_diff,)),)))


def test_classifies_credential_assignment_and_redacts_it() -> None:
    finding = _scan(f'+API_KEY = "{RAW}"\n')[0]
    assert finding.classification is Classification.SECRET
    assert finding.evidence == redact_secret(RAW)
    assert RAW not in finding.evidence


def test_does_not_match_credential_words_inside_program_identifiers() -> None:
    assert not _scan("+cTokens[i] = CToken(cTokenAddress);\n", "contracts/core.sol")
    assert not _scan("+const isCToken = await contract.isCToken().call();\n")


def test_source_code_expressions_are_false_positives() -> None:
    expressions = _scan(
        "+EIP20Interface token = EIP20Interface(underlying);\n+token = token_;\n",
        "contracts/core.sol",
    )
    assert len(expressions) == 2
    assert all(
        finding.classification is Classification.FALSE_POSITIVE
        for finding in expressions
    )


def test_unquoted_shell_assignment_remains_a_secret_candidate() -> None:
    finding = _scan(f"+API_KEY={RAW}\n", "deploy.sh")[0]
    assert finding.classification is Classification.SECRET


def test_raw_reporting_includes_the_matching_assignment_line(capsys) -> None:
    finding = _scan(f'+API_KEY = "{RAW}"\n')[0]
    TerminalReporter(show_raw_evidence=True).report([finding])
    JSONReporter(show_raw_evidence=True).report([finding])
    output = capsys.readouterr().out
    assert f'API_KEY = "{RAW}"' in output


def test_classifies_environment_reference_and_placeholder() -> None:
    reference = _scan('+password: os.getenv("DATABASE_PASSWORD")\n')[0]
    placeholder = _scan('+token = "changeme"\n')[0]
    assert reference.classification is Classification.REFERENCE
    assert placeholder.classification is Classification.FALSE_POSITIVE


def test_ambiguous_assignment_remains_unknown() -> None:
    assert _scan('+secret = "short"\n')[0].classification is Classification.UNKNOWN


def test_complete_multiline_pem_is_secret_but_boundary_alone_is_not() -> None:
    complete = _scan(
        "+-----BEGIN PRIVATE KEY-----\n+SYNTHETIC-TEST-MATERIAL\n"
        "+-----END PRIVATE KEY-----\n"
    )
    incomplete = _scan("+-----BEGIN PRIVATE KEY-----\n")
    assert len(complete) == 1
    assert complete[0].classification is Classification.SECRET
    assert not incomplete


def test_non_production_and_generated_paths_are_false_positives() -> None:
    assert (
        _scan(f'+API_KEY="{RAW}"\n', "docs/example.md")[0].classification
        is Classification.FALSE_POSITIVE
    )
    assert (
        _scan(f'+API_KEY="{RAW}"\n', "dist/app.min.js")[0].classification
        is Classification.FALSE_POSITIVE
    )


def test_binary_and_adversarially_long_lines_are_ignored() -> None:
    assert not _scan("Binary files a/image and b/image differ\n")
    assert not _scan("+API_KEY=" + "x" * 100_001 + "\n")


def test_reporters_never_print_raw_candidate(capsys) -> None:
    finding = _scan(f'+API_KEY="{RAW}"\n')[0]
    TerminalReporter().report([finding])
    JSONReporter().report([finding])
    output = capsys.readouterr().out
    assert RAW not in output
    assert "<redacted sha256:" in output
