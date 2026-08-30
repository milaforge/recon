"""Interactive terminal report navigation."""

from pathlib import Path
from typing import ClassVar

import questionary

from recon.models.findings import Finding

from .terminal import TerminalReporter


class InteractiveReporter:
    """Let a human filter findings and explicitly reveal sensitive evidence."""

    _FILTERS: ClassVar[dict[str, str | None]] = {
        "All findings": None,
        "Secrets": "secret",
        "References": "reference",
        "Unknown": "unknown",
        "False positives": "false_positive",
    }

    def __init__(
        self,
        *,
        repository_root: Path | None = None,
        github_repository: str | None = None,
    ) -> None:
        self._repository_root = repository_root
        self._github_repository = github_repository

    def report(self, findings: list[Finding]) -> None:
        active_filter: str | None = None
        show_raw_evidence = False

        while True:
            visible = [
                finding
                for finding in findings
                if active_filter is None
                or finding.classification.value == active_filter
            ]
            TerminalReporter(
                show_raw_evidence=show_raw_evidence,
                repository_root=self._repository_root,
                github_repository=self._github_repository,
            ).report(visible)

            filter_name = next(
                name for name, value in self._FILTERS.items() if value == active_filter
            )
            evidence_mode = "raw" if show_raw_evidence else "redacted"
            action = questionary.select(
                f"Viewing {filter_name.lower()} ({evidence_mode} evidence). What next?",
                choices=[
                    *[f"Filter: {name}" for name in self._FILTERS],
                    "Hide raw evidence" if show_raw_evidence else "Show raw evidence",
                    "Quit",
                ],
            ).ask()

            if action is None or action == "Quit":
                return
            if action == "Show raw evidence":
                show_raw_evidence = bool(
                    questionary.confirm(
                        "Raw evidence may contain live credentials. Reveal it?",
                        default=False,
                    ).ask()
                )
            elif action == "Hide raw evidence":
                show_raw_evidence = False
            elif action.startswith("Filter: "):
                active_filter = self._FILTERS[action.removeprefix("Filter: ")]
