"""
Scanner integration tests: end-to-end scanner with detectors.
"""

from pathlib import Path

from recon.detectors.content import ContentDetector
from recon.detectors.path import PathDetector
from recon.git.traversal import iter_commit_diffs
from recon.models.findings import Finding
from recon.scanner import ExposureScanner


def scan_repo(
    repo_path: Path,
    path_patterns: list[str] | None = None,
    content_patterns: list[str] | None = None,
    refs: list[str] | None = None,
) -> list[Finding]:
    """Run the full scan pipeline on a repository."""
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(repo_path)

        from recon.git.repository import prepare_repository
        prepare_repository(cwd=repo_path)

        if refs is None:
            refs = ["HEAD"]

        path_detector = PathDetector.from_patterns(path_patterns) if path_patterns else None
        content_detector = ContentDetector.from_patterns(content_patterns) if content_patterns else None

        scanner = ExposureScanner(
            path_detector=path_detector,
            content_detector=content_detector,
        )

        commits = iter_commit_diffs(refs, cwd=repo_path)
        return list(scanner.scan(commits))
    finally:
        os.chdir(original_cwd)


class TestScannerIntegration:
    """End-to-end scanner tests."""

    def test_scanner_finds_secret_in_added_file(self, git_repo: Path) -> None:
        """Scanner should find secret in added file."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "config.env", "API_KEY=secret123\n")
        commit(git_repo, "Add config")

        findings = scan_repo(git_repo, content_patterns=[r"API_KEY="])

        assert len(findings) == 1
        f = findings[0]
        assert f.detector == "content"
        assert f.pattern == "API_KEY="
        assert "API_KEY=secret123" in f.evidence
        assert f.new_path == "config.env"

    def test_scanner_finds_secret_in_modified_file(self, git_repo: Path) -> None:
        """Scanner should find secret in modified file (both old and new)."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "config.env", "API_KEY=old\n")
        commit(git_repo, "Initial")

        write_file(git_repo, "config.env", "API_KEY=new\n")
        commit(git_repo, "Rotate key")

        findings = scan_repo(git_repo, content_patterns=[r"API_KEY="])

        # Should find both the initial addition and the modification
        assert len(findings) == 3

        # Two findings in the modification commit
        mod_findings = [f for f in findings if f.commit_subject == "Rotate key"]
        assert len(mod_findings) == 2

    def test_scanner_finds_secret_in_deleted_file(self, git_repo: Path) -> None:
        """Scanner should find secret in deleted file."""
        from tests.fixtures.git_repo import commit, delete_file, write_file

        write_file(git_repo, "secrets.txt", "PASSWORD=hunter2\n")
        commit(git_repo, "Add password")

        delete_file(git_repo, "secrets.txt")
        commit(git_repo, "Remove password")

        findings = scan_repo(git_repo, content_patterns=[r"PASSWORD="])

        assert len(findings) == 2
        del_findings = [f for f in findings if f.commit_subject == "Remove password"]
        assert len(del_findings) == 1
        assert "PASSWORD=hunter2" in del_findings[0].evidence

    def test_scanner_finds_secret_in_renamed_file(self, git_repo: Path) -> None:
        """Scanner should find secret in renamed file."""
        from tests.fixtures.git_repo import commit, rename_file, write_file

        write_file(git_repo, "old.env", "SECRET=value\n")
        commit(git_repo, "Add secret")

        rename_file(git_repo, "old.env", "new.env")
        commit(git_repo, "Rename")

        findings = scan_repo(
            git_repo,
            content_patterns=[r"SECRET="],
            path_patterns=[r"\.env$"],
        )

        content_findings = [f for f in findings if f.detector == "content"]
        path_findings = [f for f in findings if f.detector == "path"]

        assert len(content_findings) >= 1
        assert len(path_findings) >= 1

        # Path detector should match both old and new paths
        paths = set()
        for f in path_findings:
            if f.old_path:
                paths.add(f.old_path)
            if f.new_path:
                paths.add(f.new_path)
        assert "old.env" in paths
        assert "new.env" in paths

    def test_scanner_finds_secret_only_on_branch(self, git_repo: Path) -> None:
        """Scanner should find secret only on branch where it exists."""
        from tests.fixtures.git_repo import checkout, commit, create_branch, write_file

        write_file(git_repo, "README.md", "# Project\n")
        commit(git_repo, "Initial")

        create_branch(git_repo, "feature")
        write_file(git_repo, "config.env", "PRIVATE_KEY=secret\n")
        commit(git_repo, "Add key")

        checkout(git_repo, "main")

        # Scan main only - should find nothing
        findings_main = scan_repo(git_repo, content_patterns=[r"PRIVATE_KEY="], refs=["main"])
        assert len(findings_main) == 0

        # Scan feature - should find secret
        findings_feature = scan_repo(git_repo, content_patterns=[r"PRIVATE_KEY="], refs=["feature"])
        assert len(findings_feature) == 1

        # Scan both - should find once (deduplicated)
        findings_both = scan_repo(git_repo, content_patterns=[r"PRIVATE_KEY="], refs=["main", "feature"])
        assert len(findings_both) == 1

    def test_scanner_deduplicates_shared_commits(self, git_repo: Path) -> None:
        """Scanner should deduplicate commits reachable from multiple refs."""
        from tests.fixtures.git_repo import build_shared_commit

        _main_sha, _feature_sha, shared_sha = build_shared_commit(git_repo)

        findings = scan_repo(git_repo, content_patterns=[r"SECRET="], refs=["main", "feature"])

        # Should produce exactly ONE finding for the shared commit
        assert len(findings) == 1
        assert findings[0].commit_sha == shared_sha  # B is the shared commit

    def test_scanner_with_both_detectors(self, git_repo: Path) -> None:
        """Scanner should run both path and content detectors."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "config.env", "API_KEY=key\n")
        commit(git_repo, "Add config")

        findings = scan_repo(
            git_repo,
            path_patterns=[r"\.env$"],
            content_patterns=[r"API_KEY="],
        )

        assert len(findings) == 2
        detectors = {f.detector for f in findings}
        assert detectors == {"path", "content"}

    def test_scanner_empty_patterns_returns_no_findings(self, git_repo: Path) -> None:
        """Scanner with no patterns should return no findings."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "secret.txt", "TOKEN=abc\n")
        commit(git_repo, "Add token")

        findings = scan_repo(git_repo, content_patterns=[])
        assert len(findings) == 0

    def test_scanner_no_detectors_returns_no_findings(self, git_repo: Path) -> None:
        """Scanner with no detectors should return no findings."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "secret.txt", "TOKEN=abc\n")
        commit(git_repo, "Add token")

        findings = scan_repo(git_repo, path_patterns=None, content_patterns=None)
        assert len(findings) == 0

    def test_scanner_finding_metadata_complete(self, git_repo: Path) -> None:
        """Scanner findings should have complete metadata."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "secret.txt", "TOKEN=abc123\n")
        commit_sha = commit(git_repo, "Add token")

        findings = scan_repo(git_repo, content_patterns=[r"TOKEN="])

        assert len(findings) == 1
        f = findings[0]
        assert f.commit_sha == commit_sha
        assert f.commit_subject == "Add token"
        assert f.author == "Test User <test@example.com>"
        assert f.timestamp is not None
        assert f.detector == "content"
        assert f.pattern == "TOKEN="
        assert f.evidence == "TOKEN=abc123"
        assert f.old_path is None
        assert f.new_path == "secret.txt"
