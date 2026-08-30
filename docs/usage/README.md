# How to use Recon

`recon scan` scans staged changes, unstaged changes, and untracked files that are not
excluded by `.gitignore`. In an interactive terminal it opens the filterable report
browser by default; use `--no-tui` for stable human-readable output or `-f json` for
automation.

```bash
uv run recon scan
```

`recon scan -a` first fetches every configured remote, then scans current changes and
all reachable local branches, remote-tracking branches, and tags. This is the safest
CI mode when the checkout does not retain a reliable merge base:

```bash
recon scan -a --no-tui
# or for machine processing
recon scan -a -f json
```

Plain `recon scan` is optimized for local development and pre-commit use. Most CI
checkouts have a clean working tree, so CI should use `-a` until a merge-base-aware
CI scan mode is available.

- [CLI commands and options](../../AGENTS.md#cli-commands)
- [Mission and current roadmap](../mission/README.md)
