"""Stable, redacted reporter contract tests."""

import json
from datetime import UTC, datetime

from recon.detectors.compat import RegexContentDetector
from recon.detectors.content import ContentDetector
from recon.detectors.generic import GenericSecretClassifier, GenericSecretDetector
from recon.models import ChangeStatus, Commit, CommitDiff, FileChange, FileDiff
from recon.reporting.json import JSONReporter
from recon.reporting.terminal import TerminalReporter
from recon.scanner import ExposureScanner

RAW = "SYNTHETIC-a8B7c6D5e4F3"


def _findings():
    diff = FileDiff(
        FileChange(ChangeStatus.ADDED, new_path="config.env"),
        f'+API_KEY={RAW}\n+password=os.getenv("PASSWORD")\n+token=short\n',
    )
    commit = Commit("a" * 40, "Test User", datetime(2026, 1, 1, tzinfo=UTC), "cases")
    return list(
        ExposureScanner((GenericSecretDetector(),), (GenericSecretClassifier(),)).scan(
            (CommitDiff(commit, (diff,)),)
        )
    )


def test_json_schema_is_versioned_complete_and_redacted(capsys) -> None:
    JSONReporter().report(_findings())
    output = capsys.readouterr().out
    document = json.loads(output)

    assert document["schema_version"] == "1.0"
    assert document["summary"] == {
        "total": 3,
        "classifications": {
            "secret": 1,
            "reference": 1,
            "false_positive": 0,
            "unknown": 1,
        },
    }
    assert {item["classification"] for item in document["findings"]} == {
        "secret",
        "reference",
        "unknown",
    }
    assert all(item["detector"] == "generic.secret" for item in document["findings"])
    assert all("remediation" in item for item in document["findings"])
    assert RAW not in output


def test_terminal_has_summary_actionable_details_and_no_raw_value(capsys) -> None:
    TerminalReporter().report(_findings())
    output = capsys.readouterr().out
    assert "Scan summary: 3 finding(s)" in output
    assert "SECRET 1, REFERENCE 1, FALSE_POSITIVE 0, UNKNOWN 1" in output
    assert "Action:" in output
    assert "generic.secret".upper() in output
    assert RAW not in output


def test_reporters_show_raw_evidence_only_when_explicitly_requested(capsys) -> None:
    findings = _findings()
    TerminalReporter(show_raw_evidence=True).report(findings)
    JSONReporter(show_raw_evidence=True).report(findings)
    output = capsys.readouterr().out
    assert RAW in output


def test_empty_reports_have_stable_shape(capsys) -> None:
    JSONReporter().report([])
    document = json.loads(capsys.readouterr().out)
    assert document["findings"] == []
    assert document["summary"]["total"] == 0


def test_reporters_defensively_redact_user_regex_content(capsys) -> None:
    raw_line = f"API_KEY={RAW}"
    diff = FileDiff(
        FileChange(ChangeStatus.ADDED, new_path="config.env"), f"+{raw_line}\n"
    )
    commit = Commit("b" * 40, "Test User", datetime(2026, 1, 1, tzinfo=UTC), "regex")
    findings = list(
        ExposureScanner(
            (RegexContentDetector(ContentDetector.from_patterns(("API_KEY",))),)
        ).scan((CommitDiff(commit, (diff,)),))
    )
    TerminalReporter().report(findings)
    JSONReporter().report(findings)
    output = capsys.readouterr().out
    assert raw_line not in output
    assert "<redacted sha256:" in output
