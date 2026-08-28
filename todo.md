8. Don't call every regex match a "secret"

This is one of the biggest design considerations.

Suppose:

-g 'PRIVATE_KEY'

matches:

PRIVATE_KEY = os.getenv("PRIVATE_KEY")

That's not a leaked secret.

Therefore the architecture should distinguish:

Pattern match
↓
Evidence
↓
Classification
↓
Finding

Initially, we can simply report:

MATCH
type: content
pattern: PRIVATE_KEY

Later we can add detectors/classifiers for:

actual credential formats
private-key material
seed phrases
API tokens
cloud credentials
JWTs
RPC credentials
high-entropy strings
known provider token formats

This prevents the first version from pretending to have a secret-detection capability it doesn't actually have.

---

Post mvp:

- entropy analysis
- GitHub API integration
- Git object recovery
- credential validation
- secret revocation
- external secret databases
- parallel scanning
- fancy TUI
- database storage

---

detectors/
├── path.py
├── content.py
└── patterns.py

containing known credential patterns.

---

I would make one adjustment before going further: don't let ExposureScanner know concrete detector classes if we don't need to. The scanner only needs the detect() interface.

For example:

recon/detectors/base.py
from typing import Protocol


class Detector(Protocol):
    def detect(self, value):
        ...

Then:

from recon.detectors.base import Detector


class ExposureScanner:
    def __init__(
        self,
        path_detector: Detector | None = None,
        content_detector: Detector | None = None,
    ) -> None:
        self.path_detector = path_detector
        self.content_detector = content_detector

This becomes useful when we later introduce:

PathDetector
ContentDetector
EntropyDetector
PrivateKeyDetector
TokenDetector
CredentialDetector

without modifying the scanner.

---

ContentDetector is searching lines, rather than trying to interpret the entire patch.

That makes -g behave much more like grep:

recon search_exposure -g 'PRIVATE_KEY'

and gives us a useful line in the resulting finding.

Later, we can add more sophisticated detectors that inspect complete blobs rather than individual diff lines.

---

There is one typing weakness here: Detector currently accepts anything, so the scanner can't statically know that the path detector accepts FileChange and the content detector accepts str.

That's acceptable temporarily.

I would not solve it with a complicated generic protocol yet. The actual detector APIs will tell us whether we need that abstraction.


---


the next architectural improvement I would make once the basic version works: instead of separate detector slots:

path_detector
content_detector

we can have:

detectors: Sequence[Detector]

and each detector declares what kind of input it consumes.

That gets us closer to a genuinely plugin-like detection pipeline.

---


add a command to delete a specific commit from the history. so that if the user found a secret exposed on a commit, its possible to redact the exposed password. like using git push force to adjust the history.
with proper disclaimer and warnings.

---