from pathlib import Path

_WORKSPACE = Path.cwd().resolve()
_CURRENT_DIR = _WORKSPACE

def get_workspace() -> Path:
    """Return the absolute workspace root."""
    return _WORKSPACE



def get_current_dir() -> Path:
    """Returns the agent's current directory."""
    return _CURRENT_DIR



def set_current_dir(path: str | Path) -> None:
    """Change the agent's current directory to a safe existing directory."""
    global _CURRENT_DIR
    resolved = resolve_safe_path(path)

    if not resolved.exists():
        raise FileNotFoundError(f"Directory does not exist: {resolved}")

    if not resolved.is_dir():
        raise NotADirectoryError(f"Not a directory: {resolved}")

    _CURRENT_DIR = resolved



def resolve_path(path: str | Path = '.') -> Path:
    """Resolve a relative path against the agent's current directory."""
    candidate = Path(path).expanduser()

    if not candidate.is_absolute():
        candidate = _CURRENT_DIR / candidate

    return candidate.resolve()



def is_safe_path(path: str | Path) -> bool:
    """Check whether a path resolves inside the workspace."""
    try:
        resolve_path(path).relative_to(_WORKSPACE)
        return True
    except (ValueError, OSError, RuntimeError):
        return False



def resolve_safe_path(path: str | Path = '.') -> Path:
    """Resolve a path and raise if it falls outside the workspace. Tools should use this."""
    resolved = resolve_path(path)

    if not is_safe_path(resolved):
        raise PermissionError(f"Path is outside the workspace: {resolved}")

    return resolved



def absolute_path(path: str | Path) -> Path:
    """Make a path absolute against the agent's current directory without following symlinks."""
    candidate = Path(path).expanduser()

    if not candidate.is_absolute():
        candidate = _CURRENT_DIR / candidate

    return candidate



# Names that tools refuse to delete, move or write into.
PROTECTED_NAMES = {".git", ".env", ".venv"}

def is_protected(path: str | Path) -> bool:
    """Check whether a path is, or is inside, a protected file or directory."""
    try:
        parts = resolve_path(path).relative_to(_WORKSPACE).parts
    except ValueError:
        return False

    return bool(PROTECTED_NAMES.intersection(parts))
