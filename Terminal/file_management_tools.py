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
  pass

@tool
def mv() -> str:
  pass

@tool
def cat(path: str = ".") -> list[str]:
  pass

@tool
def grep():
   pass

@tool
def head():
   pass

tools = [cp, mv, cat, grep, head]