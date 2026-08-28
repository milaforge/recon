from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from recon.detectors.base import ContentDetector, PathDetector
from recon.models.diff import CommitDiff
from recon.models.findings import Finding


@dataclass(frozen=True, slots=True)
class ExposureScanner:
    path_detector: PathDetector | None = field(default=None, kw_only=True)
    content_detector: ContentDetector | None = field(default=None, kw_only=True)

    def scan(
        self,
        commits: Iterable[CommitDiff],
    ) -> Iterator[Finding]:
        for commit in commits:
            yield from self._scan_commit(commit)

    def _scan_commit(
        self,
        commit_diff: CommitDiff,
    ) -> Iterator[Finding]:
        for file_diff in commit_diff.files:
            change = file_diff.change

            if self.path_detector is not None:
                for match in self.path_detector.detect(change):
                    yield Finding.from_path_match(
                        match=match,
                        change=change,
                        commit_sha=commit_diff.commit.sha,
                        commit_subject=commit_diff.commit.subject,
                        author=commit_diff.commit.author,
                        timestamp=commit_diff.commit.timestamp,
                    )

            if self.content_detector is not None:
                for match in self.content_detector.detect(file_diff.patch):
                    yield Finding.from_content_match(
                        match=match,
                        change=change,
                        commit_sha=commit_diff.commit.sha,
                        commit_subject=commit_diff.commit.subject,
                        author=commit_diff.commit.author,
                        timestamp=commit_diff.commit.timestamp,
                    )
