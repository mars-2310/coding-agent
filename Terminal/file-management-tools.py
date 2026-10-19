import os
from langgraph.prebuilt import ToolNode, tools_condition
from pathlib import Path
from langchain_core.tools import tool

WORKSPACE = Path.cwd().resolve()
current_dir = WORKSPACE

def resolve_path(path: str = '.') -> str:
    """Resolve a path relative to the agent's current directory."""

    target = (current_dir / path).resolve()
    if not target.is_relative_to(WORKSPACE):
       raise PermissionError("Access outside workspace denied")

    return target

@tool
def cp(src: str, dest: str) -> str:
    """Copt the file from src to dest."""
    global current_dir

    target = resolve_path(dest)

    if not target.is_dir():
        raise NotADirectoryError(f"Directory not found: {dest}")

    current_dir = target
    return f"Current directory changed to {current_dir}"


@tool
def pwd() -> str:
  """Get the agent's current working directory."""
  return str(current_dir)

@tool
def ls(path: str = ".") -> list[str]:
  """List the folder contents of current directory."""
  target = resolve_path(path)

  if not target.is_dir():
     raise NotADirectoryError(f"Directory not found: {path}")

  return os.listdir(target)

@tool
def mkdir():
   pass

@tool
def rm():
   pass

tools = [cd, pwd, ls, mkdir, rm]