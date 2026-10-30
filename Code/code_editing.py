# code_editing.py
# - write_file(path, content) -> str
# - edit_file(path, old_str, new_str) -> str
# - insert_lines(path, line: int, content) -> str
# - apply_patch(diff: str) -> str
# - undo_edit(path) -> str
# - tools = [...]

import os
from pathlib import Path
from langchain_core.tools import tool
from Core.schemas import WriteFileInput
from Core.workspace import get_current_dir, resolve_safe_path, is_protected
from Terminal.shell import run

# Previous contents of each file before an edit, newest last. None means the file didn't exist yet.
# Any tool that changes a file should call _save_backup first, so undo_edit can restore it.
_history: dict[Path, list[str | None]] = {}

def _save_backup(path: Path) -> None:
    previous = path.read_text() if path.is_file() else None
    _history.setdefault(path, []).append(previous)


@tool(args_schema=WriteFileInput)
def write_file(path: str, content: str, overwrite: bool = False) -> str:
    """Create a new file with the given content, or replace an existing file's entire content.

    Use this for new files. To change part of an existing file, use edit_file instead: it only touches the text you name, so it can't accidentally drop the rest of the file. Replacing an existing file requires overwrite=true. Missing parent directories are created. Protected paths such as .git and .env are refused. The previous version is saved, so undo_edit can reverse the write."""
    try:
        target = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"

    if is_protected(target):
        return f"Error: {path} is protected and cannot be written to"
    if target.is_dir():
        return f"Error: {path} is a directory"
    if target.exists() and not overwrite:
        return f"Error: {path} already exists. Pass overwrite=True to replace it, or use edit_file to change part of it"

    existed = target.exists()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _save_backup(target)
        target.write_text(content)
    except OSError as e:
        return f"Error: {e}"

    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    action = "Overwrote" if existed else "Created"
    return f"{action} {os.path.relpath(target, get_current_dir())} ({lines} lines)"


@tool(parse_docstring=True)
def insert_lines(path: str, line: int, content: str) -> str:
    """Insert new lines into an existing file before a given line number, without changing any existing lines.

    Use this to add code at a precise spot, e.g. a new import at line 1 or a new function at the end. Read the file first to get the right line number. A line break is added at the end of the inserted text if it is missing. undo_edit can reverse it.

    Args:
        path: File to insert into, relative to the current directory. It must already exist.
        line: Line number the new text goes before, counting from 1. Use one more than the file's line count to append at the end.
        content: Text to insert. It can span several lines.
    """
    try:
        target = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"

    if is_protected(target):
        return f"Error: {path} is protected and cannot be written to"
    if not target.is_file():
        return f"Error: file not found: {path}. Use write_file to create it"

    lines = target.read_text().splitlines(keepends=True)
    if not 1 <= line <= len(lines) + 1:
        return f"Error: line must be between 1 and {len(lines) + 1}; the file has {len(lines)} lines"

    # Make sure neither the inserted text nor the line before it runs into the next line.
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    new_text = content if content.endswith("\n") else content + "\n"

    _save_backup(target)
    lines[line - 1:line - 1] = [new_text]
    target.write_text("".join(lines))

    added = new_text.count("\n")
    return f"Inserted {added} line(s) into {path} at line {line}"


def _patch_paths(diff: str) -> list[str]:
    """Return the file paths a unified diff touches, without the a/ and b/ prefixes."""
    paths = []
    for line in diff.splitlines():
        if line.startswith(("--- ", "+++ ")):
            name = line[4:].split("\t")[0].strip()
            if name == "/dev/null":
                continue
            if name.startswith(("a/", "b/")):
                name = name[2:]
            if name not in paths:
                paths.append(name)
    return paths


@tool(parse_docstring=True)
def apply_patch(diff: str) -> str:
    """Apply a unified diff, the format 'git diff' prints, to one or more files at once.

    Use this for changes in several files or several places at once, when you can write the diff accurately. For a single change, edit_file is simpler and less error-prone. Paths in the diff headers are relative to the current directory. The diff's context lines must match the files exactly; if any part doesn't fit, nothing is changed and the error says which file failed. undo_edit reverses it, one file at a time.

    Args:
        diff: The full unified diff, including the '--- a/path' and '+++ b/path' header lines and the '@@' hunk lines.
    """
    paths = _patch_paths(diff)
    if not paths:
        return "Error: no '--- a/file' / '+++ b/file' headers found in the diff"

    targets = []
    for name in paths:
        try:
            target = resolve_safe_path(name)
        except PermissionError as e:
            return f"Error: {e}"
        if is_protected(target):
            return f"Error: {name} is protected and cannot be patched"
        targets.append(target)

    # --check first, so a patch that only partly fits changes nothing.
    check = run(["git", "apply", "--check", "--whitespace=nowarn", "-"], input=diff, cwd=get_current_dir())
    if check.startswith("Error:"):
        return f"Error: patch does not apply\n{check}"

    for target in targets:
        _save_backup(target)

    result = run(["git", "apply", "--whitespace=nowarn", "-"], input=diff, cwd=get_current_dir())
    if result.startswith("Error:"):
        return result

    return "Patched " + ", ".join(paths)


@tool(parse_docstring=True)
def undo_edit(path: str) -> str:
    """Undo the most recent change made to a file by write_file, edit_file, insert_lines or apply_patch, restoring its previous content.

    Call it again to step further back. If the change being undone created the file, the file is deleted. Only changes made by those tools during this run can be undone; changes made by run_python, format_code, mv or rm cannot.

    Args:
        path: File whose last change should be undone, relative to the current directory.
    """
    try:
        target = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"

    backups = _history.get(target)
    if not backups:
        return f"Error: no earlier version of {path} to restore"

    previous = backups.pop()
    if previous is None:
        # The change being undone created the file.
        if target.exists():
            target.unlink()
        return f"Undid the creation of {path}; the file was deleted"

    target.write_text(previous)
    return f"Restored {path} to its previous version ({len(backups)} older version(s) left)"


tools = [write_file, insert_lines, apply_patch, undo_edit]
