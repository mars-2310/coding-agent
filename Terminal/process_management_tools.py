import os
from langgraph.prebuilt import ToolNode, tools_condition
from pathlib import Path
from langchain_core.tools import tool

WORKSPACE = Path.cwd().resolve()
current_dir = WORKSPACE

@tool
def ps():
  pass

@tool
def kill():
  pass

@tool
def top():
  pass

tools = [ps, kill, top]