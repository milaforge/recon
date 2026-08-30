# Recon

Deleting a committed secret does not remove it from Git history.

Recon scans staged, unstaged, and untracked work before it is committed. It can also
search commits, branches, and tags to show what sensitive material was exposed and
where.

Run `recon scan` while developing, or `recon scan -a` for a comprehensive history
scan in CI.

## Start here

- [About Recon](docs/mission/README.md)
- [How to use Recon](docs/usage/README.md)
- [How to contribute](CONTRIBUTING.md)
