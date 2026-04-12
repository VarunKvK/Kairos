# tools/shell.py
# Gives Kairos the ability to run terminal commands on your system.
# Every command runs in a subprocess — isolated from the main program.

import sys
import subprocess
from dataclasses import dataclass

@dataclass
class ShellResult:
    """
    Holds the result of a shell command.
    
    stdout  → the normal output of the command
    stderr  → the error output (if any)
    success → True if the command ran without errors
    """
    stdout : str
    stderr : str
    success : bool

# The exact path to the current Python and pip executables.
# This ensures Kairos always installs into the active virtual environment.
PYTHON_PATH = sys.executable
PIP_PATH    = sys.executable.replace("python", "pip").replace("python3", "pip3")


def run_command(command: str, timeout: int = 60, cwd: str = None) -> ShellResult:
    """
    Run a terminal command and return the result.
    cwd: working directory for the command (default: Kairos project dir)
    """
    import os

    # Expand ~ in command
    home    = os.path.expanduser("~")
    command = command.replace("~/", f"{home}/")

    # Set display environment for GUI commands
    env                             = os.environ.copy()
    env["DISPLAY"]                  = os.environ.get("DISPLAY", ":0")
    env["DBUS_SESSION_BUS_ADDRESS"] = os.environ.get(
        "DBUS_SESSION_BUS_ADDRESS",
        f"unix:path=/run/user/{os.getuid()}/bus"
    )

    # Use provided cwd or default to home
    working_dir = cwd or home

    try:
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,    # ← run in correct directory
            env=env,
            executable="/bin/bash",
        )

        # Combine stdout and stderr so we never miss error output
        output = process.stdout.strip()
        errors = process.stderr.strip()

        # For pip installs, stderr often contains progress info not real errors
        # So we combine both and let the LLM decide what it means
        full_output = output
        if errors and process.returncode != 0:
            full_output = f"{output}\nSTDERR: {errors}".strip()

        return ShellResult(
            stdout  = full_output,
            stderr  = errors,
            success = process.returncode == 0,
        )

    except subprocess.TimeoutExpired:
        return ShellResult(
            stdout  = "",
            stderr  = "Command timed out after 30 seconds.",
            success = False,
        )
    except Exception as e:
        return ShellResult(
            stdout  = "",
            stderr  = f"Unexpected error: {str(e)}",
            success = False,
        )