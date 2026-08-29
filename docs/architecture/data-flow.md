# Data Flow Architecture

The scanning boundary is context based: for each file in each reachable commit,
`ExposureScanner` constructs one immutable `DetectionContext` and supplies it to
every configured detector. Each returned `Evidence` item is passed through the
ordered classifier sequence and combined with commit and path metadata in a
`Finding`.

```mermaid
flowchart LR
    A[CommitDiff] --> B[DetectionContext]
    B --> C[Detector sequence]
    C --> D[Evidence]
    D --> E[Classifier sequence]
    E --> F[ClassificationResult]
    D --> G[Finding]
    F --> G
    G --> H[Reporter]
```

An evidence item always creates exactly one finding. Multiple evidence items from
one detector create multiple traceable findings. An absent or inconclusive
classifier produces `UNKNOWN`; the scanner does not silently promote evidence to
a secret.

## End-to-End Flow

```mermaid
flowchart TD
    A["User Input (CLI args)"] --> B[Repository Preparation]
    B --> C[Commit Traversal]
    C --> D["Scanner (detectors)"]
    D --> E["Findings (evidence)"]
    E --> F["Reporter (terminal/json)"]
```

## Stage 1: Repository Preparation

**Entry**: `prepare_repository(cwd)` in `git/repository.py`

```mermaid
flowchart TD
    A[User provides --repo or cwd] --> B[ensure_repository]
    B -->|GitError if not in Git work tree| C[is_partial_repository]
    C -->|GitError if partial clone detected| D[unshallow]
    D -->|Fetch --unshallow from remotes| E[ensure_complete_repository]
    E -->|Final validation| F[Validated, complete repository]
```

**Output**: Validated, complete repository ready for historical analysis

---

## Stage 2: Ref Resolution

**Entry**: `_resolve_refs()` in `commands/search_exposure.py`

```mermaid
flowchart TD
    A[Input: all_refs, interactive, refs] --> B{refs provided?}
    B -->|Yes| C[Use provided refs]
    B -->|No| D{all_refs?}
    D -->|Yes| E[local branches + remote refs + tags]
    D -->|No| F{interactive?}
    F -->|Yes| G[stub → HEAD]
    F -->|No| H[Default → HEAD]
    C --> I[Output: List of ref strings]
    E --> I
    G --> I
    H --> I
```

**Output**: List of ref strings (branch names, tag names, commit SHAs)

---

## Stage 3: Commit Traversal

**Entry**: `iter_commit_diffs(refs, cwd)` in `git/traversal.py`

```mermaid
flowchart TD
    A["get_all_reachable_commits(refs[])"] --> B[For each ref: git rev-list --topo-order --reverse ref]
    B --> C["Deduplicate SHAs (set → list, preserves order)"]
    C --> D["For each SHA: get_commit_diff(sha)"]
    D --> E["Yield CommitDiff (lazy iterator)"]
```

### Commit Diff Construction (`git/commits.py` → `git/diff.py`)

```mermaid
flowchart TD
    A["get_commit_diff(sha)"] --> B["get_commit(sha)" → Commit metadata]
    A --> C["get_file_diffs(sha) → list[FileDiff]"]
    C --> D["get_file_changes(sha) → list[FileChange]"]
    D --> E[git diff-tree -r --root -M -C --name-status -z]
    C --> F["For each change: get_file_patch(sha, change)"]
    F --> G[git show --format= --patch --find-renames --find-copies sha -- path]
```

**Output**: `Iterator[CommitDiff]` — lazy, newest-first, deduplicated

---

## Stage 4: Scanning

**Entry**: `ExposureScanner.scan(commits)` in `scanner.py`

```mermaid
flowchart TD
    A[for commit_diff in commits] --> B[For each file_diff in commit_diff.files]
    B --> C{path_detector?}
    C -->|Yes| D["path_detector.detect(change)"]
    D --> E["For each PathMatch: yield Finding.from_path_match()"]
    C -->|No| F{content_detector?}
    F -->|Yes| G["content_detector.detect(patch)"]
    G --> H["For each ContentMatch: yield Finding.from_content_match()"]
    F -->|No| I[Next file_diff]
    E --> I
    H --> I
    I --> J["Iterator[Finding]"]
```

### Path Detection (`detectors/path.py`)

```mermaid
flowchart TD
    A["detect(change: FileChange)"] --> B["Collect paths: {old_path, new_path} - {None}"]
    B --> C[For each path, for each pattern]
    C --> D{"pattern.search(path)?"}
    D -->|Yes| E["PathMatch(pattern, path)"]
    D -->|No| F[Next pattern]
    E --> F
    F --> G["Return tuple[PathMatch, ...]"]
```

### Content Detection (`detectors/content.py`)

```mermaid
flowchart TD
    A["detect(patch: str)"] --> B[Split patch into lines]
    B --> C["For each line: _classify_line()"]
    C --> D{line type}
    D -->|+++ or ---| E["None (metadata)"]
    D -->|"@@"| F["None (hunk header)"]
    D -->|+| G["(ADDITION, line[1:])"]
    D -->|-| H["(DELETION, line[1:])"]
    D -->| | I["(CONTEXT, line[1:])"]
    D -->|else| J[None]
    G --> K[For classified lines, test each pattern]
    H --> K
    I --> K
    K --> L["Return tuple[ContentMatch, ...]"]
```

---

## Stage 5: Finding Construction

**Entry**: `Finding.from_path_match()` / `Finding.from_content_match()` in `models/findings.py`

```mermaid
flowchart TD
    subgraph PathMatch
        A1[PathMatch] --> A2[FileChange]
        A2 --> A3[Commit metadata]
        A3 --> A4["Finding(detector='path', commit_sha, commit_subject, author, timestamp, old_path, new_path, pattern, evidence=match.path)"]
    end

    subgraph ContentMatch
        B1[ContentMatch] --> B2[FileChange]
        B2 --> B3[Commit metadata]
        B3 --> B4["Finding(detector='content', commit_sha, commit_subject, author, timestamp, old_path, new_path, pattern, evidence=match.line)"]
    end
```

---

## Stage 6: Reporting

### Terminal Reporter (`reporting/terminal.py`)

```mermaid
flowchart TD
    A[For each finding] --> B["Print commit header (sha, subject, author, time)"]
    B --> C["Print detector badge (PATH/CONTENT)"]
    C --> D[Print pattern]
    D --> E["Print file paths (old → new)"]
    E --> F[Print evidence with line type indicator]
```

### JSON Reporter (`reporting/json.py`)

```json
{
  "findings": [
    {
      "detector": "content",
      "commit_sha": "abc123",
      "commit_subject": "Add config",
      "author": "User <email>",
      "timestamp": "2024-01-15T10:30:00Z",
      "old_path": null,
      "new_path": "config.env",
      "pattern": "PRIVATE_KEY=",
      "evidence": "PRIVATE_KEY=secret123"
    }
  ],
  "summary": {
    "total": 1,
    "by_detector": {"content": 1, "path": 0}
  }
}
```

---

## Data Flow Summary

| Stage | Input | Output | Key Function |
|-------|-------|--------|--------------|
| 1. Repo Prep | Path | Validated repo | `prepare_repository()` |
| 2. Ref Resolution | CLI args | `list[str]` refs | `_resolve_refs()` |
| 3. Traversal | Refs | `Iterator[CommitDiff]` | `iter_commit_diffs()` |
| 4. Scanning | `Iterator[CommitDiff]` | `Iterator[Finding]` | `ExposureScanner.scan()` |
| 5. Findings | Matches + metadata | `Finding` objects | `Finding.from_*_match()` |
| 6. Reporting | `list[Finding]` | stdout / JSON | `Reporter.report()` |

---

## Error Handling

| Stage | Failure Mode | Handling |
|-------|--------------|----------|
| Repo prep | Not a Git repo | `GitError` → CLI exit 1 |
| Repo prep | Partial clone | `GitError` with remediation hint |
| Repo prep | Shallow, no remote | `GitError` → CLI exit 1 |
| Traversal | Invalid ref | `GitError` from `git rev-list` |
| Diff extraction | Binary file | Empty patch, no crash |
| Detection | Malformed diff | Graceful skip (metadata filtered) |
| Reporting | I/O error | Propagate to CLI |
