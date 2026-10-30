import platform
import re
from langchain_core.tools import tool
from Terminal.shell import run

# Hostnames, IPv4 and IPv6 addresses. Rejecting anything else (like a leading '-')
# stops the LLM from smuggling extra command-line options into ping.
HOST_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-:]*$")

@tool(parse_docstring=True)
def ping(host: str, count: int = 4) -> str:
    """Check whether a network host is reachable and how long it takes to respond.

    Sends a few pings and returns the ping command's output, including packet loss and round-trip times. Use this to diagnose network problems, e.g. whether a server or the internet can be reached. Some hosts block ping, so getting no reply doesn't always mean the host is down. Anything other than a plain hostname or IP address is rejected.

    Args:
        host: Hostname or IP address, e.g. 'google.com', 'localhost' or '8.8.8.8'.
        count: Number of pings to send, from 1 to 10. Defaults to 4.
    """
    if not HOST_PATTERN.match(host):
        return f"Error: invalid host: {host!r}"

    count = min(max(count, 1), 10)
    flag = "-n" if platform.system() == "Windows" else "-c"
    return run(["ping", flag, str(count), host], timeout=count * 5 + 5)


@tool
def ipconfig() -> str:
    """Show this machine's network interfaces and the IPv4 and IPv6 addresses assigned to each.

    Use this to find the machine's local IP address, or to check whether it is connected to a network. On macOS, interfaces without an address are left out; 'lo0' is the loopback interface (127.0.0.1) and 'en0' is usually Wi-Fi or Ethernet."""
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
    """List network ports on this machine.

    By default, shows the TCP ports that programs are listening on, with the program name and PID on macOS. Use this to find what is using a port, e.g. 8000, or to check that a dev server started. Set listening_only to false to list every open connection instead, which can be a long list.

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
