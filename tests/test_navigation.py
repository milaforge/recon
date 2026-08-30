from dataclasses import replace
from pathlib import Path

from recon.models import LineType
from recon.reporting.navigation import github_repository_url, navigation_targets
from recon.reporting.terminal import TerminalReporter

from .test_reporting_contract import _findings


def test_github_repository_url_supports_https_and_ssh_remotes() -> None:
    assert (
        github_repository_url("https://github.com/acme/security-repo.git")
        == "https://github.com/acme/security-repo"
    )
    assert (
        github_repository_url("git@github.com:acme/security-repo.git")
        == "https://github.com/acme/security-repo"
    )
    assert github_repository_url("https://gitlab.com/acme/security-repo.git") is None


def test_navigation_uses_commit_file_and_source_line(tmp_path: Path) -> None:
    finding = _findings()[0]
    targets = navigation_targets(
        finding,
        repository_root=tmp_path,
        github_repository="https://github.com/acme/security-repo",
    )

    assert targets.commit_url == (
        f"https://github.com/acme/security-repo/commit/{finding.commit_sha}"
    )
    assert targets.path_url == f"vscode://file/{tmp_path}/config.env:1:1"


def test_deleted_file_navigation_uses_parent_commit(tmp_path: Path) -> None:
    finding = replace(
        _findings()[0],
        old_path="old config.env",
        new_path=None,
        source=replace(_findings()[0].source, line_type=LineType.DELETION),
    )
    targets = navigation_targets(finding, github_repository="https://github.com/acme/security-repo")

    assert targets.path_url is not None
    assert f"/blob/{finding.commit_sha}%5E/" in targets.path_url
    assert "/old%20config.env#L1" in targets.path_url


def test_navigation_rejects_paths_outside_repository(tmp_path: Path) -> None:
    finding = replace(_findings()[0], new_path="../outside.env")
    targets = navigation_targets(finding, repository_root=tmp_path)
    assert targets.path_url is None


def test_terminal_emits_clickable_navigation_when_enabled(
    capsys, tmp_path: Path
) -> None:
    finding = _findings()[0]
    TerminalReporter(
        repository_root=tmp_path,
        github_repository="https://github.com/acme/security-repo",
        enable_hyperlinks=True,
    ).report([finding])

    output = capsys.readouterr().out
    assert "VS Code:" not in output
    assert "GitHub:" not in output
    assert "\x1b]8;;https://github.com/acme/security-repo/commit/" in output
    assert "\x1b]8;;vscode://file/" in output


def test_terminal_emits_copyable_navigation_when_hyperlinks_are_disabled(
    capsys, tmp_path: Path
) -> None:
    TerminalReporter(
        repository_root=tmp_path,
        github_repository="https://github.com/acme/security-repo",
        enable_hyperlinks=False,
    ).report([_findings()[0]])

    output = capsys.readouterr().out
    assert "Commit:     " in output
    assert "Path:       " in output
    assert f"commit/{_findings()[0].commit_sha}" in output
    assert "vscode://file/" in output
