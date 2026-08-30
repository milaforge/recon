"""Safe, opt-in navigation targets for terminal reports."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

from recon.models.findings import Finding, LineType


@dataclass(frozen=True, slots=True)
class NavigationTargets:
    """Editor and browser locations for a finding, when they can be derived."""

    commit_url: str | None = None
    path_url: str | None = None


def github_repository_url(remote_url: str) -> str | None:
    """Return a canonical GitHub repository URL for a supported Git remote."""
    remote_url = remote_url.strip()
    if remote_url.startswith("git@github.com:"):
        path = remote_url.removeprefix("git@github.com:")
    else:
        parsed = urlparse(remote_url)
        if parsed.hostname != "github.com" or not parsed.path:
            return None
        path = parsed.path.lstrip("/")
    path = path.removesuffix(".git").strip("/")
    return f"https://github.com/{quote(path, safe='/')}" if path and "/" in path else None


def navigation_targets(
    finding: Finding,
    *,
    repository_root: Path | None = None,
    github_repository: str | None = None,
) -> NavigationTargets:
    """Build links without opening programs or exposing untrusted paths."""
    path, revision = _location(finding)
    commit_url = (
        f"{github_repository}/commit/{quote(finding.commit_sha, safe='')}"
        if github_repository
        else None
    )
    if path is None:
        return NavigationTargets(commit_url=commit_url)

    line_suffix = f":{finding.line_number}:1" if finding.line_number else ""
    vscode_url = _vscode_url(repository_root, path, line_suffix)
    github_url = _github_url(github_repository, revision, path, finding.line_number)
    return NavigationTargets(commit_url=commit_url, path_url=vscode_url or github_url)


def _location(finding: Finding) -> tuple[str | None, str]:
    if finding.line_type is LineType.DELETION:
        return finding.old_path, f"{finding.commit_sha}^"
    return finding.new_path or finding.old_path, finding.commit_sha


def _vscode_url(repository_root: Path | None, path: str, line_suffix: str) -> str | None:
    if repository_root is None:
        return None
    root = repository_root.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        return None
    return f"vscode://file/{quote(str(target), safe='/:')}{line_suffix}"


def _github_url(
    repository: str | None, revision: str, path: str, line_number: int | None
) -> str | None:
    if repository is None:
        return None
    line_fragment = f"#L{line_number}" if line_number else ""
    return f"{repository}/blob/{quote(revision, safe='')}/{quote(path, safe='/')}{line_fragment}"
