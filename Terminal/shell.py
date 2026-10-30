import os
import subprocess

MAX_OUTPUT_LINES = 200

def truncate(text: str, max_lines: int = MAX_OUTPUT_LINES) -> str:
    """Cut long output down to max_lines, noting how much was left out."""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text

    hidden = len(lines) - max_lines
    return "\n".join(lines[:max_lines]) + f"\n... ({hidden} more lines not shown)"


def run(args: list[str], timeout: int = 30, max_lines: int | None = MAX_OUTPUT_LINES, cwd=None, input: str | None = None, ok_codes: tuple[int, ...] = (0,)) -> str:
    """Run a command without a shell and return its output, or an 'Error: ...' string.

    Output is cut to max_lines; pass None to get all of it, e.g. when the output will be parsed.
    Exit codes in ok_codes count as success, e.g. a linter exits with 1 when it finds problems.
    stdin gets `input` if given; otherwise it is closed, so a program waiting for keyboard input fails instead of hanging.
    """
    name = os.path.basename(args[0])
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, cwd=cwd,
            input=input, stdin=None if input is not None else subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return f"Error: command not found: {name}"
    except subprocess.TimeoutExpired:
        return f"Error: {name} timed out after {timeout} seconds"

    output = (result.stdout + result.stderr).strip()
    if result.returncode not in ok_codes:
        return f"Error: {name} exited with code {result.returncode}\n{truncate(output)}"

    return output if max_lines is None else truncate(output, max_lines)
