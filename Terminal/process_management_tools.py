import os
import signal
from typing import Literal
from langchain_core.tools import tool
from Terminal.shell import run

def _list_processes() -> list[dict] | str:
    """Return running processes as dicts, or an 'Error: ...' string."""
    # A trailing '=' on each field hides the header row. comm goes last because it can contain spaces.
    output = run(["ps", "-axo", "pid=,ppid=,user=,%cpu=,%mem=,comm="], max_lines=None)
    if output.startswith("Error:"):
        return output

    processes = []
    for line in output.splitlines():
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        pid, ppid, user, cpu, mem, command = parts
        try:
            processes.append({
                "pid": int(pid), "ppid": int(ppid), "user": user,
                "cpu": float(cpu), "mem": float(mem), "command": command,
            })
        except ValueError:
            continue

    return processes


def _format(processes: list[dict]) -> str:
    rows = [f"{'PID':>7} {'PPID':>7} {'USER':<12} {'%CPU':>5} {'%MEM':>5}  COMMAND"]
    for p in processes:
        rows.append(f"{p['pid']:>7} {p['ppid']:>7} {p['user'][:12]:<12} {p['cpu']:>5.1f} {p['mem']:>5.1f}  {p['command']}")
    return "\n".join(rows)


@tool(parse_docstring=True)
def ps(name_filter: str | None = None, limit: int = 50) -> str:
    """List running processes with their PID, parent PID, user, CPU and memory use.

    Args:
        name_filter: Only show processes whose command contains this text, ignoring case.
        limit: Maximum number of processes to return.
    """
    processes = _list_processes()
    if isinstance(processes, str):
        return processes

    if name_filter:
        processes = [p for p in processes if name_filter.lower() in p["command"].lower()]
    if not processes:
        return f"No processes matching {name_filter!r}"

    shown = processes[:max(limit, 1)]
    result = _format(shown)
    if len(processes) > len(shown):
        result += f"\n... {len(processes) - len(shown)} more processes not shown"
    return result


@tool(parse_docstring=True)
def top(count: int = 10, sort_by: Literal["cpu", "memory"] = "cpu") -> str:
    """Show the processes using the most CPU or memory right now.

    Args:
        count: Number of processes to show.
        sort_by: Rank processes by 'cpu' or 'memory' use.
    """
    processes = _list_processes()
    if isinstance(processes, str):
        return processes

    key = "cpu" if sort_by == "cpu" else "mem"
    processes.sort(key=lambda p: p[key], reverse=True)
    return _format(processes[:max(count, 1)])


@tool(parse_docstring=True)
def kill(pid: int, force: bool = False) -> str:
    """Stop a running process by its process ID. Use ps to find the PID first.

    Args:
        pid: Process ID to stop.
        force: If false, ask the process to exit cleanly (SIGTERM). If true, stop it immediately (SIGKILL).
    """
    if pid <= 1:
        return f"Error: refusing to stop system process {pid}"
    if pid in (os.getpid(), os.getppid()):
        return "Error: refusing to stop the agent itself"

    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        return f"Error: no process with PID {pid}"
    except PermissionError:
        return f"Error: not allowed to stop process {pid}; it belongs to another user"

    return f"Sent {sig.name} to process {pid}"


tools = [ps, kill, top]
