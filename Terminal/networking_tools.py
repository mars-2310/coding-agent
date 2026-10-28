import os
from langgraph.prebuilt import ToolNode, tools_condition
from pathlib import Path
from langchain_core.tools import tool

WORKSPACE = Path.cwd().resolve()
current_dir = WORKSPACE

@tool
def ping():
  pass

@tool
def ipconfig():
  pass

@tool
def netstat():
  pass

tools = [ping, ipconfig, netstat]