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
    """Copy a file or directory to another location inside the workspace.

    Use this to duplicate a file before changing it, or to start a new file from an existing one. Directories are copied with everything inside them, and symlinks are copied as links. The original is left untouched. Nothing is changed if the destination already exists (unless overwrite is true), is a protected path such as .git or .env, or is inside the directory being copied. Returns the path of the new copy.

    Args:
        src: File or directory to copy, relative to the current directory.
        dest: Where to put the copy. If this is an existing directory, the copy goes inside it under the same name.
        overwrite: Replace an existing file at the destination. Directories are never replaced.
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

    Use this to rename a file or move it into another folder. A symlink is moved as the link itself, not the file it points to. Refuses to move protected paths (.git, .env, .venv), the current directory or any folder containing it, and will not move a directory into itself. Nothing is changed if the destination already exists, unless overwrite is true. Returns the new path. To undo, move it back.

    Args:
        src: File or directory to move, relative to the current directory.
        dest: New path. If this is an existing directory, src is moved inside it under the same name.
        overwrite: Replace an existing file at the destination. Directories are never replaced.
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
    """Read a text file and return its contents, with a line number before each line.

    Use this to look at a file before editing it or to check what it contains. For long files, read part of it with start_line and end_line. At most 500 lines are returned per call; longer output is cut with a note saying how many lines were left out. The line numbers are for reference only and are not part of the file. Binary files are refused.

    Args:
        path: File to read, relative to the current directory.
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
    """Return the first lines of a text file, each with its line number.

    A quick way to see how a file starts, e.g. its imports, a header comment or a CSV's column names, without reading all of it. Same output format as cat.

    Args:
        path: File to read, relative to the current directory.
        lines: How many lines from the top to return. Defaults to 10.
    """
    return cat.invoke({"path": path, "start_line": 1, "end_line": max(lines, 1)})


@tool(parse_docstring=True)
def grep(pattern: str, path: str = ".", file_glob: str = "*", ignore_case: bool = False, max_results: int = 100) -> str:
    """Search text files for lines matching a regular expression, and return each match as 'file:line: text'.

    Use this to find where something is defined or used, e.g. a function name, an error message or a TODO. Directories are searched recursively, skipping .git, .venv, __pycache__, node_modules, binary files and files over 1 MB. Paths in the results are relative to the current directory and can be passed straight to cat. Matching lines longer than 300 characters are shortened. Returns a 'No matches' message when nothing is found.

    Args:
        pattern: Python regular expression, e.g. 'def \\w+', 'import requests' or 'TODO'. Put a backslash before special characters such as ( . * to match them literally.
        path: File or directory to search. Defaults to the current directory.
        file_glob: Only search files whose name matches this glob, e.g. '*.py' or 'test_*'. Defaults to all files.
        ignore_case: Match regardless of letter case, so 'todo' also finds 'TODO'.
        max_results: Stop after this many matching lines. Defaults to 100.
    """
    try:
        regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as e:
        return f"Error: invalid regular expression: {e}"

    try:
        root = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"

    # Globs match file names, so drop any directory part the model adds, e.g. '**/*.py' -> '*.py'.
    name_glob = file_glob.rsplit("/", 1)[-1] or "*"

    if root.is_file():
        files = [root]
    elif root.is_dir():
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            files += [os.path.join(dirpath, f) for f in sorted(filenames) if fnmatch(f, name_glob)]
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
