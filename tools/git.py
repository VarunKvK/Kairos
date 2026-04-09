"""
tools/git.py — Kairos Git Integration
Provides git-aware operations for the agent.

The agent calls these via the shell tool already,
but this dedicated tool gives cleaner output,
better error messages, and repo-aware context.

Operations:
    status      → current repo status
    log         → commit history
    diff        → show changes
    branches    → list branches
    info        → repo summary (branch + last commit + status)
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path


# ── Result Type ───────────────────────────────────────────────────────────────

@dataclass
class GitResult:
    """
    Returned by every git operation.
    Consistent structure makes it easy for the agent to parse.
    """
    output:  str   # The actual git output
    success: bool  # True if command succeeded
    message: str   # Human readable status message


# ── Core Runner ───────────────────────────────────────────────────────────────

def _run(args: list[str], cwd: str = None) -> GitResult:
    """
    Run a git command and return a GitResult.

    Args:
        args: git command parts e.g. ["log", "--oneline", "-5"]
        cwd:  working directory — defaults to current directory

    Never raises — all errors returned as GitResult(success=False)
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd or Path.cwd(),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            return GitResult(
                output=output or "(no output)",
                success=True,
                message="OK",
            )
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return GitResult(
                output=error,
                success=False,
                message=f"Git error: {error[:200]}",
            )

    except subprocess.TimeoutExpired:
        return GitResult(
            output="",
            success=False,
            message="Git command timed out after 30 seconds.",
        )
    except FileNotFoundError:
        return GitResult(
            output="",
            success=False,
            message="Git is not installed or not in PATH.",
        )
    except Exception as e:
        return GitResult(
            output="",
            success=False,
            message=f"Unexpected error: {e}",
        )


def _find_repo(path: str = None) -> str | None:
    """
    Find the git repo root from a given path.
    Returns the repo root path or None if not in a git repo.
    """
    check_path = Path(path) if path else Path.cwd()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=check_path,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


# ── Git Operations ────────────────────────────────────────────────────────────

def git_status(repo_path: str = None) -> GitResult:
    """
    Get the current git status of a repository.
    Shows staged, unstaged, and untracked files.

    Args:
        repo_path: path to repo — defaults to current directory
    """
    repo = _find_repo(repo_path)
    if not repo:
        return GitResult("", False, "Not a git repository.")

    return _run(["status", "--short"], cwd=repo)


def git_log(
    repo_path: str = None,
    limit:     int = 10,
    since:     str = None,
    author:    str = None,
) -> GitResult:
    """
    Get commit history.

    Args:
        repo_path: path to repo
        limit:     max number of commits to show (default 10)
        since:     time filter e.g. "today", "1 week ago", "2024-01-01"
        author:    filter by author name or email
    """
    repo = _find_repo(repo_path)
    if not repo:
        return GitResult("", False, "Not a git repository.")

    args = [
        "log",
        f"--max-count={limit}",
        "--pretty=format:%h | %ad | %an | %s",  # hash | date | author | message
        "--date=short",
    ]

    if since:
        args.append(f"--since={since}")

    if author:
        args.append(f"--author={author}")

    return _run(args, cwd=repo)


def git_diff(
    repo_path: str = None,
    staged:    bool = False,
    commit:    str = None,
) -> GitResult:
    """
    Show changes in the repository.

    Args:
        repo_path: path to repo
        staged:    if True, show staged changes (git diff --cached)
        commit:    specific commit hash to diff against HEAD
    """
    repo = _find_repo(repo_path)
    if not repo:
        return GitResult("", False, "Not a git repository.")

    if commit:
        args = ["diff", commit, "HEAD"]
    elif staged:
        args = ["diff", "--cached"]
    else:
        args = ["diff"]

    result = _run(args, cwd=repo)

    # Diffs can be huge — truncate to keep LLM context manageable
    if len(result.output) > 3000:
        result.output = result.output[:3000] + "\n... [diff truncated — too large]"

    return result


def git_branches(repo_path: str = None) -> GitResult:
    """
    List all branches and show current branch.

    Args:
        repo_path: path to repo
    """
    repo = _find_repo(repo_path)
    if not repo:
        return GitResult("", False, "Not a git repository.")

    return _run(["branch", "-a"], cwd=repo)


def git_info(repo_path: str = None) -> GitResult:
    """
    Get a full summary of the repo state.
    Combines branch, last commit, and status into one output.
    Most useful for giving the agent quick repo context.

    Args:
        repo_path: path to repo
    """
    repo = _find_repo(repo_path)
    if not repo:
        return GitResult("", False, "Not a git repository.")

    # Get current branch
    branch = _run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)

    # Get last commit
    last_commit = _run(
        ["log", "-1", "--pretty=format:%h | %ad | %an | %s", "--date=short"],
        cwd=repo
    )

    # Get status summary
    status = _run(["status", "--short"], cwd=repo)

    # Get remote URL
    remote = _run(["remote", "get-url", "origin"], cwd=repo)

    # Combine into one clean output
    lines = [
        f"Repo:          {repo}",
        f"Branch:        {branch.output}",
        f"Last commit:   {last_commit.output}",
        f"Remote:        {remote.output if remote.success else 'no remote'}",
        f"Changed files: {status.output if status.output != '(no output)' else 'none'}",
    ]

    return GitResult(
        output="\n".join(lines),
        success=True,
        message="OK",
    )


def git_commit_message(repo_path: str = None) -> GitResult:
    """
    Generate context for writing a commit message.
    Returns staged diff + list of changed files.
    The agent uses this to write a meaningful commit message.

    Args:
        repo_path: path to repo
    """
    repo = _find_repo(repo_path)
    if not repo:
        return GitResult("", False, "Not a git repository.")

    # Get staged files
    staged_files = _run(["diff", "--cached", "--name-only"], cwd=repo)

    if staged_files.output == "(no output)":
        return GitResult(
            "",
            False,
            "No staged changes. Run 'git add' first."
        )

    # Get staged diff (truncated)
    staged_diff = _run(["diff", "--cached", "--stat"], cwd=repo)

    output = (
        f"Staged files:\n{staged_files.output}\n\n"
        f"Change summary:\n{staged_diff.output}"
    )

    return GitResult(output=output, success=True, message="OK")