"""Interactive report filtering and evidence-safety tests."""

from unittest.mock import Mock

import questionary

from recon.reporting.interactive import InteractiveReporter
from tests.test_reporting_contract import RAW, _findings


def test_interactive_report_filters_and_quits(monkeypatch, capsys) -> None:
    prompts = iter(("Filter: References", "Quit"))
    monkeypatch.setattr(
        questionary,
        "select",
        lambda *args, **kwargs: Mock(ask=lambda: next(prompts)),
    )

    InteractiveReporter().report(_findings())

    output = capsys.readouterr().out
    assert "Scan summary: 3 finding(s)" in output
    assert "Scan summary: 1 finding(s)" in output
    assert "[1/1] REFERENCE" in output
    assert RAW not in output


def test_interactive_report_requires_confirmation_to_reveal(
    monkeypatch, capsys
) -> None:
    prompts = iter(("Show raw evidence", "Quit"))
    monkeypatch.setattr(
        questionary,
        "select",
        lambda *args, **kwargs: Mock(ask=lambda: next(prompts)),
    )
    monkeypatch.setattr(
        questionary, "confirm", lambda *args, **kwargs: Mock(ask=lambda: True)
    )

    InteractiveReporter().report(_findings())

    output = capsys.readouterr().out
    assert "WARNING: Raw evidence is visible" in output
    assert RAW in output
