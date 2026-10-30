import shutil
from langchain_core.tools import tool
from Core.workspace import (
    get_current_dir, set_current_dir, resolve_safe_path, absolute_path, is_protected,
)

@tool(parse_docstring=True)
def cd(path: str) -> str:
    """Change the agent's current directory, like the shell command cd.

    Every other tool resolves relative paths from the current directory, so after cd('src'), the path 'main.py' means src/main.py. The change lasts until the next cd. Only directories inside the workspace are allowed. Returns the new current directory, or an error if the directory doesn't exist or is outside the workspace.

    Args:
        path: Directory to switch to, relative to the current directory, e.g. 'src', '..' to go up one level, or an absolute path inside the workspace.
    """
    try:
        set_current_dir(path)
    except (FileNotFoundError, NotADirectoryError, PermissionError) as e:
        return f"Error: {e}"

    return f"Current directory changed to {get_current_dir()}"


@tool
def pwd() -> str:
    """Return the agent's current directory as an absolute path.

    Use this to check where relative paths will be resolved from, for example after several cd calls."""
    return str(get_current_dir())


@tool(parse_docstring=True)
def ls(path: str = ".") -> str:
    """List the files and directories in one directory, one name per line, sorted by name.

    Directory names end with '/'. Hidden entries such as .git are included. Only one level is shown; use file_tree to see nested folders, or find_files to search for a file by name.

    Args:
        path: Directory to list, relative to the current directory. Defaults to the current directory.
    """
    try:
        target = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"

    if not target.is_dir():
        return f"Error: directory not found: {path}"

    entries = sorted(target.iterdir(), key=lambda p: p.name)
    if not entries:
        return f"{path} is empty"

    return "\n".join(p.name + "/" if p.is_dir() else p.name for p in entries)


@tool(parse_docstring=True)
def mkdir(path: str) -> str:
    """Create a directory, including any missing parent directories, so 'src/utils/helpers' can be created in one call.

    Returns whether the directory was created or already existed. Fails if a file already exists at that path or the path is outside the workspace. You usually don't need this before write_file, which creates missing parent directories itself.

    Args:
        path: Directory to create, relative to the current directory.
    """
    try:
        target = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"

    if target.is_file():
        return f"Error: a file already exists at {path}"

    if target.is_dir():
        return f"Directory already exists: {path}"

    target.mkdir(parents=True)
    return f"Directory created: {path}"


@tool(parse_docstring=True)
def rm(path: str) -> str:
    """Permanently delete a file or directory. A directory is deleted together with everything inside it. This cannot be undone, so only delete what the task requires, and check the path with ls first.

    Deleting a symlink removes only the link, not the file it points to. Refuses to delete protected paths (.git, .env, .venv and anything inside them), the workspace root, the current directory or any folder containing it. To reverse your own edits to a file, use undo_edit instead of deleting it.

    Args:
        path: File or directory to delete, relative to the current directory.
    """
    # A symlink must be deleted as the link itself, so look at the path before resolving it.
    raw = absolute_path(path)
    if raw.is_symlink():
        try:
            link = resolve_safe_path(raw.parent) / raw.name
        except PermissionError as e:
            return f"Error: {e}"

        link.unlink()
        return f"Deleted symlink: {path}"

    try:
        target = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"

    if not target.exists():
        return f"Error: path not found: {path}"

    if get_current_dir().is_relative_to(target):
        return f"Error: cannot delete {path} because it is the workspace root, the current directory, or contains it"

    if is_protected(target):
        return f"Error: {path} is protected and cannot be deleted"

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    return f"Deleted: {path}"


tools = [cd, pwd, ls, mkdir, rm]
