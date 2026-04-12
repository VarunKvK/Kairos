"""
plugins/timer.py — Countdown Timer
Set countdown timers that send desktop notifications.
Runs in a background thread — non-blocking.

Actions:
    set    → set a countdown timer
    list   → list active timers
    cancel → cancel a timer
"""

import threading
import time as time_module
from datetime import datetime, timedelta

PLUGIN_NAME        = "timer"
PLUGIN_DESCRIPTION = "Set countdown timers with desktop notifications"
PLUGIN_ACTIONS     = ["set", "list", "cancel"]

# ── State ─────────────────────────────────────────────────────────────────────

# Active timers
# { timer_id: { "label": str, "ends_at": datetime, "thread": Thread } }
_timers: dict = {}
_timer_id     = 0
_lock         = threading.Lock()


def run(action: str, input: str) -> str:
    """
    Timer actions.

    Input formats:
        set:    "5 minutes coffee break"
                "30 seconds test"
                "1 hour lunch"
        list:   (empty)
        cancel: timer_id
    """
    if action == "set":
        return _set_timer(input.strip())
    elif action == "list":
        return _list_timers()
    elif action == "cancel":
        return _cancel_timer(input.strip())
    else:
        return f"Unknown action: {action}"


# ── Timer Logic ───────────────────────────────────────────────────────────────

def _parse_duration(text: str) -> tuple[int, str]:
    """
    Parse duration from text.
    Returns (seconds, label)

    Examples:
        "5 minutes coffee" → (300, "coffee")
        "30 seconds"       → (30, "Timer")
        "1 hour lunch"     → (3600, "lunch")
        "90 seconds rest"  → (90, "rest")
    """
    parts   = text.lower().split()
    seconds = 0
    label   = "Timer"
    i       = 0

    while i < len(parts):
        part = parts[i]

        # Try to parse as number
        try:
            value = float(part)
            # Next part should be unit
            if i + 1 < len(parts):
                unit = parts[i + 1]
                if unit in ["second", "seconds", "sec", "secs", "s"]:
                    seconds += int(value)
                    i += 2
                elif unit in ["minute", "minutes", "min", "mins", "m"]:
                    seconds += int(value * 60)
                    i += 2
                elif unit in ["hour", "hours", "hr", "hrs", "h"]:
                    seconds += int(value * 3600)
                    i += 2
                else:
                    # No unit found — assume minutes
                    seconds += int(value * 60)
                    i += 1
            else:
                # No unit — assume minutes
                seconds += int(value * 60)
                i += 1
        except ValueError:
            # Not a number — it's the label
            label = " ".join(parts[i:])
            break

    if seconds <= 0:
        seconds = 60  # default 1 minute

    return seconds, label


def _set_timer(input: str) -> str:
    global _timer_id

    if not input:
        return "Provide duration. Example: '5 minutes coffee break'"

    seconds, label = _parse_duration(input)
    ends_at        = datetime.now() + timedelta(seconds=seconds)

    with _lock:
        _timer_id += 1
        tid = _timer_id

    if seconds >= 3600:
        display = f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    elif seconds >= 60:
        display = f"{seconds // 60}m {seconds % 60}s"
    else:
        display = f"{seconds}s"

    # Start background thread for notification
    thread = threading.Thread(
        target=_run_timer,
        args=(tid, label, seconds),
        daemon=True,
    )
    thread.start()

    with _lock:
        _timers[tid] = {
            "label":   label,
            "ends_at": ends_at,
            "thread":  thread,
            "active":  True,
        }

    # Open a separate terminal window showing the countdown
    _open_timer_window(tid, label, seconds)

    return f"Timer #{tid} set — {display} — '{label}'"


def _open_timer_window(tid: int, label: str, seconds: int) -> None:
    """
    Open a new terminal window showing a live countdown.
    Window closes automatically when timer ends.
    Non-blocking — Kairos continues normally.
    """
    import subprocess
    from pathlib import Path

    # Write a small countdown script
    script_path = Path("/tmp") / f"kairos_timer_{tid}.sh"
    script_path.write_text(f"""#!/bin/bash
# Kairos Timer #{tid} — {label}
echo ""
echo "  ⚡ KAIROS TIMER"
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Timer #{tid}: {label}"
echo ""

END=$((SECONDS + {seconds}))

while [ $SECONDS -lt $END ]; do
    REMAINING=$((END - SECONDS))
    MINS=$((REMAINING / 60))
    SECS=$((REMAINING % 60))
    HRS=$((MINS / 60))
    MINS=$((MINS % 60))

    if [ $HRS -gt 0 ]; then
        printf "\\r  ⏰  %02d:%02d:%02d remaining   " $HRS $MINS $SECS
    else
        printf "\\r  ⏰  %02d:%02d remaining      " $MINS $SECS
    fi
    sleep 1
done

echo ""
echo ""
echo "  ✓ Done! '{label}' complete."
echo ""
echo "  This window closes in 5 seconds..."
sleep 5
""")
    script_path.chmod(0o755)

    # Try different terminal emulators
    # gnome-terminal is default on Ubuntu
    terminals = [
        ["gnome-terminal", "--title", f"⏰ Kairos Timer — {label}",
         "--geometry", "50x10",
         "--", "bash", str(script_path)],
        ["xterm", "-title", f"Kairos Timer — {label}",
         "-geometry", "50x10",
         "-e", f"bash {script_path}"],
        ["konsole", "--title", f"Kairos Timer — {label}",
         "-e", f"bash {script_path}"],
        ["xfce4-terminal", "--title", f"Kairos Timer — {label}",
         "-e", f"bash {script_path}"],
    ]

    env = {
        **__import__("os").environ,
        "DISPLAY": __import__("os").environ.get("DISPLAY", ":0"),
        "DBUS_SESSION_BUS_ADDRESS": __import__("os").environ.get(
            "DBUS_SESSION_BUS_ADDRESS",
            f"unix:path=/run/user/{__import__('os').getuid()}/bus"
        ),
    }

    for terminal_cmd in terminals:
        try:
            subprocess.Popen(
                terminal_cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return  # Success — stop trying
        except FileNotFoundError:
            continue  # Try next terminal
        except Exception:
            continue

    # No terminal found — silent fail, notification still works

def _run_timer(tid: int, label: str, seconds: int) -> None:
    """Background thread — waits then sends notification."""
    time_module.sleep(seconds)

    # Check if still active
    with _lock:
        if tid not in _timers or not _timers[tid]["active"]:
            return
        _timers[tid]["active"] = False

    # Send desktop notification
    try:
        from notifications import notify
        notify("⏰ Timer Done", f"'{label}' — time's up!", timeout=10)
    except Exception:
        pass


def _list_timers() -> str:
    with _lock:
        active = {
            tid: t for tid, t in _timers.items()
            if t["active"]
        }

    if not active:
        return "No active timers."

    lines = [f"  {len(active)} active timer(s):"]
    now   = datetime.now()

    for tid, t in active.items():
        remaining = (t["ends_at"] - now).total_seconds()
        if remaining > 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            lines.append(f"  #{tid} '{t['label']}' — {mins}m {secs}s remaining")

    return "\n".join(lines)


def _cancel_timer(input: str) -> str:
    try:
        tid = int(input)
    except ValueError:
        return f"Invalid timer ID: {input}"

    with _lock:
        if tid not in _timers:
            return f"Timer #{tid} not found."
        _timers[tid]["active"] = False

    return f"Timer #{tid} cancelled."