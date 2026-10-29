import shutil
from langchain_core.tools import tool
from Core.workspace import (
    get_current_dir, set_current_dir, resolve_safe_path, absolute_path, is_protected,
)

@tool
def cd(path: str) -> str:
    """Change the agent's working directory within its workspace."""
    try:
        set_current_dir(path)
    except (FileNotFoundError, NotADirectoryError, PermissionError) as e:
        return f"Error: {e}"

    return f"Current directory changed to {get_current_dir()}"


@tool
def pwd() -> str:
    """Get the agent's current working directory."""
    return str(get_current_dir())


@tool
def ls(path: str = ".") -> str:
    """List the contents of a directory, one entry per line. Directories end with '/'."""
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


@tool
def mkdir(path: str) -> str:
    """Create a directory inside the workspace, including any missing parent directories."""
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


@tool
def rm(path: str) -> str:
    """Delete a file or directory inside the workspace. Directories are deleted with all their contents. Cannot be undone."""
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
