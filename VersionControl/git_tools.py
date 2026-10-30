# - git_status() -> str
# - git_diff(path=None) -> str
# - git_log(n: int = 10) -> str
# - git_commit(message: str) -> str
# - git_branch(name: str) -> str
# - git_checkout(ref: str) -> str
# - tools = [...]

from langchain_core.tools import tool
from Core.workspace import PROTECTED_NAMES, get_current_dir, resolve_safe_path
from Terminal.shell import run

def _git(*args: str, **kwargs) -> str:
    return run(["git", *args], cwd=get_current_dir(), **kwargs)


def _invalid_ref(ref: str) -> bool:
    """Reject refs that git would read as an option, like '-f' or '--hard'."""
    return not ref or ref.startswith("-") or any(c.isspace() for c in ref)


@tool
def git_status() -> str:
    """Show the current branch and which files have changed since the last commit.

    Each file line starts with a two-character code: the first character is the staged state, the second the unstaged state. 'M' means modified, 'A' added, 'D' deleted, and '??' untracked (a new file git doesn't know about yet). The first line shows the branch and, if there is a remote, how far ahead or behind it is. Use this before git_commit to see what would be committed."""
    output = _git("status", "--short", "--branch")
    if output.startswith("Error:") and "not a git repository" in output:
        return "Error: the current directory is not inside a git repository"
    return output


@tool(parse_docstring=True)
def git_diff(path: str | None = None, staged: bool = False) -> str:
    """Show uncommitted changes to tracked files as a unified diff, where lines starting with '-' were removed and lines starting with '+' were added.

    Use this to review your own edits before committing, or to see what changed in a file. New untracked files are not included; git_status lists them. Returns 'No changes' when there is nothing to show.

    Args:
        path: Only show changes to this file or directory. Defaults to the whole repository.
        staged: If true, show changes already staged for the next commit. If false, show changes not yet staged.
    """
    args = ["diff", "--no-color"]
    if staged:
        args.append("--cached")

    if path:
        try:
            args += ["--", str(resolve_safe_path(path))]
        except PermissionError as e:
            return f"Error: {e}"

    output = _git(*args)
    return output or "No changes"


@tool(parse_docstring=True)
def git_log(n: int = 10) -> str:
    """Show the most recent commits, newest first, one per line: short hash, date, author and the first line of the message.

    Use this to see recent history, or to get a commit hash to pass to git_checkout.

    Args:
        n: Number of commits to show, from 1 to 100. Defaults to 10.
    """
    n = min(max(n, 1), 100)
    output = _git("log", f"-{n}", "--no-color", "--date=short", "--pretty=format:%h %ad %an  %s")
    if output.startswith("Error:") and "does not have any commits" in output:
        return "No commits yet"
    return output


@tool(parse_docstring=True)
def git_commit(message: str, paths: list[str] | None = None) -> str:
    """Stage changes and save them as a new commit with the given message.

    Only commit when the task asks for it or the user has agreed. Without paths, every change is committed, including new files; pass paths to commit only some of them. Files listed in .gitignore and protected files such as .env are never committed, and the result says if any were skipped. Returns how many files were committed, or 'Nothing to commit'.

    Args:
        message: Commit message: a short summary line in the imperative mood, e.g. 'Fix crash when the config file is empty', optionally followed by a blank line and more detail.
        paths: Files or directories to commit, relative to the current directory. Defaults to every change in the repository.
    """
    if not message.strip():
        return "Error: commit message is empty"

    if paths:
        try:
            targets = [str(resolve_safe_path(p)) for p in paths]
        except PermissionError as e:
            return f"Error: {e}"
        added = _git("add", "--", *targets)
    else:
        added = _git("add", "--all")
    if added.startswith("Error:"):
        return added

    # Never commit secrets or environment folders, even if .gitignore misses them.
    staged = _git("diff", "--cached", "--name-only", max_lines=None).splitlines()
    blocked = [f for f in staged if PROTECTED_NAMES.intersection(f.split("/"))]
    if blocked:
        _git("reset", "--quiet", "--", *blocked)
        staged = [f for f in staged if f not in blocked]
    skipped = f" Skipped protected files: {', '.join(blocked)}." if blocked else ""

    if not staged:
        return "Nothing to commit." + skipped

    output = _git("commit", "--quiet", "-m", message)
    if output.startswith("Error:"):
        return output
    return f"Committed {len(staged)} file(s): {message.splitlines()[0]}.{skipped}"


@tool(parse_docstring=True)
def git_branch(name: str | None = None) -> str:
    """Create a new branch at the current commit, or list all branches if no name is given (the current branch is marked with '*').

    Creating a branch does not switch to it; call git_checkout afterwards. Use a branch to keep experimental changes separate from the main branch.

    Args:
        name: Name for the new branch, e.g. 'fix-login-bug'. Use letters, numbers, '-', '_' and '/', with no spaces. Leave it out to list branches.
    """
    if name is None:
        return _git("branch", "--no-color")

    if _invalid_ref(name) or _git("check-ref-format", "--branch", name).startswith("Error:"):
        return f"Error: invalid branch name: {name!r}"

    return _git("branch", name) or f"Created branch {name}"


@tool(parse_docstring=True)
def git_checkout(ref: str) -> str:
    """Switch to another branch, or to a commit or tag in detached (read-only) mode.

    Use this to move between branches, e.g. after git_branch. It never discards work: if uncommitted changes would be overwritten, git refuses and the error lists the files, so commit them first. To look at an old version, pass a commit hash from git_log, then switch back to a branch before making changes.

    Args:
        ref: Branch name, tag or commit hash to switch to.
    """
    if _invalid_ref(ref):
        return f"Error: invalid ref: {ref!r}"

    # git switch only ever changes branches, unlike git checkout, which can also
    # overwrite files (e.g. 'git checkout .' discards every uncommitted change).
    output = _git("switch", ref)
    if output.startswith("Error:") and ("invalid reference" in output or "a branch is expected" in output):
        output = _git("switch", "--detach", ref)

    if output.startswith("Error:"):
        return output
    return f"Switched to {ref}"


tools = [git_status, git_diff, git_log, git_commit, git_branch, git_checkout]
