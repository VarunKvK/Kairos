"""
plugins/system.py — System Information
Gets CPU, RAM, disk, and process information.
Uses only Python standard library — no extra installs.
"""

import subprocess
import shutil

PLUGIN_NAME        = "system"
PLUGIN_DESCRIPTION = "Get system information — CPU, RAM, disk, processes"
PLUGIN_ACTIONS     = ["cpu", "ram", "disk", "processes", "summary"]


def run(action: str, input: str) -> str:
    """
    Get system information.

    Actions:
        cpu       → CPU usage
        ram       → RAM usage
        disk      → Disk usage
        processes → Top running processes
        summary   → Everything at once
    """

    if action == "cpu":
        return _get_cpu()
    elif action == "ram":
        return _get_ram()
    elif action == "disk":
        return _get_disk()
    elif action == "processes":
        return _get_processes()
    elif action == "summary":
        return "\n\n".join([
            _get_cpu(),
            _get_ram(),
            _get_disk(),
            _get_processes(),
        ])
    else:
        return f"Unknown action: {action}"


def _run_cmd(cmd: str) -> str:
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return f"Error: {e}"


def _get_cpu() -> str:
    output = _run_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
    return f"CPU Usage: {output}%"


def _get_ram() -> str:
    output = _run_cmd("free -h | grep Mem")
    parts  = output.split()
    if len(parts) >= 3:
        return f"RAM — Total: {parts[1]} | Used: {parts[2]} | Free: {parts[3]}"
    return f"RAM: {output}"


def _get_disk() -> str:
    output = _run_cmd("df -h | grep -v tmpfs | grep -v udev")
    return f"Disk Usage:\n{output}"


def _get_processes() -> str:
    output = _run_cmd(
        "ps aux --sort=-%cpu | head -6 | awk '{print $1, $2, $3, $4, $11}'"
    )
    return f"Top Processes (user, pid, cpu%, mem%, cmd):\n{output}"