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


def run_command(command: str)-> ShellResult:
    """
    Run a shell command and return its result.
    Automatically replaces bare 'pip' and 'python' calls with the
    correct paths so installs always go into the active environment.

    Example:
        result = run_command("pip install fastapi")
        print(result.stdout)
    """

    # Replace bare pip/python calls with the correct executable paths
    # This ensures packages install into the active venv, not system Python
    command = command.replace("pip3 ", f"{PIP_PATH} ")
    command = command.replace("pip ",  f"{PIP_PATH} ")
    command = command.replace("python3 ", f"{PYTHON_PATH} ")
    command = command.replace("python ", f"{PYTHON_PATH} ")

    try:
        process = subprocess.run(
            command,
            shell = True,         # Allows full bash commands like "cd && ls"
            text=True,            # Returns output as string instead of bytes
            capture_output=True,  # Captures both stdout and stderr
            timeout=60,           # Kills the command if it runs more than 30 seconds
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