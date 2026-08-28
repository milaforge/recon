"""
Content detector tests: regex matching against diff content, line classification.
"""

import pytest

from recon.detectors.content import ContentDetector
from recon.models.findings import ContentMatch, LineType


class TestContentDetector:
    """Tests for ContentDetector."""

    def test_content_detector_matches_added_line(self) -> None:
        """ContentDetector should match patterns in added lines."""
        detector = ContentDetector.from_patterns([r"PRIVATE_KEY="])

        patch = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
+PRIVATE_KEY=new
"""
        matches = detector.detect(patch)

        assert len(matches) == 1
        match = matches[0]
        assert match.pattern == "PRIVATE_KEY="
        assert match.line == "PRIVATE_KEY=new"
        assert match.line_type == LineType.ADDITION

    def test_content_detector_matches_deleted_line(self) -> None:
        """ContentDetector should match patterns in deleted lines."""
        detector = ContentDetector.from_patterns([r"PRIVATE_KEY="])

        patch = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
-PRIVATE_KEY=secret
"""
        matches = detector.detect(patch)

        assert len(matches) == 1
        match = matches[0]
        assert match.line == "PRIVATE_KEY=secret"
        assert match.line_type == LineType.DELETION

    def test_content_detector_matches_context_line(self) -> None:
        """ContentDetector should match patterns in context lines."""
        detector = ContentDetector.from_patterns([r"API_KEY="])

        patch = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,3 @@
 API_KEY=keep
-OLD=value
+NEW=value
 OTHER=thing
"""
        matches = detector.detect(patch)

        assert len(matches) == 1
        match = matches[0]
        assert match.line == "API_KEY=keep"
        assert match.line_type == LineType.CONTEXT

    def test_content_detector_ignores_git_metadata(self) -> None:
        """ContentDetector should ignore diff metadata lines."""
        detector = ContentDetector.from_patterns([r"diff"])

        patch = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
+diff = "something"
"""
        matches = detector.detect(patch)

        # Should only match the added line, not the metadata
        assert len(matches) == 1
        assert matches[0].line == 'diff = "something"'
        assert matches[0].line_type == LineType.ADDITION

    def test_content_detector_matches_multiple_patterns(self) -> None:
        """ContentDetector should match multiple patterns."""
        detector = ContentDetector.from_patterns([r"PRIVATE_KEY=", r"API_KEY="])

        patch = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
-PRIVATE_KEY=old
+API_KEY=new
"""
        matches = detector.detect(patch)

        assert len(matches) == 2
        patterns = {m.pattern for m in matches}
        assert patterns == {"PRIVATE_KEY=", "API_KEY="}

    def test_content_detector_matches_multiple_lines(self) -> None:
        """ContentDetector should match multiple lines."""
        detector = ContentDetector.from_patterns([r"SECRET="])

        patch = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1,2 +1,2 @@
-SECRET=one
+SECRET=two
"""
        matches = detector.detect(patch)

        assert len(matches) == 2
        lines = {m.line for m in matches}
        assert lines == {"SECRET=one", "SECRET=two"}

    def test_content_detector_empty_patterns_returns_empty(self) -> None:
        """ContentDetector with empty patterns should return empty."""
        detector = ContentDetector.from_patterns([])

        patch = "+SECRET=value\n"
        matches = detector.detect(patch)

        assert matches == ()

    def test_content_detector_line_number_tracking(self) -> None:
        """ContentDetector should track line numbers correctly."""
        detector = ContentDetector.from_patterns([r"SECRET="])

        patch = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,3 @@
 LINE1
-SECRET=old
+SECRET=new
 LINE3
"""
        matches = detector.detect(patch)

        assert len(matches) == 2
        line_numbers = {m.line_number for m in matches}
        # Line numbers are 1-indexed within the patch
        assert all(isinstance(n, int) and n > 0 for n in line_numbers)

    def test_content_detector_classifies_addition_correctly(self) -> None:
        """ContentDetector should classify + lines as ADDITION."""
        detector = ContentDetector.from_patterns([r"SECRET="])

        patch = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
+SECRET=added
"""
        matches = detector.detect(patch)

        assert len(matches) == 1
        assert matches[0].line_type == LineType.ADDITION

    def test_content_detector_classifies_deletion_correctly(self) -> None:
        """ContentDetector should classify - lines as DELETION."""
        detector = ContentDetector.from_patterns([r"SECRET="])

        patch = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
-SECRET=deleted
"""
        matches = detector.detect(patch)

        assert len(matches) == 1
        assert matches[0].line_type == LineType.DELETION

    def test_content_detector_classifies_context_correctly(self) -> None:
        """ContentDetector should classify ' ' lines as CONTEXT."""
        detector = ContentDetector.from_patterns([r"SECRET="])

        patch = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
 SECRET=context
"""
        matches = detector.detect(patch)

        assert len(matches) == 1
        assert matches[0].line_type == LineType.CONTEXT

    def test_content_detector_handles_binary_patch_gracefully(self) -> None:
        """ContentDetector should handle binary patches without crashing."""
        detector = ContentDetector.from_patterns([r"SECRET"])

        # Binary patch output from git
        patch = """diff --git a/binary.dat b/binary.dat
index 0000000..1234567 100644
Binary files a/binary.dat and b/binary.dat differ
"""
        matches = detector.detect(patch)

        # Should not crash, just return no matches
        assert matches == ()