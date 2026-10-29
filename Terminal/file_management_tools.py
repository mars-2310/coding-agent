import os
import re
import shutil
from fnmatch import fnmatch
from langchain_core.tools import tool
from Core.workspace import get_current_dir, resolve_safe_path, absolute_path, is_protected, is_safe_path
from Terminal.shell import truncate

# Directories grep never searches.
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules"}
MAX_FILE_BYTES = 1_000_000

def _destination(src, dest: str, overwrite: bool):
    """Resolve where src should land, following cp/mv rules. Returns (path, error)."""
    target = resolve_safe_path(dest)

    if target.is_dir():
        target = target / src.name

    if is_protected(target):
        return None, f"Error: {dest} is protected and cannot be written to"

    if target.exists():
        if target.is_dir():
            return None, f"Error: a directory already exists at {target}"
        if not overwrite:
            return None, f"Error: {target} already exists. Pass overwrite=True to replace it"

    return target, None


def _is_binary(path) -> bool:
    with open(path, "rb") as f:
        return b"\0" in f.read(1024)


@tool(parse_docstring=True)
def cp(src: str, dest: str, overwrite: bool = False) -> str:
    """Copy a file or directory to a new location inside the workspace.

    Args:
        src: File or directory to copy.
        dest: Where to copy it. If this is an existing directory, the copy goes inside it.
        overwrite: Whether to replace an existing file at the destination.
    """
    try:
        source = resolve_safe_path(src)
        if not source.exists():
            return f"Error: path not found: {src}"

        target, error = _destination(source, dest, overwrite)
        if error:
            return error

        if source.is_dir():
            if target.is_relative_to(source):
                return f"Error: cannot copy {src} into itself"
            # symlinks=True copies links as links, so nothing outside the workspace gets pulled in.
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target)
    except (PermissionError, OSError, shutil.Error) as e:
        return f"Error: {e}"

    return f"Copied {src} to {os.path.relpath(target, get_current_dir())}"


@tool(parse_docstring=True)
def mv(src: str, dest: str, overwrite: bool = False) -> str:
    """Move or rename a file or directory inside the workspace.

    Args:
        src: File or directory to move.
        dest: New path. If this is an existing directory, src is moved inside it.
        overwrite: Whether to replace an existing file at the destination.
    """
    try:
        # A symlink is moved as the link itself, not the file it points to.
        raw = absolute_path(src)
        if raw.is_symlink():
            source = resolve_safe_path(raw.parent) / raw.name
        else:
            source = resolve_safe_path(src)

        if not source.exists() and not source.is_symlink():
            return f"Error: path not found: {src}"

        if is_protected(source):
            return f"Error: {src} is protected and cannot be moved"

        if get_current_dir().is_relative_to(source):
            return f"Error: cannot move {src} because it is the workspace root, the current directory, or contains it"

        target, error = _destination(source, dest, overwrite)
        if error:
            return error

        if source.is_dir() and target.is_relative_to(source):
            return f"Error: cannot move {src} into itself"

        shutil.move(source, target)
    except (PermissionError, OSError, shutil.Error) as e:
        return f"Error: {e}"

    return f"Moved {src} to {os.path.relpath(target, get_current_dir())}"


@tool(parse_docstring=True)
def cat(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    """Read a text file and return its lines, each prefixed with its line number.

    Args:
        path: File to read.
        start_line: First line to return, counting from 1. Defaults to the start of the file.
        end_line: Last line to return, inclusive. Defaults to the end of the file.
    """
    try:
        target = resolve_safe_path(path)
        if not target.is_file():
            return f"Error: file not found: {path}"
        if _is_binary(target):
            return f"Error: {path} is a binary file"

        lines = target.read_text(errors="replace").splitlines()
    except (PermissionError, OSError) as e:
        return f"Error: {e}"

    if not lines:
        return f"{path} is empty"

    start = max(start_line or 1, 1)
    end = min(end_line or len(lines), len(lines))
    if start > end:
        return f"Error: line range {start}-{end} is empty; the file has {len(lines)} lines"

    numbered = [f"{i:>5}  {lines[i - 1]}" for i in range(start, end + 1)]
    return truncate("\n".join(numbered), max_lines=500)


@tool(parse_docstring=True)
def head(path: str, lines: int = 10) -> str:
    """Return the first lines of a text file, each prefixed with its line number.

    Args:
        path: File to read.
        lines: How many lines to return.
    """
    return cat.invoke({"path": path, "start_line": 1, "end_line": max(lines, 1)})


@tool(parse_docstring=True)
def grep(pattern: str, path: str = ".", file_glob: str = "*", ignore_case: bool = False, max_results: int = 100) -> str:
    """Search text files for lines matching a regular expression. Returns matches as 'file:line: text'.

    Args:
        pattern: Regular expression to search for, e.g. 'def \\w+' or 'TODO'.
        path: File or directory to search. Directories are searched recursively.
        file_glob: Only search files whose name matches this glob, e.g. '*.py'.
        ignore_case: Whether to ignore letter case when matching.
        max_results: Stop after this many matching lines.
    """
    try:
        regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as e:
        return f"Error: invalid regular expression: {e}"

    try:
        root = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"

    if root.is_file():
        files = [root]
    elif root.is_dir():
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            files += [os.path.join(dirpath, f) for f in sorted(filenames) if fnmatch(f, file_glob)]
    else:
        return f"Error: path not found: {path}"

    matches = []
    for file in files:
        try:
            # Skip symlinks that lead outside the workspace.
            if not is_safe_path(file):
                continue
            if os.path.getsize(file) > MAX_FILE_BYTES or _is_binary(file):
                continue
            with open(file, errors="replace") as f:
                for number, line in enumerate(f, start=1):
                    if regex.search(line):
                        shown = os.path.relpath(file, get_current_dir())
                        matches.append(f"{shown}:{number}: {line.rstrip()[:300]}")
                        if len(matches) >= max_results:
                            return "\n".join(matches) + f"\n... stopped after {max_results} results"
        except OSError:
            continue

    if not matches:
        return f"No matches for {pattern!r} in {path}"

    return "\n".join(matches)


tools = [cp, mv, cat, grep, head]
