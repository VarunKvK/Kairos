"""
notifications.py — Kairos Desktop Notifications
Sends desktop notifications from Kairos to the user.

Used by:
    - FRIDAY   → when a filesystem event fires
    - Scheduler → when a job completes
    - Agent     → when a long task finishes
    - Manual    → /notify command in terminal UI

Requires: plyer
"""
"""
notifications.py — Kairos Desktop Notifications
Sends desktop notifications from Kairos to the user.

Used by:
    - FRIDAY   → when a filesystem event fires
    - Scheduler → when a job completes
    - Agent     → when a long task finishes
    - Manual    → /notify command in terminal UI

Requires: plyer
"""

import os
import subprocess
from plyer import notification
from pathlib import Path
import logging

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "notifications.log"

LOGS_DIR.mkdir(exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────

log = logging.getLogger("kairos.notifications")
log.setLevel(logging.INFO)

if not log.handlers:
    _handler = logging.FileHandler(LOG_FILE)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    log.addHandler(_handler)


# ── Display Environment ───────────────────────────────────────────────────────

def _ensure_display_env() -> None:
    """
    Ensure DISPLAY and DBUS_SESSION_BUS_ADDRESS are set.
    Background threads from systemd don't inherit desktop session.
    """
    if not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":0"

    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        try:
            result = subprocess.run(
                ["bash", "-c",
                 "cat /proc/$(pgrep -u $USER gnome-session | head -1)/environ "
                 "2>/dev/null | tr '\\0' '\\n' | grep DBUS_SESSION_BUS_ADDRESS"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stdout.strip():
                value = result.stdout.strip().split("=", 1)[1]
                os.environ["DBUS_SESSION_BUS_ADDRESS"] = value
        except Exception:
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = \
                f"unix:path=/run/user/{os.getuid()}/bus"


# ── Core Notify Function ──────────────────────────────────────────────────────

def notify(
    title:   str,
    message: str,
    timeout: int = 5,
) -> bool:
    """Send a desktop notification."""
    try:
        _ensure_display_env()
        notification.notify(
            title    = f"⚡ {title}",
            message  = message[:256],
            app_name = "Kairos",
            timeout  = timeout,
        )
        log.info(f"[{title}] {message[:100]}")
        return True
    except Exception as e:
        log.error(f"Notification failed: {e}")
        return False


# ── Preset Notifications ──────────────────────────────────────────────────────

def notify_friday(event: str, filepath: str, result: str = "") -> bool:
    """Notification for FRIDAY filesystem events."""
    filename = Path(filepath).name
    message  = f"{event.upper()}: {filename}"
    if result:
        message += f"\n→ {result[:100]}"
    return notify("FRIDAY", message)


def notify_scheduler(job_id: str, task: str, result: str = "") -> bool:
    """Notification for scheduled job completion."""
    message = f"Job [{job_id}] complete.\n{task[:80]}"
    if result:
        message += f"\n→ {result[:80]}"
    return notify("Scheduler", message)


def notify_agent(task: str, result: str = "") -> bool:
    """Notification for long agent tasks completing."""
    message = f"{task[:80]}"
    if result:
        message += f"\n→ {result[:80]}"
    return notify("Kairos", message)


def notify_error(source: str, error: str) -> bool:
    """Notification for errors."""
    return notify(f"⚠ {source} Error", error[:200], timeout=10)