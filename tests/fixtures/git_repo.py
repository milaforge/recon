"""
Git repository fixtures for integration tests.

Uses actual `git` subprocess calls to create real repositories with
real history. This validates our code against Git's actual behavior.
"""

import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def run_git(*args: str, cwd: Path | str) -> str:
    """Execute a Git command and return stdout."""
    # Disable global gitignore to allow adding .env files in tests
    git_args = ["git", "-c", "core.excludesfile=", *args]
    result = subprocess.run(
        git_args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or f"Git command failed: git {' '.join(args)}"
        raise RuntimeError(message)

    return result.stdout


def run_shell(*args: str, cwd: Path) -> str:
    """Execute a shell command and return stdout."""
    result = subprocess.run(
        list(args),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or f"Shell command failed: {' '.join(args)}"
        raise RuntimeError(message)

    return result.stdout


@contextmanager
def temp_git_repo() -> Iterator[Path]:
    """
    Create a temporary Git repository.

    Yields the repository path. The repo is initialized with:
    - main branch
    - user.name = "Test User"
    - user.email = "test@example.com"
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        repo.mkdir()

        run_git("init", "-b", "main", cwd=repo)
        run_git("config", "user.name", "Test User", cwd=repo)
        run_git("config", "user.email", "test@example.com", cwd=repo)

        yield repo


@contextmanager
def temp_bare_repo() -> Iterator[Path]:
    """Create a temporary bare Git repository (for use as remote)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "remote.git"
        repo.mkdir()

        run_git("init", "--bare", cwd=repo)

        yield repo


def commit(repo: Path, message: str, *, allow_empty: bool = False) -> str:
    """Create a commit and return its SHA."""
    if allow_empty:
        run_git("commit", "--allow-empty", "-m", message, cwd=repo)
    else:
        run_git("add", ".", cwd=repo)
        run_git("commit", "-m", message, cwd=repo)

    return run_git("rev-parse", "HEAD", cwd=repo).strip()


def write_file(repo: Path, path: str, content: str) -> None:
    """Write a file relative to repo root and stage it."""
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    run_git("add", path, cwd=repo)


def delete_file(repo: Path, path: str) -> None:
    """Delete a file and stage the deletion."""
    target = repo / path
    if target.exists():
        target.unlink()
    run_git("add", "-A", cwd=repo)


def rename_file(repo: Path, old_path: str, new_path: str) -> None:
    """Rename a file using git mv."""
    # Ensure destination directory exists
    (repo / new_path).parent.mkdir(parents=True, exist_ok=True)
    run_git("mv", old_path, new_path, cwd=repo)


def create_branch(repo: Path, name: str) -> None:
    """Create and checkout a new branch."""
    run_git("checkout", "-b", name, cwd=repo)


def checkout(repo: Path, ref: str) -> None:
    """Checkout a ref."""
    run_git("checkout", ref, cwd=repo)


def get_head_sha(repo: Path) -> str:
    """Return current HEAD SHA."""
    return run_git("rev-parse", "HEAD", cwd=repo).strip()


def get_remote_branches(repo: Path, remote: str = "origin") -> list[tuple[str, str]]:
    """Return (branch_name, sha) for all branches on a remote."""
    output = run_git("ls-remote", "--heads", remote, cwd=repo)
    branches = []
    for line in output.splitlines():
        if not line.strip():
            continue
        sha, ref = line.split("\t", 1)
        if ref.startswith("refs/heads/"):
            branches.append((ref.removeprefix("refs/heads/"), sha))
    return branches


def get_local_branches(repo: Path) -> list[str]:
    """Return all local branch names."""
    output = run_git("for-each-ref", "--format=%(refname:short)", "refs/heads/", cwd=repo)
    return [b for b in output.splitlines() if b]


def get_local_remote_refs(repo: Path) -> list[str]:
    """Return all local remote-tracking refs."""
    output = run_git("for-each-ref", "--format=%(refname)", "refs/remotes/", cwd=repo)
    return [r for r in output.splitlines() if r]


def get_local_tags(repo: Path) -> list[str]:
    """Return all local tag refs."""
    output = run_git("for-each-ref", "--format=%(refname)", "refs/tags/", cwd=repo)
    return [t for t in output.splitlines() if t]


def is_shallow(repo: Path) -> bool:
    """Return True if repository is shallow."""
    return run_git("rev-parse", "--is-shallow-repository", cwd=repo).strip() == "true"


def make_shallow(repo: Path, depth: int = 1) -> None:
    """Make a repository shallow (for testing shallow detection)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        shallow = Path(tmpdir) / "shallow"
        run_git("clone", "--depth", str(depth), "--no-single-branch", f"file://{repo}", str(shallow), cwd=Path.cwd())
        import shutil
        shutil.rmtree(repo / ".git")
        shutil.move(shallow / ".git", repo / ".git")


def push_to_remote(working: Path, remote: Path, branch: str = "main") -> None:
    """Push a branch from working repo to bare remote."""
    # Check if remote already exists
    remotes = run_git("remote", cwd=working).splitlines()
    if "origin" not in remotes:
        run_git("remote", "add", "origin", str(remote), cwd=working)
    run_git("push", "origin", branch, cwd=working)


def clone_repo(remote: Path, target: Path) -> None:
    """Clone a bare repository."""
    run_git("clone", str(remote), str(target))


# ──────────────────────────────────────────────────────────────────────
# Scenario builders — common historical patterns
# ──────────────────────────────────────────────────────────────────────

def build_linear_history(repo: Path) -> list[str]:
    """
    Build a linear history:
      C1: initial
      C2: add .env
      C3: modify .env
      C4: rename .env -> config/.env
      C5: delete config/.env

    Returns list of commit SHAs in order.
    """
    shas = []

    write_file(repo, "README.md", "# Project\n")
    shas.append(commit(repo, "initial"))

    write_file(repo, ".env", "PRIVATE_KEY=secret1\n")
    shas.append(commit(repo, "add .env"))

    write_file(repo, ".env", "PRIVATE_KEY=secret2\n")
    shas.append(commit(repo, "modify .env"))

    rename_file(repo, ".env", "config/.env")
    shas.append(commit(repo, "rename .env -> config/.env"))

    delete_file(repo, "config/.env")
    shas.append(commit(repo, "delete config/.env"))

    return shas


def build_branch_with_secret(repo: Path) -> tuple[str, str]:
    """
    Build:
      main: C1 -> C2 (clean)
      feature: C1 -> C2 -> C3 (add secret) -> C4 (remove secret)

    Returns (main_head_sha, feature_head_sha)
    """
    write_file(repo, "README.md", "# Project\n")
    commit(repo, "initial")

    write_file(repo, "config.json", '{"key": "value"}\n')
    main_sha = commit(repo, "add config")

    create_branch(repo, "feature")

    write_file(repo, "secrets.json", '{"api_key": "secret123"}\n')
    commit(repo, "add secrets")

    delete_file(repo, "secrets.json")
    feature_sha = commit(repo, "remove secrets")

    checkout(repo, "main")

    return main_sha, feature_sha


def build_shared_commit(repo: Path) -> tuple[str, str, str]:
    """
    Build:
      A -- B -- C (main)
           \
            D (feature)

    Commit B is reachable from both main and feature.
    Returns (main_sha, feature_sha, shared_sha)
    """
    write_file(repo, "a.txt", "a\n")
    commit(repo, "A")

    write_file(repo, "b.txt", "SECRET=shared\n")
    shared_sha = commit(repo, "B (shared)")

    write_file(repo, "c.txt", "c\n")
    main_sha = commit(repo, "C")

    checkout(repo, shared_sha)
    create_branch(repo, "feature")

    write_file(repo, "d.txt", "d\n")
    feature_sha = commit(repo, "D")

    checkout(repo, "main")

    return main_sha, feature_sha, shared_sha


def build_merge_history(repo: Path) -> tuple[str, str, str, str]:
    """Build two diverged branches and merge feature into main."""
    write_file(repo, "README.md", "# Synthetic project\n")
    root_sha = commit(repo, "root")

    create_branch(repo, "feature")
    write_file(repo, "feature.env", "SYNTHETIC_TOKEN=feature-only-value\n")
    feature_sha = commit(repo, "feature exposure")

    checkout(repo, "main")
    write_file(repo, "main.txt", "main-side change\n")
    main_sha = commit(repo, "main change")
    run_git("merge", "--no-ff", "feature", "-m", "merge feature", cwd=repo)
    merge_sha = get_head_sha(repo)
    return root_sha, main_sha, feature_sha, merge_sha


def build_unusual_path_history(repo: Path) -> tuple[str, str]:
    """Add and delete a synthetic exposure under a space/non-ASCII path."""
    path = "config files/秘密 🔐.env"
    write_file(repo, path, "SYNTHETIC_TOKEN=unusual-path-value\n")
    added_sha = commit(repo, "add unusual path")
    delete_file(repo, path)
    deleted_sha = commit(repo, "delete unusual path")
    return added_sha, deleted_sha


def build_remote_with_branches(remote: Path, working: Path) -> list[tuple[str, str]]:
    """
    Set up a bare remote with multiple branches pushed from working repo.

    Returns list of (branch_name, sha) that were pushed.
    """
    # main
    write_file(working, "README.md", "# Project\n")
    commit(working, "initial")

    write_file(working, "main.txt", "main content\n")
    main_sha = commit(working, "main commit")

    # feature/busd
    create_branch(working, "feature/busd")
    write_file(working, "busd.txt", "busd content\n")
    busd_sha = commit(working, "busd commit")

    # feature/security-config
    checkout(working, "main")
    create_branch(working, "feature/security-config")
    write_file(working, "security.txt", "security content\n")
    security_sha = commit(working, "security commit")

    # Push all to remote
    push_to_remote(working, remote, "main")
    push_to_remote(working, remote, "feature/busd")
    push_to_remote(working, remote, "feature/security-config")

    return [
        ("main", main_sha),
        ("feature/busd", busd_sha),
        ("feature/security-config", security_sha),
    ]
