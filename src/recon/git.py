import subprocess
import sys
from pathlib import Path

import questionary


def run_git(*args: str) -> str:
    """Run a Git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)

        raise RuntimeError(f"Git command failed with exit code {result.returncode}")

    return result.stdout


def ensure_git_repository() -> None:
    """Ensure the current directory is inside a Git working tree."""
    try:
        result = run_git("rev-parse", "--is-inside-work-tree")
    except RuntimeError as exc:
        raise RuntimeError("Not inside a Git repository.") from exc

    if result.strip() != "true":
        raise RuntimeError("Not inside a Git working tree.")


def get_remotes() -> list[str]:
    """Return all configured Git remotes."""
    return [
        remote.strip() for remote in run_git("remote").splitlines() if remote.strip()
    ]


def get_remote_branches(
    remote: str,
) -> list[tuple[str, str]]:
    """
    Return every branch advertised by a remote.

    Each item is:

        (branch_name, commit_sha)
    """
    output = run_git(
        "ls-remote",
        "--heads",
        remote,
    )

    branches = []

    for line in output.splitlines():
        if not line.strip():
            continue

        sha, ref = line.split("\t", 1)

        if not ref.startswith("refs/heads/"):
            continue

        branch = ref.removeprefix("refs/heads/")

        branches.append((branch, sha))

    return branches


def fetch_branch(
    remote: str,
    branch: str,
    expected_sha: str,
) -> int:
    """
    Fetch one branch and verify its complete reachable history.

    Returns the number of reachable commits.
    """
    local_ref = f"refs/remotes/{remote}/{branch}"

    run_git(
        "fetch",
        remote,
        f"refs/heads/{branch}:{local_ref}",
    )

    verify_ref(local_ref, expected_sha)

    commit_count = verify_reachable_history(local_ref)

    return commit_count


def verify_ref(
    local_ref: str,
    expected_sha: str,
) -> None:
    """Verify that a local ref points to the expected remote commit."""
    actual_sha = run_git(
        "rev-parse",
        local_ref,
    ).strip()

    if actual_sha != expected_sha:
        raise RuntimeError(
            f"Fetch verification failed for {local_ref}:\n"
            f"  expected: {expected_sha}\n"
            f"  actual:   {actual_sha}"
        )

    # Confirm the commit object exists locally.
    run_git(
        "cat-file",
        "-e",
        f"{expected_sha}^{{commit}}",
    )


def get_reachable_commits(ref: str) -> set[str]:
    """Return every commit reachable from a ref."""
    output = run_git(
        "rev-list",
        "--full-history",
        ref,
    )

    return {commit.strip() for commit in output.splitlines() if commit.strip()}


def verify_reachable_history(ref: str) -> int:
    """
    Verify that every commit reachable from a ref exists locally.

    Returns the number of reachable commits.
    """
    commits = get_reachable_commits(ref)

    for commit in commits:
        run_git(
            "cat-file",
            "-e",
            f"{commit}^{{commit}}",
        )

    return len(commits)


def fetch_remote_branches(
    remote: str,
    branches: list[tuple[str, str]],
) -> None:
    """Fetch and verify a collection of branches from one remote."""
    print(f"\nRemote: {remote}")
    print(f"Branches selected: {len(branches)}\n")

    total_commits = 0

    for branch, expected_sha in branches:
        print(f"  {branch}")

        commit_count = fetch_branch(
            remote,
            branch,
            expected_sha,
        )

        total_commits += commit_count

        print(f"    ✓ {expected_sha[:12]} — {commit_count} reachable commits")

    # Fetch tags as well. Tags can point to historical commits that aren't
    # reachable from the selected branches.
    run_git(
        "fetch",
        remote,
        "--tags",
    )

    print(f"\n  Verified {len(branches)} branches / {total_commits} reachable commits.")


def fetch() -> None:
    """Interactively select branches to fetch."""
    ensure_git_repository()

    remotes = get_remotes()

    if not remotes:
        print("No Git remotes configured.")
        return

    for remote in remotes:
        unshallow(remote)

        branches = get_remote_branches(remote)

        if not branches:
            print(f"\nRemote: {remote}")
            print("  No branches found.")
            continue

        choices = [
            questionary.Choice(
                title=branch,
                value=(branch, sha),
            )
            for branch, sha in branches
        ]

        selected = questionary.checkbox(
            f"Select branches to fetch from {remote}:",
            choices=choices,
        ).ask()

        if selected is None:
            print("\nCancelled.")
            return

        if not selected:
            print(f"\nNo branches selected from {remote}.")
            continue

        fetch_remote_branches(remote, selected)

    print("\nFetch complete.")


def fetch_all() -> None:
    """Fetch every branch from every configured remote."""
    ensure_git_repository()

    remotes = get_remotes()

    if not remotes:
        print("No Git remotes configured.")
        return

    for remote in remotes:
        unshallow(remote)

        branches = get_remote_branches(remote)

        if not branches:
            print(f"\nRemote: {remote}")
            print("  No branches found.")
            continue

        fetch_remote_branches(
            remote,
            branches,
        )

    print("\nFetch complete.")


def normalize_path(path: str) -> str:
    """Normalize a Git path for comparison."""
    return path.replace("\\", "/").strip("/")


def path_matches(
    changed_path: str,
    targets: list[str],
) -> bool:
    """Return True if a changed path matches one of the targets."""
    changed_path = normalize_path(changed_path)

    for target in targets:
        target = normalize_path(target)

        if changed_path == target:
            return True

        if changed_path.startswith(target + "/"):
            return True

        if Path(changed_path).name == target:
            return True

    return False


def get_commit_metadata(commit: str) -> str:
    """Return concise metadata for a commit."""
    return run_git(
        "show",
        "-s",
        "--format=%h | %ad | %an | %s",
        "--date=iso",
        commit,
    ).strip()


def history_exposed_secrets(
    targets: list[str],
) -> None:
    """
    historical secret-exposure detector

    Search the complete Git history of selected branches for evidence that sensitive files or secret-like strings were ever committed, modified, deleted, or otherwise exposed.
    """
    ensure_git_repository()

    print("Searching Git history for:")

    for target in targets:
        print(f"  {target}")

    commits = run_git(
        "rev-list",
        "--all",
        "--full-history",
    ).splitlines()

    print(f"\nScanning {len(commits)} commits...\n")

    findings: list[tuple[str, str, str]] = []

    for commit in commits:
        output = run_git(
            "diff-tree",
            "-r",
            "--root",
            "-m",
            "--no-commit-id",
            "--name-status",
            commit,
        )

        for line in output.splitlines():
            if not line.strip():
                continue

            parts = line.split("\t")

            status = parts[0]
            changed_paths = parts[1:]

            for changed_path in changed_paths:
                if path_matches(changed_path, targets):
                    findings.append(
                        (
                            commit,
                            status,
                            changed_path,
                        )
                    )

    if not findings:
        print("No matching historical files found.")
        return

    print("=" * 80)
    print(f"FOUND {len(findings)} MATCHES")
    print("=" * 80)

    for commit, status, path in findings:
        print(f"\n{get_commit_metadata(commit)}")
        print(f"  {status:<4} {path}")

    print("\nDone.")


def is_shallow_repository() -> bool:
    """Return True if the current repository is shallow."""
    return (
        run_git(
            "rev-parse",
            "--is-shallow-repository",
        ).strip()
        == "true"
    )


def unshallow(remote: str) -> None:
    """Convert a shallow repository into a complete repository."""
    if not is_shallow_repository():
        return

    print("Repository is shallow.")
    print(f"Unshallowing from {remote}...")

    run_git(
        "fetch",
        "--unshallow",
        remote,
    )

    if is_shallow_repository():
        raise RuntimeError("Repository is still shallow after --unshallow.")

    print("Repository is now complete.")
