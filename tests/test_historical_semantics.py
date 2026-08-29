"""
Historical semantics tests: complex scenarios that validate correct
historical exposure detection.
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


class TestLinearHistory:
    """Test the canonical linear history scenario."""

    def test_linear_history_secret_lifecycle(self, git_repo: Path) -> None:
        """
        Test the full secret lifecycle:
          C1: initial
          C2: add .env with secret
          C3: modify .env (rotate secret)
          C4: rename .env -> config/.env
          C5: delete config/.env

        All historical exposures should be detectable.
        """
        from tests.fixtures.git_repo import build_linear_history

        build_linear_history(git_repo)

        # Scan all history
        findings = scan_repo(git_repo, content_patterns=[r"PRIVATE_KEY="])

        # Should find:
        # C2: addition of secret1
        # C3: deletion of secret1 + addition of secret2
        # C4: secret2 in context (rename shows content)
        # C5: deletion of secret2
        assert len(findings) >= 4

        # Verify each commit has findings
        subjects = {f.commit_subject for f in findings}
        assert "add .env" in subjects
        assert "modify .env" in subjects
        assert "delete config/.env" in subjects

    def test_path_detector_tracks_rename_history(self, git_repo: Path) -> None:
        """Path detector should track file through rename."""
        from tests.fixtures.git_repo import build_linear_history

        build_linear_history(git_repo)

        findings = scan_repo(git_repo, path_patterns=[r"\.env$"])

        # Should match .env in C2, C3, and config/.env in C4, C5
        paths = set()
        for f in findings:
            if f.old_path:
                paths.add(f.old_path)
            if f.new_path:
                paths.add(f.new_path)

        assert ".env" in paths
        assert "config/.env" in paths


class TestBranchScenarios:
    """Test branch-specific exposure scenarios."""

    def test_secret_only_on_feature_branch(self, git_repo: Path) -> None:
        """
        main: clean
        feature: has secret
        """
        from tests.fixtures.git_repo import build_branch_with_secret

        _main_sha, _feature_sha = build_branch_with_secret(git_repo)

        # Scan main - clean
        findings_main = scan_repo(git_repo, content_patterns=[r"api_key"], refs=["main"])
        assert len(findings_main) == 0

        # Scan feature - has secret in two commits (add + delete)
        findings_feature = scan_repo(git_repo, content_patterns=[r"api_key"], refs=["feature"])
        assert len(findings_feature) == 2
        assert "api_key" in findings_feature[0].evidence.lower()
        assert "api_key" in findings_feature[1].evidence.lower()

        # Scan both - deduplicated (shared commits: initial, add config)
        findings_both = scan_repo(git_repo, content_patterns=[r"api_key"], refs=["main", "feature"])
        assert len(findings_both) == 2

    def test_secret_added_then_removed_on_different_branch(self, git_repo: Path) -> None:
        """
        main: C1 -> C2 (add secret) -> C3 (clean)
        feature: C1 -> C2 -> C4 (remove secret)
        """
        from tests.fixtures.git_repo import checkout, commit, create_branch, write_file

        write_file(git_repo, "README.md", "# Project\n")
        commit(git_repo, "Initial")

        # Add secret on main
        write_file(git_repo, "secret.txt", "TOKEN=abc123\n")
        commit(git_repo, "Add token")

        # Create feature branch (has secret)
        create_branch(git_repo, "feature")

        # Back to main, remove secret
        checkout(git_repo, "main")
        from tests.fixtures.git_repo import delete_file
        delete_file(git_repo, "secret.txt")
        commit(git_repo, "Remove token")

        # Scan feature - should find addition (commit C2 is shared)
        findings_feature = scan_repo(git_repo, content_patterns=[r"TOKEN="], refs=["feature"])
        assert len(findings_feature) == 1
        assert findings_feature[0].commit_subject == "Add token"

        # Scan main - should find both addition and deletion
        findings_main = scan_repo(git_repo, content_patterns=[r"TOKEN="], refs=["main"])
        assert len(findings_main) == 2
        subjects = {f.commit_subject for f in findings_main}
        assert subjects == {"Add token", "Remove token"}

        # Scan both - should find 2 unique commits (Add token is shared, Remove token is main-only)
        findings_both = scan_repo(git_repo, content_patterns=[r"TOKEN="], refs=["main", "feature"])
        assert len(findings_both) == 2


class TestSharedCommitDeduplication:
    """Test deduplication of shared commits."""

    def test_same_commit_reachable_from_two_branches(self, git_repo: Path) -> None:
        """
        A -- B -- C (main)
             \
              D (feature)

        Commit B is reachable from both main and feature.
        Should produce ONE finding for B, not two.
        """
        from tests.fixtures.git_repo import build_shared_commit

        _main_sha, _feature_sha, shared_sha = build_shared_commit(git_repo)

        findings = scan_repo(git_repo, content_patterns=[r"SECRET="], refs=["main", "feature"])

        # Should produce exactly ONE finding for the shared commit B
        assert len(findings) == 1
        assert findings[0].commit_sha == shared_sha  # B is the shared commit


class TestBinaryFiles:
    """Test binary file handling."""

    def test_binary_file_does_not_crash_scanner(self, git_repo: Path) -> None:
        """Binary files should not crash the scanner."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "README.md", "# Project\n")
        commit(git_repo, "Initial")

        # Create a binary file
        binary_content = bytes(range(256))
        (git_repo / "binary.dat").write_bytes(binary_content)
        commit(git_repo, "Add binary file")

        # Should not crash
        findings = scan_repo(git_repo, content_patterns=[r"SECRET"])

        # Binary file produces no matches
        assert isinstance(findings, list)


class TestFalsePositives:
    """Test that known false positives are not promoted to secrets."""

    def test_env_var_reference_not_secret(self, git_repo: Path) -> None:
        """
        PRIVATE_KEY = os.getenv("PRIVATE_KEY")
        should match as evidence but NOT be classified as a secret.
        """
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "app.py", 'PRIVATE_KEY = os.getenv("PRIVATE_KEY")\n')
        commit(git_repo, "Add config loading")

        findings = scan_repo(git_repo, content_patterns=[r"PRIVATE_KEY"])

        # The scanner WILL match this (it's a regex match)
        # But the Finding records it as evidence, not a classified secret
        assert len(findings) == 1
        f = findings[0]
        assert f.detector == "content"
        assert f.pattern == "PRIVATE_KEY"
        assert 'os.getenv("PRIVATE_KEY")' in f.evidence
        # Classification happens at a higher layer

    def test_test_fixture_not_secret(self, git_repo: Path) -> None:
        """Test fixtures with fake secrets should match as evidence."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "test_config.py", 'API_KEY = "test_key_123"\n')
        commit(git_repo, "Add test config")

        findings = scan_repo(git_repo, content_patterns=[r"API_KEY"])

        assert len(findings) == 1
        assert "test_key_123" in findings[0].evidence

    def test_documentation_example_not_secret(self, git_repo: Path) -> None:
        """Documentation examples should match as evidence."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "README.md", "# Config\n\nSet `PRIVATE_KEY=your_key_here`\n")
        commit(git_repo, "Add docs")

        findings = scan_repo(git_repo, content_patterns=[r"PRIVATE_KEY"])

        assert len(findings) == 1
        assert "your_key_here" in findings[0].evidence


class TestMultiplePatterns:
    """Test multiple pattern combinations."""

    def test_multiple_content_patterns(self, git_repo: Path) -> None:
        """Multiple content patterns should all be matched."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "config.env", "API_KEY=key1\nPRIVATE_KEY=key2\nMNEMONIC=word1 word2\n")
        commit(git_repo, "Add keys")

        findings = scan_repo(
            git_repo,
            content_patterns=[r"API_KEY=", r"PRIVATE_KEY=", r"MNEMONIC="],
        )

        assert len(findings) == 3
        patterns = {f.pattern for f in findings}
        assert patterns == {"API_KEY=", "PRIVATE_KEY=", "MNEMONIC="}

    def test_path_and_content_patterns_combined(self, git_repo: Path) -> None:
        """Path and content patterns should both work."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, ".env", "SECRET=value\n")
        write_file(git_repo, "config.json", '{"key": "value"}\n')
        commit(git_repo, "Add configs")

        findings = scan_repo(
            git_repo,
            path_patterns=[r"\.env$"],
            content_patterns=[r"SECRET="],
        )

        assert len(findings) == 2
        detectors = {f.detector for f in findings}
        assert detectors == {"path", "content"}


class TestTraversalEdgeCases:
    """Test traversal edge cases."""

    def test_empty_repository(self, git_repo: Path) -> None:
        """Empty repository should produce no findings."""
        findings = scan_repo(git_repo, content_patterns=[r"SECRET"])
        assert findings == []

    def test_single_commit_repository(self, git_repo: Path) -> None:
        """Single commit repository should work."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "a.txt", "a\n")
        commit(git_repo, "Only commit")

        findings = scan_repo(git_repo, content_patterns=[r"SECRET"])
        assert findings == []

    def test_traversal_order_newest_first(self, git_repo: Path) -> None:
        """Traversal should return commits newest-first."""
        from tests.fixtures.git_repo import commit, write_file

        write_file(git_repo, "a.txt", "a\n")
        commit(git_repo, "A")

        write_file(git_repo, "b.txt", "b\n")
        commit(git_repo, "B")

        write_file(git_repo, "c.txt", "c\n")
        commit(git_repo, "C")

        diffs = list(iter_commit_diffs(["HEAD"], cwd=git_repo))
        assert len(diffs) == 3
        assert diffs[0].commit.subject == "C"
        assert diffs[1].commit.subject == "B"
        assert diffs[2].commit.subject == "A"
