# code_execution.py
# - run_python(path: str, script_args: list[str] = []) -> str  (LangChain reserves the name 'args')
# - run_tests(path=".") -> str
# - lint(path=".") -> str
# - type_check(path=".") -> str
# - format_code(path=".") -> str
# - install_package(name: str) -> str
# - list_packages() -> list[str]
# - tools = [...]

import re
import sys
from langchain_core.tools import tool
from Core.workspace import get_current_dir, resolve_safe_path
from Terminal.shell import run

@tool(parse_docstring=True)
def run_python(path: str, script_args: list[str] | None = None, timeout: int = 60) -> str:
    """Run a Python script and return everything it printed, including any error traceback.

    Use this to test code you wrote, or to check how a script behaves. The script runs from the current directory with the agent's own Python environment, so installed packages are available. It cannot read keyboard input: input() fails immediately. It is stopped after timeout seconds. A non-zero exit code is reported as an error, together with the output. For pytest tests, use run_tests instead.

    Args:
        path: Python file to run, relative to the current directory.
        script_args: Command-line arguments passed to the script, e.g. ['--verbose', 'input.txt'].
        timeout: Seconds to wait before stopping the script, from 1 to 300. Defaults to 60.
    """
    try:
        script = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"

    if not script.is_file():
        return f"Error: file not found: {path}"
    if script.suffix != ".py":
        return f"Error: {path} is not a .py file"

    timeout = min(max(timeout, 1), 300)
    output = run([sys.executable, str(script), *(script_args or [])], timeout=timeout, cwd=get_current_dir())
    return output or "Script finished with no output"


def _python_module(module: list[str], path: str, timeout: int = 120, ok_codes: tuple[int, ...] = (0, 1)) -> str:
    """Run `python -m <module...> <path>` from the current directory, after checking the path is safe.

    Exit code 1 counts as success by default, because these tools use it to mean "found problems".
    """
    try:
        target = resolve_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"

    if not target.exists():
        return f"Error: path not found: {path}"

    return run([sys.executable, "-m", *module, str(target)], timeout=timeout, cwd=get_current_dir(), ok_codes=ok_codes)


@tool(parse_docstring=True)
def run_tests(path: str = ".") -> str:
    """Run pytest tests and return the report: one character per test ('.' passed, 'F' failed, 'E' error), the details of each failure, and a summary line.

    Run this after changing code, to check nothing broke. Point it at a single test file to run fewer tests. pytest looks for files named test_*.py or *_test.py. Says so when no tests are found. Stopped after 5 minutes.

    Args:
        path: Test file or directory to run. Defaults to everything under the current directory.
    """
    # pytest exits with 5 when it finds no tests.
    output = _python_module(["pytest", "-q", "--no-header", "-p", "no:cacheprovider"], path, timeout=300, ok_codes=(0, 1, 5))
    if "no tests ran" in output:
        return f"No tests found in {path}"
    return output


@tool(parse_docstring=True)
def lint(path: str = ".") -> str:
    """Check Python code for likely bugs and style problems with ruff, without changing any files.

    Reports problems such as undefined names, unused imports and syntax errors, one per line as 'file:line:column: CODE message'. Codes starting with F are likely bugs, so fix those first. Returns 'All checks passed!' when there is nothing to report.

    Args:
        path: File or directory to check. Defaults to the current directory.
    """
    return _python_module(["ruff", "check", "--no-cache", "--output-format=concise"], path)


@tool(parse_docstring=True)
def type_check(path: str = ".") -> str:
    """Check Python code for type errors with mypy, without changing any files.

    Finds problems such as calling a function with the wrong argument types, using an undefined name, or returning the wrong type, reported as 'file:line: error: message'. Missing type information for third-party packages is ignored. Slower than lint, especially on a big project.

    Args:
        path: File or directory to check. Defaults to the current directory.
    """
    return _python_module(["mypy", "--no-incremental", "--ignore-missing-imports", "--check-untyped-defs"], path, timeout=300)


@tool(parse_docstring=True)
def format_code(path: str = ".") -> str:
    """Reformat Python files in place with ruff's formatter, fixing indentation, spacing, quotes and line length.

    Changes only the layout, never what the code does. Run it after writing code rather than before reading it, because it shifts line numbers. undo_edit cannot reverse it. Returns how many files were reformatted.

    Args:
        path: File or directory to format. Defaults to the current directory.
    """
    return _python_module(["ruff", "format", "--no-cache"], path)


# Package names as pip accepts them, with optional extras and a version, e.g. 'requests' or 'httpx[http2]>=0.27'.
PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9._,-]+\])?([<>=!~]=?[A-Za-z0-9.*+!-]+)?$")

@tool(parse_docstring=True)
def install_package(name: str) -> str:
    """Install a Python package from PyPI into the agent's environment with pip, so that scripts and tests can import it.

    Use this only when code needs a package that isn't installed; check with list_packages first. Only a package name is accepted, optionally with extras and a version, never pip options. Returns which packages were installed, or says the package was already installed.

    Args:
        name: Package name as listed on PyPI, optionally with extras or a version, e.g. 'requests', 'httpx[http2]' or 'numpy>=2.0'.
    """
    if not PACKAGE_PATTERN.match(name):
        return f"Error: invalid package name: {name!r}"

    output = run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", name], timeout=300)
    if output.startswith("Error:"):
        return output

    installed = [line for line in output.splitlines() if line.startswith("Successfully installed")]
    return installed[0] if installed else f"{name} is already installed"


@tool
def list_packages() -> str:
    """List every Python package installed in the agent's environment, one 'name==version' per line, sorted by name.

    Use this to check whether a package is available, or which version is installed, before importing it or calling install_package."""
    return run([sys.executable, "-m", "pip", "list", "--format=freeze", "--disable-pip-version-check"], max_lines=None)


tools = [run_python, run_tests, lint, type_check, format_code, install_package, list_packages]
