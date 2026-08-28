Sometimes developers mistakenly commit `secrets` into Git history.
Build an automation that detects, prevents and recovers such a mistake in a git repository.

## Prevention

**Before commit**

As a _git hook_ that answers the following question:

> "Does this change contain something that should not enter Git history?"

```
Scanning staged changes...

✗ Potential secret detected

  file:     .env
  pattern:  private_key
  confidence: HIGH

  Commit blocked.
```

This is the prevention product.

## Detection

For existing git history or repositories:

> **"Did we already expose something somewhere in Git history?"**

**CLI Tool**

```
$ pip install recon
$ recon scan -a

Scanned:
  4 branches
  1,284 commits
  8,921 file changes

Findings: 3

HIGH  origin/main
      commit: abc123
      file: config/deploy.json
      detector: ethereum_private_key
```

This is the forensic/recovery capability.


## Recovery

> A secret is already exposed in our git history; how to recovery?

- **Urgently revoke the exposed key**

- [Optionally] Clean the git history

```
$ recon clean [COMMIT_HASH]
```

---

# WHY

Git is particularly dangerous for secrets because once a secret enters a commit, deleting the file from the current tree doesn't necessarily remove the historical exposure.

Therefore `recon` should intervene **as early as possible**:

```text
Developer writes code
        ↓
recon detects sensitive material
        ↓
Developer fixes it
        ↓
git commit
```

while also providing:

```text
Git repository
        ↓
recon searches history
        ↓
historical exposure report
```

The history scanner becomes a second line of defense.

---

# HOW

> **A plugin system defines what "a secret" might look like.**

`recon` **does not need to know** what an AWS key, Ethereum private key, GitHub token, JWT, API credential, or proprietary company credential looks like.

Instead:

```text
                    Recon Core
                       │
          ┌────────────┼────────────┐
          │            │            │
       Git input    Plugin API    Findings
          │            │            │
          │      ┌─────┴─────┐      │
          │      │           │      │
          │    AWS         Ethereum │
          │    plugin      plugin   │
          │      │           │      │
          │      └─────┬─────┘      │
          │            │            │
          └────────────┼────────────┘
                       ↓
                  Classification
                       ↓
                     Report
```

## A plugin should answer:

> "Given this piece of developer-controlled content, is there evidence that it represents a secret?"

For example:

```python
class SecretDetector(Protocol):
    name: str

    def detect(self, context: DetectionContext) -> Iterable[Evidence]:
        ...
```

An Ethereum plugin could eventually contain:

```text
ethereum_private_key
ethereum_mnemonic
ethereum_rpc_credentials
```

An AWS plugin:

```text
aws_access_key
aws_secret_key
session_token
```

A generic plugin:

```text
private_key_pem
high_entropy_token
password_assignment
```

And a project-specific plugin could define:

```text
company_api_token
internal_service_credentials
production_database_url
```

That last category is particularly important. **The developer should be able to define organization-specific secret patterns without modifying Recon itself.**

---

# The core should operate on evidence, not secrets

This distinction is worth preserving.

```text
                 INPUT
                   │
                   ▼
             DetectionContext
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
        path      diff     blob
          │        │        │
          └────────┼────────┘
                   ▼
              Plugin(s)
                   │
                   ▼
                Evidence
                   │
                   ▼
             Classification
                   │
                   ▼
                Finding
```

A plugin shouldn't necessarily say:

```python
return Secret(...)
```

It should produce **evidence**.

For example:

```text
plugin: ethereum
detector: private_key
evidence:
    "0x4f3..."
classification:
    SECRET
confidence:
    HIGH
```

Whereas:

```text
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
```

might produce:

```text
plugin: generic
detector: private_key_assignment
classification:
    REFERENCE
confidence:
    HIGH
```

That keeps the system intellectually honest.

---

# The CLI

We currently have:

```text
recon git fetch
recon git fetch-all
recon search_exposure
```

Those are useful development commands, but they're exposing implementation details.

Eventually the user-facing model should probably be:

```text
recon scan
recon scan-history
recon plugins
recon explain
```

with Git operations being internal infrastructure.

For example:

```bash
recon scan
```

means:

> Inspect what I'm about to commit.

And:

```bash
recon scan-history
```

means:

> Inspect Git history for previously exposed material.

The user shouldn't need to understand Git ref traversal to use the security tool.

---

# Plugin Architecture

Declarative where possible.

Something conceptually like:

```python
@dataclass(frozen=True)
class Detector:
    name: str
    description: str
    pattern: Pattern[str]
    evidence_type: EvidenceType

    def detect(...):
        ...
```

But don't constrain every plugin to regex.

We eventually want:

```text
RegexDetector
EntropyDetector
StructuredTokenDetector
ASTDetector
CustomDetector
```

For example, detecting:

```text
AWS_ACCESS_KEY_ID=...
```

is straightforward regex.

Detecting:

```text
random-looking 40-character credential
```

may require entropy.

Detecting:

```text
password = "..."
```

may benefit from syntax/AST context.

Detecting a mnemonic may require word-list validation.

Therefore the actual extension point should be a **detector interface**, not a "regex plugin" interface.

Regex is simply the easiest first implementation.

---

# The Plugin Ecosystem Could Eventually Look Like

```text
recon/
    core/
        scanner
        evidence
        classification
        reporting

    git/
        repository
        traversal
        diff

    plugins/
        generic/
        ethereum/
        aws/
        github/
        gcp/
        jwt/
```

And externally:

```text
recon-plugin-company-internal
recon-plugin-solidity
recon-plugin-cloud
```

Potentially loaded through Python packaging entry points.

That gives us:

```bash
uv add recon-plugin-ethereum
```

and Recon discovers the detector automatically.

But **don't implement package-level plugin discovery yet**. First define the internal plugin contract cleanly. Packaging/discovery can come after the detector API stabilizes.

---

# The Most Important Architectural Decision

I would now explicitly separate these concepts:

```text
Detector
    ↓
Evidence
    ↓
Classifier
    ↓
Finding
```

A detector answers:

> **"Did I observe something interesting?"**

A classifier answers:

> **"What does that evidence probably mean?"**

A finding answers:

> **"What should the user know about this?"**

That gives us room for sophisticated reasoning later without coupling it to Git.

---

## The Product Architecture I'd Target

```text
                         RECON
                           │
              ┌────────────┴────────────┐
              │                         │
          Prevention                 Forensics
              │                         │
          recon scan             recon scan-history
              │                         │
              └────────────┬────────────┘
                           │
                      Detection Engine
                           │
                ┌──────────┼──────────┐
                │          │          │
             Generic    Ethereum    Custom
             plugins    plugins     plugins
                │          │          │
                └──────────┼──────────┘
                           │
                        Evidence
                           │
                      Classification
                           │
                         Finding
                           │
                    ┌──────┴──────┐
                    │             │
                Terminal        JSON
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Quick start: adding a new detector
- Development workflow
- Test guidelines (use existing fixtures)
- Architecture principles
- Adding new CLI commands
