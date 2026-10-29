import platform
import re
from langchain_core.tools import tool
from Terminal.shell import run

# Hostnames, IPv4 and IPv6 addresses. Rejecting anything else (like a leading '-')
# stops the LLM from smuggling extra command-line options into ping.
HOST_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-:]*$")

@tool(parse_docstring=True)
def ping(host: str, count: int = 4) -> str:
    """Check whether a network host is reachable and how long replies take.

    Args:
        host: Hostname or IP address, e.g. 'google.com' or '8.8.8.8'.
        count: Number of pings to send, from 1 to 10.
    """
    if not HOST_PATTERN.match(host):
        return f"Error: invalid host: {host!r}"

    count = min(max(count, 1), 10)
    flag = "-n" if platform.system() == "Windows" else "-c"
    return run(["ping", flag, str(count), host], timeout=count * 5 + 5)


@tool
def ipconfig() -> str:
    """Show this machine's network interfaces and their IP addresses."""
    system = platform.system()

    if system == "Windows":
        return run(["ipconfig"])
    if system == "Linux":
        return run(["ip", "-brief", "address"])

    # macOS: keep only interfaces that have an address, and only their address lines.
    output = run(["ifconfig"])
    if output.startswith("Error:"):
        return output

    summary, interface, listed = [], None, None
    for line in output.splitlines():
        if line and not line[0].isspace():
            interface = line.split(":")[0]
        elif line.strip().startswith(("inet ", "inet6 ")) and interface:
            if listed != interface:
                summary.append(f"{interface}:")
                listed = interface
            summary.append("    " + " ".join(line.split()[:2]))

    return "\n".join(summary) or "No interfaces with an IP address found"


@tool(parse_docstring=True)
def netstat(listening_only: bool = True) -> str:
    """List network ports and connections on this machine.

    Args:
        listening_only: If true, show only ports that programs are listening on. If false, show all connections.
    """
    system = platform.system()

    if not listening_only:
        return run(["netstat", "-an"])
    if system == "Linux":
        return run(["ss", "-tuln"])
    if system == "Windows":
        return run(["netstat", "-an", "-p", "TCP"])

    # macOS: lsof also shows which program owns each port.
    output = run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"])
    if output.startswith("Error: lsof exited with code 1"):
        return "No programs are listening on TCP ports"
    return output


tools = [ping, ipconfig, netstat]
