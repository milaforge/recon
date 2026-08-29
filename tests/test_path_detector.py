"""
Path detector tests: regex matching against file paths.
"""


from recon.detectors.path import PathDetector
from recon.models.diff import FileChange, ChangeStatus


class TestPathDetector:
    """Tests for PathDetector."""

    def test_path_detector_matches_exact_path(self) -> None:
        """PathDetector should match exact path patterns."""
        detector = PathDetector.from_patterns([r"secret\.txt$"])

        change = FileChange(status=ChangeStatus.ADDED, new_path="secret.txt")
        matches = detector.detect(change)

        assert len(matches) == 1
        assert matches[0].pattern == r"secret\.txt$"
        assert matches[0].path == "secret.txt"

    def test_path_detector_matches_regex(self) -> None:
        """PathDetector should match regex patterns."""
        detector = PathDetector.from_patterns([r"\.env$"])

        change = FileChange(status=ChangeStatus.ADDED, new_path="config.env")
        matches = detector.detect(change)

        assert len(matches) == 1
        assert matches[0].path == "config.env"

    def test_path_detector_matches_multiple_patterns(self) -> None:
        """PathDetector should match multiple patterns."""
        detector = PathDetector.from_patterns([r"\.env$", r"secret"])

        change = FileChange(status=ChangeStatus.ADDED, new_path="secret.env")
        matches = detector.detect(change)

        assert len(matches) == 2
        patterns = {m.pattern for m in matches}
        assert patterns == {r"\.env$", r"secret"}

    def test_path_detector_checks_both_old_and_new_paths(self) -> None:
        """PathDetector should check both old_path and new_path."""
        detector = PathDetector.from_patterns([r"\.env$"])

        # Rename: old_path matches, new_path doesn't
        change = FileChange(
            status=ChangeStatus.RENAMED,
            old_path="config.env",
            new_path="config.json",
        )
        matches = detector.detect(change)

        assert len(matches) == 1
        assert matches[0].path == "config.env"

    def test_path_detector_deduplicates_same_path(self) -> None:
        """PathDetector should not duplicate matches for same path."""
        detector = PathDetector.from_patterns([r"\.env$"])

        # Both old and new are .env files
        change = FileChange(
            status=ChangeStatus.RENAMED,
            old_path="old.env",
            new_path="new.env",
        )
        matches = detector.detect(change)

        # Should match both paths
        paths = {m.path for m in matches}
        assert paths == {"old.env", "new.env"}

    def test_path_detector_no_match_returns_empty(self) -> None:
        """PathDetector should return empty tuple for no matches."""
        detector = PathDetector.from_patterns([r"\.env$"])

        change = FileChange(status=ChangeStatus.ADDED, new_path="config.json")
        matches = detector.detect(change)

        assert matches == ()

    def test_path_detector_empty_patterns_returns_empty(self) -> None:
        """PathDetector with empty patterns should return empty."""
        detector = PathDetector.from_patterns([])

        change = FileChange(status=ChangeStatus.ADDED, new_path="secret.env")
        matches = detector.detect(change)

        assert matches == ()

    def test_path_detector_case_sensitive_by_default(self) -> None:
        """PathDetector should be case-sensitive by default."""
        detector = PathDetector.from_patterns([r"SECRET"])

        change = FileChange(status=ChangeStatus.ADDED, new_path="secret.txt")
        matches = detector.detect(change)

        assert matches == ()

    def test_path_detector_case_insensitive_with_flag(self) -> None:
        """PathDetector should support case-insensitive matching via flag."""
        import re
        detector = PathDetector.from_patterns([re.compile(r"secret", re.IGNORECASE)])

        change = FileChange(status=ChangeStatus.ADDED, new_path="SECRET.txt")
        matches = detector.detect(change)

        assert len(matches) == 1