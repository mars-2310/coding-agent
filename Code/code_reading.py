# code_reading.py
# - read_file(path, start_line=None, end_line=None) -> str
# - find_files(pattern: str, path=".") -> list[str]
# - search_code(pattern: str, path=".", file_glob="*") -> list[str]
# - file_tree(path=".", depth=2) -> str
# - get_symbols(path) -> list[str]
# - tools = [...]
#
# read_file and search_code reuse the Terminal cat and grep tools. Bind either these or those
# to the agent, not both: two tools that do the same thing confuse a small model.

import ast
import os
from fnmatch import fnmatch
from langchain_core.tools import tool
from Core.schemas import ReadFileInput, SearchInput
from Core.workspace import get_current_dir, resolve_safe_path, is_safe_path
from Terminal.file_management_tools import cat, grep, SKIP_DIRS
from Terminal.shell import truncate

@tool(args_schema=ReadFileInput)
def read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    """Read a text file and return its contents, with a line number before each line.

    Use this before editing a file, so that edits are based on its exact current text. For long files, read a range with start_line and end_line instead of the whole file; at most 500 lines are returned per call. The line numbers are for reference only and are not part of the file's text. Binary files are refused."""
    return cat.invoke({"path": path, "start_line": start_line, "end_line": end_line})


@tool(args_schema=SearchInput)
def search_code(query: str, path: str = ".", file_pattern: str = "*", case_sensitive: bool = False) -> str:
    """Search code for lines matching a regular expression, and return each match as 'file:line: text'.

    Use this to find where a function, class, variable or error message is defined or used, then read_file the matching file around that line. Searches subdirectories too, skipping .git, .venv, __pycache__, node_modules, binary files and files over 1 MB. Matching ignores letter case unless case_sensitive is true. Stops after 100 matches."""
    return grep.invoke({
        "pattern": query, "path": path, "file_glob": file_pattern, "ignore_case": not case_sensitive,
    })


def _walk(root):
    """os.walk that skips SKIP_DIRS and anything that leads outside the workspace."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and is_safe_path(os.path.join(dirpath, d)))
        yield dirpath, dirnames, sorted(f for f in filenames if is_safe_path(os.path.join(dirpath, f)))


@tool(parse_docstring=True)
def find_files(pattern: str, path: str = ".", max_results: int = 200) -> str:
    """Find files by name anywhere under a directory, and return their paths, one per line.

    Use this when you know roughly what a file is called but not where it is, e.g. '*.py' for all Python files or 'test_*' for test files. Matches file names only, not contents; use search_code to search inside files. Skips .git, .venv, __pycache__ and node_modules.

    Args:
        pattern: Glob for the file name, e.g. '*.py', 'test_*', 'config.*' or 'README*'.
        path: Directory to search in, relative to the current directory. Defaults to the current directory.
        max_results: Stop after this many files. Defaults to 200.
    """
    try:
        root = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"
    if not root.is_dir():
        return f"Error: directory not found: {path}"

    # Globs match file names, so drop any directory part the model adds, e.g. '**/*.py' -> '*.py'.
    name_glob = pattern.rsplit("/", 1)[-1] or "*"

    found = []
    for dirpath, _, filenames in _walk(root):
        for name in filenames:
            if fnmatch(name, name_glob):
                found.append(os.path.relpath(os.path.join(dirpath, name), get_current_dir()))
                if len(found) >= max_results:
                    return "\n".join(found) + f"\n... stopped after {max_results} files"

    return "\n".join(found) if found else f"No files matching {pattern!r} in {path}"


@tool(parse_docstring=True)
def file_tree(path: str = ".", depth: int = 2) -> str:
    """Show a directory's structure as an indented tree, to get an overview of how a project is organized.

    A good first step in an unfamiliar project. Directories end with '/', and .git, .venv, __pycache__ and node_modules are left out. Output is cut at 300 lines, so for big projects use a smaller depth or a subdirectory.

    Args:
        path: Directory to show, relative to the current directory. Defaults to the current directory.
        depth: How many levels of subdirectories to show, from 1 to 6. Defaults to 2.
    """
    try:
        root = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"
    if not root.is_dir():
        return f"Error: directory not found: {path}"

    depth = min(max(depth, 1), 6)
    lines = [os.path.relpath(root, get_current_dir()) + "/"]

    def add(directory, level):
        _, dirnames, filenames = next(_walk(directory))
        indent = "    " * level
        for d in dirnames:
            lines.append(f"{indent}{d}/")
            if level < depth:
                add(os.path.join(directory, d), level + 1)
        for f in filenames:
            lines.append(f"{indent}{f}")

    add(root, 1)
    return truncate("\n".join(lines), max_lines=300)


@tool(parse_docstring=True)
def get_symbols(path: str) -> str:
    """List the classes, functions and methods defined in a Python file, with their line numbers and full signatures.

    Use this to get an overview of a file's structure, or to find the line where a function starts before reading it with read_file. Methods are shown as 'ClassName.method'. Only works on .py files; if the file has a syntax error, the error's line is reported instead.

    Args:
        path: Python file to inspect, relative to the current directory.
    """
    try:
        target = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"
    if not target.is_file():
        return f"Error: file not found: {path}"
    if target.suffix != ".py":
        return f"Error: {path} is not a Python file"

    try:
        tree = ast.parse(target.read_text(), filename=str(target))
    except SyntaxError as e:
        return f"Error: {path} has a syntax error on line {e.lineno}: {e.msg}"

    symbols = []

    def visit(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                symbols.append(f"{child.lineno:>5}  class {prefix}{child.name}")
                visit(child, prefix=f"{prefix}{child.name}.")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "async def" if isinstance(child, ast.AsyncFunctionDef) else "def"
                returns = f" -> {ast.unparse(child.returns)}" if child.returns else ""
                symbols.append(f"{child.lineno:>5}  {kind} {prefix}{child.name}({ast.unparse(child.args)}){returns}")

    visit(tree)
    return "\n".join(symbols) if symbols else f"No classes or functions in {path}"


tools = [read_file, find_files, search_code, file_tree, get_symbols]
