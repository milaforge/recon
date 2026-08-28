# Product Roadmap

## Current State (v0.1.x)

**Forensics MVP** — Historical scanning works end-to-end.

```
✅ Git repository validation (shallow/partial detection)
✅ Commit traversal with deduplication
✅ File diff extraction (add/modify/delete/rename/copy)
✅ Path detector (regex on paths)
✅ Content detector (regex on diff lines with classification)
✅ Scanner orchestration
✅ Terminal + JSON reporting
✅ CLI: search_exposure, git fetch-all
✅ Comprehensive test suite (unit, integration, semantic)
```

---

## Phase 2: Prevention (v0.2)

**Goal**: `recon scan` blocks secrets at commit time.

### Features

| Feature | Description | Effort |
|---------|-------------|--------|
| `recon scan` | Scan staged changes (index) | M |
| Pre-commit hook | `recon install-hook` installs `.git/hooks/pre-commit` | S |
| Exit codes | Non-zero on findings for CI | S |
| Baseline/allowlist | `.reconignore` or `.recon-baseline` for known patterns | M |
| Staged-only mode | Don't scan unstaged changes | S |

### Technical

```python
# New command: recon scan
# Scans git diff --cached (staged changes)
# Uses same detectors, same findings model
# Exits 1 if findings, 0 if clean
```

### CLI

```bash
recon scan                    # Scan staged changes
recon scan --all              # Scan working tree + staged
recon install-hook            # Install pre-commit hook
recon uninstall-hook          # Remove hook
```

---

## Phase 3: Classification (v0.3)

**Goal**: Reduce noise, prioritize real secrets.

### Features

| Feature | Description | Effort |
|---------|-------------|--------|
| Classifier interface | `Evidence → Classification` | M |
| Built-in rules | Heuristics for common false positives | M |
| Confidence scoring | HIGH/MEDIUM/LOW per finding | M |
| Context awareness | Test files, docs, examples, env var refs | L |
| Severity filtering | `--min-severity HIGH` | S |

### Classifier Design

```python
class Classification(Enum):
    SECRET = "secret"
    REFERENCE = "reference"      # os.getenv("KEY")
    FALSE_POSITIVE = "false_positive"  # test fixtures, docs
    UNKNOWN = "unknown"

class Classifier(Protocol):
    def classify(self, evidence: Evidence, context: Context) -> Classification: ...

class Context:
    file_path: str
    line_type: LineType
    surrounding_lines: list[str]
    is_test_file: bool
    is_doc_file: bool
```

### Heuristics

| Pattern | Classification | Reason |
|---------|----------------|--------|
| `os.getenv("KEY")` | REFERENCE | Loading from env |
| `process.env.KEY` | REFERENCE | Loading from env |
| `test_*.py`, `*_test.py` | FALSE_POSITIVE | Test fixture |
| `*.md`, `*.rst` | FALSE_POSITIVE | Documentation |
| `example`, `sample`, `placeholder` | FALSE_POSITIVE | Example value |
| High entropy + no context | SECRET | Likely real credential |

---

## Phase 4: Plugin Ecosystem (v0.4)

**Goal**: Extensible detectors without core changes.

### Plugin Interface

```python
# recon/plugins/base.py
class DetectorPlugin(Protocol):
    name: str
    version: str
    detectors: list[Detector]  # PathDetector, ContentDetector, etc.

class Detector(Protocol):
    name: str
    def detect(self, context: DetectionContext) -> Iterable[Evidence]: ...

class DetectionContext:
    # For path detectors
    old_path: str | None
    new_path: str | None
    # For content detectors
    patch: str | None
    # For blob detectors
    blob: bytes | None
    # Metadata
    commit: Commit
    file_change: FileChange
```

### Built-in Plugins

| Plugin | Detectors | Patterns |
|--------|-----------|----------|
| `recon-plugin-generic` | Path, Content | `.env`, `secret`, `credential`, high entropy |
| `recon-plugin-aws` | Content | Access keys, secret keys, session tokens |
| `recon-plugin-github` | Content | PATs, OAuth tokens, SSH keys |
| `recon-plugin-ethereum` | Content | Private keys, mnemonics, RPC URLs |
| `recon-plugin-jwt` | Content | JWT tokens, JWKS |
| `recon-plugin-gcp` | Content | Service account keys, API keys |

### Discovery

```python
# Entry point: recon.detectors
# pyproject.toml:
[project.entry-points."recon.detectors"]
aws = "recon_plugin_aws:plugin"
github = "recon_plugin_github:plugin"
```

```bash
uv add recon-plugin-aws
# Automatically discovered
```

### Custom Plugins

```python
# company_plugin.py
from recon.plugins.base import DetectorPlugin, Detector, DetectionContext, Evidence

class CompanyAPIDetector:
    name = "company_api"
    def detect(self, ctx: DetectionContext) -> Iterable[Evidence]:
        if ctx.new_path and "internal" in ctx.new_path:
            # Custom logic
            ...

class CompanyPlugin:
    name = "company-internal"
    version = "1.0.0"
    detectors = [CompanyAPIDetector()]
```

---

## Phase 5: Remediation (v0.5)

**Goal**: Help fix exposures.

### Features

| Feature | Description | Effort |
|---------|-------------|--------|
| `recon clean <commit>` | Interactive history rewrite | XL |
| Secret rotation guide | "Revoke X, rotate Y" per finding | M |
| Secret manager integration | Vault, AWS Secrets Manager, 1Password | L |
| Automated PR creation | Fix + open PR | XL |

### Clean Command

```bash
recon clean abc123           # Rewrite from commit
recon clean --dry-run abc123 # Show what would change
recon clean --force abc123   # No confirmation
```

**Approach**: `git filter-repo` or `git filter-branch` with path/content rewriting.

---

## Phase 6: Enterprise (v1.0)

**Goal**: Production-ready for organizations.

### Features

| Feature | Description | Effort |
|---------|-------------|--------|
| Policy-as-code | `recon-policy.yaml` with rules | M |
| Centralized patterns | Pattern registry, versioned | M |
| Audit logging | JSONL audit trail | S |
| SARIF output | GitHub/GitLab code scanning | M |
| Multi-repo scanning | `recon scan-org --org myorg` | L |
| Team management | Per-team policies | L |
| Metrics dashboard | Exposure trends, MTTR | XL |

### Policy Example

```yaml
# recon-policy.yaml
version: 1
rules:
  - id: no-aws-keys
    detector: aws
    action: block
    severity: critical
  - id: no-private-keys
    pattern: "PRIVATE_KEY="
    action: block
    severity: critical
  - id: allow-test-fixtures
    pattern: "test_.*"
    action: allow
    paths: ["**/test_*.py", "**/*_test.py"]
```

---

## Technical Debt & Improvements

| Area | Issue | Priority |
|------|-------|----------|
| Performance | Large repo scanning (>100k commits) | High |
| Memory | Streaming for huge diffs | Medium |
| Windows | Path handling, line endings | Medium |
| Binary files | Better detection/skipping | Low |
| Merge commits | Parent diff selection | Medium |
| Submodules | Recursive scanning | Low |

---

## Release Cadence

| Version | Target | Focus |
|---------|--------|-------|
| 0.1.x | Current | Forensics MVP |
| 0.2.0 | Q1 2025 | Prevention |
| 0.3.0 | Q2 2025 | Classification |
| 0.4.0 | Q3 2025 | Plugins |
| 0.5.0 | Q4 2025 | Remediation |
| 1.0.0 | Q1 2026 | Enterprise |

---

## Dependencies

### Current
- `typer` — CLI
- `questionary` — Interactive prompts (future)
- `uv` — Package management

### Future
- `git-filter-repo` — History rewriting (Phase 5)
- `rich` — Better terminal output
- `pydantic` — Config validation
- `importlib.metadata` — Plugin discovery

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Git subprocess changes | Low | High | Pin Git version, test matrix |
| False positive fatigue | High | High | Classification phase, baselines |
| Performance at scale | Medium | High | Streaming, indexing, profiling |
| Plugin API stability | Medium | Medium | Versioned protocols, deprecation policy |
| Secret manager integration | Low | Medium | Abstract interface, multiple providers |