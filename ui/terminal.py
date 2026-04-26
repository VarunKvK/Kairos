# ui/terminal.py
# Kairos terminal UI — minimal, Claude Code inspired, Greek accents.

import time
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from datetime import datetime
from rich.live import Live
from rich.console import Console
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich.align import Align
from pathlib import Path

from agent import run_agent
from planner import run_planner
from config import config

from scheduler import add_job, remove_job, list_jobs, run_job_now
from friday import add_watch, remove_watch, list_watches
from memory import remember, forget, forget_all, list_memory
from notifications import notify

import requests as _requests
from plugin_manager import list_plugins


console = Console()

def _api(method: str, endpoint: str, body: dict = None) -> dict | None:
    """
    Make a request to the Kairos API.
    Ensures changes go to the correct process (systemd)
    instead of the local terminal process.
    """
    url = f"http://127.0.0.1:8765{endpoint}"
    try:
        if method == "GET":
            r = _requests.get(url, timeout=10)
        elif method == "POST":
            r = _requests.post(url, json=body, timeout=10)
        elif method == "DELETE":
            r = _requests.delete(url, timeout=10)
        else:
            return None

        if r.ok:
            # Some endpoints return empty body (204)
            if r.content:
                return r.json()
            return {"ok": True}
        else:
            try:
                return {"error": r.json().get("detail", r.text)}
            except Exception:
                return {"error": r.text}

    except _requests.exceptions.ConnectionError:
        return {"error": "Cannot reach Kairos API. Is it running?"}
    except Exception as e:
        return {"error": str(e)}

# ─── PROMPT STYLE ──────────────────────────────────────────────────────────
PROMPT_STYLE = Style.from_dict({
    "prompt": "#d4af37 bold",
})


# ─── WELCOME SCREEN ────────────────────────────────────────────────────────

def show_welcome():
    import os
    # Use launch directory if set — otherwise fall back to cwd
    cwd = os.environ.get("KAIROS_LAUNCH_DIR", os.getcwd())
    
    console.print()
    console.print(Text("  ⚡ KAIROS  Κ Α Ι Ρ Ο Σ", style="bold gold1"))
    console.print(Text("  God of the Opportune Moment", style="italic dim white"))
    console.print()
    console.print(Text(f"  Provider  {config['provider'].upper()}  ·  {config['models'][config['provider']]}", style="dim white"))
    console.print(Text(f"  Location  {cwd}", style="dim white"))   # ← add this
    console.print(Text("  Status    Ready", style="dim green"))
    console.print()
    console.print(Rule(style="dim gold1"))
    console.print()
    console.print(Text("  Speak your intent. Type 'exit' to dismiss.", style="dim white"))
    console.print()


# ─── STEP LOGGER ───────────────────────────────────────────────────────────

def log_step(message: str, style: str = "dim white"):
    """Print a single visible step line — minimal, one line each."""
    console.print(Text(f"  {message}", style=style))


# ─── THINKING LOADER ───────────────────────────────────────────────────────

class KairosLoader:
    """
    Animated loader shown while waiting for LLM response.
    Transient — erases itself when done.
    """

    def __init__(self, message: str = "Kairos contemplates..."):
        self.message = message
        self.live    = None

    def __enter__(self):
        self.live = Live(
            Align.left(Text(f"  ⌛  {self.message}", style="dim gold1")),
            console            = console,
            refresh_per_second = 10,
            transient          = True,
        )
        self.live.start()
        return self

    def update(self, message: str):
        self.live.update(
            Align.left(Text(f"  ⌛  {message}", style="dim gold1"))
        )

    def __exit__(self, *args):
        self.live.stop()


# ─── DISPLAY RESPONSE ──────────────────────────────────────────────────────

def show_response(answer: str):
    """
    Display final answer — clean, no heavy panel.
    Just a gold rule, the text, and whitespace.
    """

    console.print()
    console.print(Rule(style="gold1"))
    console.print()
    console.print(Text(f"  {answer}", style="white"))
    console.print()
    console.print(Rule(style="dim gold1"))
    console.print()


# ─── DISPLAY ERROR ─────────────────────────────────────────────────────────

def show_error(message: str):
    """Display an error — minimal red text."""

    console.print()
    console.print(Text(f"  ⚔  {message}", style="bold red"))
    console.print()


# ─── DISPLAY FAREWELL ──────────────────────────────────────────────────────

def show_farewell():
    """Minimal farewell — one quote, one line."""

    console.print()
    console.print(Rule(style="dim gold1"))
    console.print()
    console.print(Text(
        "  \"He who seizes the right moment, is the right man.\"",
        style="italic dim white"
    ))
    console.print(Text("                                        — Goethe", style="dim white"))
    console.print()
    console.print(Text("  Καιρός departs. Until the moment returns.", style="gold1"))
    console.print()


# ─── PATCHED AGENT WITH VISIBLE STEPS ─────────────────────────────────────

def run_agent_visible(user_input: str, history: list) -> tuple[str, list]:
    """
    Wraps run_planner but patches console output so every
    step is visible as a clean one-liner.
    
    We monkey-patch console.print temporarily to intercept
    the dim step messages from agent.py and planner.py
    and reformat them cleanly.
    """

    # Intercept prints from agent/planner and reformat them
    original_print = console.print

    def clean_print(*args, **kwargs):
        # Let all prints through — they're already one-liners in agent.py
        original_print(*args, **kwargs)

    console.print = clean_print

    try:
        answer, history = run_planner(user_input, history)
    finally:
        # Always restore original print even if something fails
        console.print = original_print

    return answer, history

# ─── SLASH COMMAND HANDLER ─────────────────────────────────────────────────
def _handle_watch_natural_language(user_input: str) -> None:
    """
    Parse a natural language /watch request using the LLM.
    """
    from llm import chat
    import json
    import re

    # Strip the /watch prefix — only send the actual intent to LLM
    # "/watch monitor my Downloads folder" → "monitor my Downloads folder"
    intent = user_input.strip()
    if intent.lower().startswith("/watch"):
        intent = intent[len("/watch"):].strip()

    console.print()
    console.print(Text("  ⌛ Interpreting your watch request...", style="dim gold1"))

    extraction_prompt = [
        {
            "role": "system",
            "content": """You extract filesystem watch parameters from natural language.
                Always respond with a single JSON object — nothing else.

                Valid events: created, modified, deleted, any
                Pattern examples: *.py, *.log, *.txt, * (for all files)
                Task should include {filepath} as placeholder for the actual file path.

                Default values if not mentioned:
                - folder: ~/Dev
                - pattern: * (all files)
                - event: created
                - task: "A file event occurred at {filepath}. Briefly describe what happened."

                JSON format:
                {
                "folder": "absolute or ~ path to watch",
                "pattern": "*.py",
                "event": "created",
                "task": "what kairos should do when the event fires, use {filepath} as placeholder"
                }"""
        },
        {
            "role": "user",
            "content": f"Extract watch parameters from this request: {intent}"
        }
    ]

    try:
        raw     = chat(extraction_prompt)
        cleaned = raw.strip()

        # Strip markdown code blocks if present
        if cleaned.startswith("```"):
            parts   = cleaned.split("```")
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        # Fix unquoted none values
        cleaned = re.sub(r':\s*none\b', ': "none"', cleaned)

        params  = json.loads(cleaned)

        folder  = params.get("folder",  "~/Dev")
        pattern = params.get("pattern", "*")
        event   = params.get("event",   "created")
        task = params.get("task", "A file was created at {filepath}. State the filename only.")

        # Show what was understood — let user confirm before creating
        console.print(Text("  Understood:", style="dim gold1"))
        console.print(Text(f"    Folder:  {folder}", style="dim white"))
        console.print(Text(f"    Pattern: {pattern}", style="dim white"))
        console.print(Text(f"    Event:   {event}", style="dim white"))
        console.print(Text(f"    Task:    {task[:80]}", style="dim white"))
        console.print()

        # Ask user to confirm before creating
        console.print(Text("  Confirm? (yes/no)", style="dim gold1"))
        confirm = input("  → ").strip().lower()

        if confirm not in ["yes", "y"]:
            console.print(Text("  Watch cancelled.", style="dim white"))
            console.print()
            return

        data = _api("POST", "/watches", {
            "folder":  folder,
            "task":    task,
            "event":   event,
            "pattern": pattern,
        })
        if data and "error" not in data:
            console.print(Text(f"  ✓ Watch active [{data['id']}]", style="green"))
        else:
            show_error(data.get("error", "Failed to add watch."))

        console.print()

    except json.JSONDecodeError:
        show_error("Could not parse watch request. Try: /watch add <folder> <pattern> <event> \"<task>\"")
    except ValueError as e:
        show_error(str(e))
    except Exception as e:
        show_error(f"Watch setup failed: {str(e)}")

def handle_slash_command(user_input: str) -> bool:
    """
    Handle /commands before they reach the LLM.
    Returns True if a command was handled, False if not a command.

    Commands:
        /watch add <folder> <pattern> <event> <task>
        /watch list
        /watch remove <id>

        /job add <task> | <schedule>
        /job list
        /job remove <id>
        /job run <id>

        /help
    """
    inp = user_input.strip()

    if not inp.startswith("/"):
        return False

    parts = inp.split(None, 3)   # split on whitespace, max 4 parts
    cmd   = parts[0].lower()     # /watch or /job or /help

    # ── /help ─────────────────────────────────────────────
    if cmd == "/help":
        console.print()
        console.print(Text("  ── Slash Commands ──", style="bold gold1"))
        console.print()
        console.print(Text("  FRIDAY — Filesystem Watcher:", style="gold1"))
        console.print(Text('  /watch add <folder> <pattern> <event> "<task>"', style="dim white"))
        console.print(Text("  /watch list", style="dim white"))
        console.print(Text("  /watch remove <id>", style="dim white"))
        console.print()
        console.print(Text("  Scheduler — Timed Tasks:", style="gold1"))
        console.print(Text('  /job add "<task>" | "<schedule>"', style="dim white"))
        console.print(Text("  /job list", style="dim white"))
        console.print(Text("  /job remove <id>", style="dim white"))
        console.print(Text("  /job run <id>", style="dim white"))
        console.print()
        console.print(Text("  Examples:", style="gold1"))
        console.print(Text('  /watch add ~/Dev/Kairos *.py created "review {filepath}"', style="dim white"))
        console.print(Text('  /job add "summarize Dev folder" | "every day at 08:00"', style="dim white"))
        console.print(Text("  Memory:", style="gold1"))
        console.print(Text("  /memory add <facts|preferences|projects> <content>", style="dim white"))
        console.print(Text("  /memory list", style="dim white"))
        console.print(Text("  /memory forget <content>", style="dim white"))
        console.print(Text("  /memory clear", style="dim white"))
        console.print(Text("  Notifications:", style="gold1"))
        console.print(Text("  /notify <message>    → send yourself a desktop notification", style="dim white"))
        console.print(Text("  Plugins:", style="gold1"))
        console.print(Text("  /plugins    → list all loaded plugins", style="dim white"))
        console.print(Text("  /open <path>  → open file, folder or URL in GUI", style="dim white"))
        console.print(Text("  /timer        → list active timers", style="dim white"))
        console.print(Text("  /timer <id>   → watch live countdown", style="dim white"))

        console.print()
        return True

    # ── /watch ────────────────────────────────────────────
    if cmd == "/watch":
        if len(parts) < 2:
            show_error("Usage: /watch add|list|remove or natural language")
            return True

        sub = parts[1].lower()

        # ── /watch list ───────────────────────────────
        if sub == "list":
            data = _api("GET", "/watches")
            console.print()
            if not data or "error" in data:
                show_error(data.get("error", "Failed to reach API"))
                return True
            watches = data.get("watches", [])
            if not watches:
                console.print(Text("  No active watches.", style="dim white"))
            else:
                console.print(Text(f"  {len(watches)} active watch(es):", style="gold1"))
                for w in watches:
                    console.print(Text(f"  [{w['id']}] {w['folder']} — {w['event']} {w['pattern']}", style="dim white"))
                    console.print(Text(f"    Task: {w['task'][:80]}", style="dim white"))
            console.print()
            return True

        if sub == "remove":
            if len(parts) < 3:
                show_error("Usage: /watch remove <id>")
                return True
            watch_id = parts[2]
            data     = _api("DELETE", f"/watches/{watch_id}")
            console.print()
            if data and "error" not in data:
                console.print(Text(f"  ✓ Watch '{watch_id}' removed.", style="green"))
            else:
                show_error(data.get("error", f"Watch '{watch_id}' not found."))
            console.print()
            return True

        if sub == "add":
            import os
            rest   = inp[len("/watch add"):].strip()
            tokens = rest.split(None, 3)

            if len(tokens) < 4:
                show_error('Usage: /watch add <folder> <pattern> <event> "<task>"')
                return True

            # Extract the four parts
            folder  = tokens[0]
            pattern = tokens[1]
            event   = tokens[2]
            task    = tokens[3].strip('"')

            # CWD is where the user launched kairos from — set by /usr/local/bin/kairos
            # The API runs under systemd and has a different CWD — never trust os.getcwd() here
            cwd      = os.environ.get("KAIROS_LAUNCH_DIR", os.getcwd())
            cwd_path = Path(cwd).resolve()

            # Step 1 — expand ~ if present
            folder_path = Path(folder).expanduser()

            # Step 2 — if still relative, resolve it
            if not folder_path.is_absolute():
                # Did the user type the name of the CWD folder itself?
                # e.g. CWD = /home/x/Dev/Scripts/Hermes and input = "Hermes"
                if cwd_path.name == folder:
                    folder_path = cwd_path          # They meant the CWD itself
                else:
                    # Treat as a subfolder inside CWD
                    folder_path = (cwd_path / folder_path).resolve()
            else:
                # Already absolute — just clean it up
                folder_path = folder_path.resolve()

            folder = str(folder_path)

            # Validate before sending to API
            if not folder_path.exists():
                show_error(f"Folder does not exist: {folder}")
                console.print()
                return True

            data = _api("POST", "/watches", {
                "folder":  folder,
                "task":    task,
                "event":   event,
                "pattern": pattern,
            })
            console.print()
            if data and "error" not in data:
                console.print(Text(f"  ✓ Watch added [{data['id']}]", style="green"))
                console.print(Text(f"    Folder:  {data['folder']}", style="dim white"))
                console.print(Text(f"    Pattern: {data['pattern']}", style="dim white"))
                console.print(Text(f"    Event:   {data['event']}", style="dim white"))
                console.print(Text(f"    Task:    {data['task'][:80]}", style="dim white"))
            else:
                show_error(data.get("error", "Failed to add watch."))
            console.print()
            return True

    # ── /job ──────────────────────────────────────────────
    if cmd == "/job":
        if len(parts) < 2:
            show_error("Usage: /job add|list|remove|run ...")
            return True

        sub = parts[1].lower()

        if sub == "list":
            data = _api("GET", "/jobs")
            console.print()
            if not data or "error" in data:
                show_error(data.get("error", "Failed to reach API"))
                return True
            jobs = data.get("jobs", [])
            if not jobs:
                console.print(Text("  No scheduled jobs.", style="dim white"))
            else:
                console.print(Text(f"  {len(jobs)} scheduled job(s):", style="gold1"))
                for j in jobs:
                    console.print(Text(f"  [{j['id']}] {j['schedule']}", style="dim white"))
                    console.print(Text(f"    Task: {j['task'][:80]}", style="dim white"))
            console.print()
            return True

        if sub == "remove":
            if len(parts) < 3:
                show_error("Usage: /job remove <id>")
                return True
            job_id = parts[2]
            data   = _api("DELETE", f"/jobs/{job_id}")
            console.print()
            if data and "error" not in data:
                console.print(Text(f"  ✓ Job '{job_id}' removed.", style="green"))
            else:
                show_error(data.get("error", f"Job '{job_id}' not found."))
            console.print()
            return True

        if sub == "run":
            if len(parts) < 3:
                show_error("Usage: /job run <id>")
                return True
            job_id = parts[2]
            console.print()
            console.print(Text(f"  ⌛ Running job '{job_id}'...", style="dim gold1"))
            data = _api("POST", f"/jobs/{job_id}/run")
            if data and "error" not in data:
                show_response(data.get("result", "Done."))
            else:
                show_error(data.get("error", "Failed to run job."))
            return True

        if sub == "add":
            rest = inp[len("/job add"):].strip()
            if " | " not in rest:
                show_error('Usage: /job add "<task>" | "<schedule>"')
                return True
            task_part, schedule_part = rest.split(" | ", 1)
            task     = task_part.strip().strip('"')
            schedule = schedule_part.strip().strip('"')

            data = _api("POST", "/jobs", {
                "task":     task,
                "schedule": schedule,
            })
            console.print()
            if data and "error" not in data:
                console.print(Text(f"  ✓ Job added [{data['id']}]", style="green"))
                console.print(Text(f"    Task:     {data['task'][:80]}", style="dim white"))
                console.print(Text(f"    Schedule: {data['schedule']}", style="dim white"))
            else:
                show_error(data.get("error", "Failed to add job."))
            console.print()
            return True

        show_error(f"Unknown /job subcommand: {sub}. Use add|list|remove|run.")
        return True

    # ── /plugins ──────────────────────────────────────────
    if cmd == "/plugins":
        plugins = list_plugins()
        console.print()
        if not plugins:
            console.print(Text("  No plugins loaded.", style="dim white"))
        else:
            console.print(Text(f"  {len(plugins)} plugin(s) loaded:", style="gold1"))
            for p in plugins:
                actions = ", ".join(p["actions"])
                console.print(Text(f"  [{p['name']}] {p['description']}", style="dim white"))
                console.print(Text(f"    Actions: {actions}", style="dim gold1"))
        console.print()
        return True

    # ── /timer ────────────────────────────────────────────
    if cmd == "/timer":
        # /timer <id> → show live countdown for a timer
        from plugin_manager import get_plugin
        import time as _time

        timer_plugin = get_plugin("timer")
        if not timer_plugin:
            show_error("Timer plugin not loaded.")
            return True

        if len(parts) < 2:
            # Just list timers
            result = timer_plugin.run("list", "")
            console.print()
            console.print(Text(f"  {result}", style="dim white"))
            console.print()
            return True

        # Show live countdown
        try:
            tid     = int(parts[1])
            console.print()
            console.print(Text(f"  Watching timer #{tid} — Ctrl+C to stop", style="dim gold1"))
            console.print()

            with Live(console=console, refresh_per_second=1) as live:
                while True:
                    with timer_plugin._lock:
                        timer = timer_plugin._timers.get(tid)

                    if not timer:
                        live.update(Text("  Timer not found.", style="red"))
                        break

                    if not timer["active"]:
                        live.update(Text(f"  ⏰ '{timer['label']}' — Done!", style="gold1"))
                        _time.sleep(1)
                        break

                    remaining = (timer["ends_at"] - datetime.now()).total_seconds()
                    if remaining <= 0:
                        live.update(Text(f"  ⏰ '{timer['label']}' — Done!", style="gold1"))
                        _time.sleep(1)
                        break

                    mins = int(remaining // 60)
                    secs = int(remaining % 60)
                    hrs  = int(mins // 60)
                    mins = mins % 60

                    if hrs > 0:
                        time_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
                    else:
                        time_str = f"{mins:02d}:{secs:02d}"

                    live.update(Text(
                        f"  ⏰ [{tid}] '{timer['label']}' — {time_str} remaining",
                        style="gold1"
                    ))
                    _time.sleep(1)

            console.print()

        except ValueError:
            show_error(f"Invalid timer ID: {parts[1]}")
        except KeyboardInterrupt:
            console.print()
            console.print(Text("  Timer watch stopped.", style="dim white"))
            console.print()

        return True

    # ── /open ─────────────────────────────────────────────
    if cmd == "/open":
        if len(parts) < 2:
            show_error("Usage: /open <file|folder|url|search query>")
            return True

        import os
        cwd = os.environ.get("KAIROS_LAUNCH_DIR", os.getcwd())
        path = " ".join(parts[1:])

        # URL check first
        if path.startswith("http://") or path.startswith("https://"):
            final_path = path

        # Search query
        elif any(path.lower().startswith(t) for t in
                ["search ", "google ", "look up ", "find "]):
            for trigger in ["search ", "google ", "look up ", "find "]:
                if path.lower().startswith(trigger):
                    query      = path[len(trigger):].strip()
                    encoded    = query.replace(" ", "+")
                    final_path = f"https://duckduckgo.com/?q={encoded}"
                    break

        # File or folder
        else:
            # Strip trailing keywords
            for keyword in [" folder", " file", " directory", " dir"]:
                if path.lower().endswith(keyword):
                    path = path[:-len(keyword)].strip()
                    break

            # Shortcuts — include current dir
            shortcuts = {
                "downloads": str(Path.home() / "Downloads"),
                "desktop":   str(Path.home() / "Desktop"),
                "documents": str(Path.home() / "Documents"),
                "dev":       str(Path.home() / "Dev"),
                "home":      str(Path.home()),
                "kairos":    str(Path.home() / "Dev/Kairos"),
                "pictures":  str(Path.home() / "Pictures"),
                "videos":    str(Path.home() / "Videos"),
                "music":     str(Path.home() / "Music"),
                "here":      cwd,
                "this":      cwd,
                "current":   cwd,
                ".":         cwd,
            }

            path_lower = path.lower().strip()

            if path_lower in shortcuts:
                final_path = shortcuts[path_lower]
            else:
                # Expand ~
                path = path.replace("~", str(Path.home()))

                if path.startswith("/"):
                    # Absolute path — use as is
                    final_path = path
                else:
                    # Relative path — resolve from CWD first
                    relative = Path(cwd) / path
                    if relative.exists():
                        final_path = str(relative)
                    else:
                        # Try home directory
                        from_home = Path.home() / path
                        if from_home.exists():
                            final_path = str(from_home)
                        else:
                            # Use as-is and let xdg-open handle the error
                            final_path = str(relative)

        # Open it
        env = {
            **os.environ,
            "DISPLAY": os.environ.get("DISPLAY", ":0"),
            "DBUS_SESSION_BUS_ADDRESS": os.environ.get(
                "DBUS_SESSION_BUS_ADDRESS",
                f"unix:path=/run/user/{os.getuid()}/bus"
            ),
        }

        import subprocess
        try:
            subprocess.Popen(
                ["xdg-open", final_path],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            console.print()
            if final_path.startswith("http"):
                console.print(Text(f"  ✓ Opening browser: {final_path}", style="green"))
            else:
                console.print(Text(f"  ✓ Opening: {final_path}", style="green"))
            console.print()
        except Exception as e:
            show_error(f"Could not open: {e}")
        return True
        
    # ── /memory ───────────────────────────────────────────────
    if cmd == "/memory":
        if len(parts) < 2:
            show_error("Usage: /memory add|list|forget|clear")
            return True

        sub = parts[1].lower()

        if sub == "list":
            mem   = list_memory()
            total = sum(len(v) for v in mem.values())
            console.print()
            if total == 0:
                console.print(Text("  No memories stored.", style="dim white"))
            else:
                for category, items in mem.items():
                    if items:
                        console.print(Text(f"  {category.upper()}:", style="gold1"))
                        for item in items:
                            console.print(Text(f"    · {item['content']}", style="dim white"))
            console.print()
            return True

        if sub == "add":
            # Re-split the original input with no limit to get all parts cleanly
            # parts = ["/memory", "add", "facts", "My name is Varun..."]
            # but original parts was split(None, 3) so parts[3] is the full rest
            # We need to re-split to separate category from content
            all_parts = inp.split(None)   # split with no limit — every word

            # /memory add <category> <content...>
            # all_parts[0]=/memory [1]=add [2]=facts [3]=My [4]=name ...
            if len(all_parts) < 4:
                show_error("Usage: /memory add <facts|preferences|projects> <content>")
                return True

            category = parts[2].lower()                  # "facts"
            fact = " ".join(parts[3:])               # "My name is Varun..."

            if category not in ("facts", "preferences", "projects"):
                show_error(f"Unknown category '{category}'. Use: facts, preferences, projects")
                return True

            saved = remember(fact, category)
            console.print()
            if saved:
                console.print(Text(f"  ✓ Remembered: {fact}", style="green"))
            else:
                console.print(Text(f"  Already known: {fact}", style="dim white"))
            console.print()
            return True

        if sub == "forget":
            all_parts = inp.split(None, 2)   # ["/memory", "forget", "the fact..."]
            if len(all_parts) < 3:
                show_error("Usage: /memory forget <fact>")
                return True
            fact    = all_parts[2]
            removed = forget(fact)
            console.print()
            if removed:
                console.print(Text(f"  ✓ Forgotten: {fact}", style="green"))
            else:
                show_error(f"Not found in memory: {fact}")
            console.print()
            return True

        if sub == "clear":
            forget_all()
            console.print()
            console.print(Text("  ✓ All memory cleared.", style="green"))
            console.print()
            return True

        show_error(f"Unknown /memory subcommand: {sub}. Use add|list|forget|clear")
        return True    # ── /notify ───────────────────────────────────────────────
    if cmd == "/notify":
        # /notify <message>
        # Quick way to test notifications or send yourself a reminder
        if len(parts) < 2:
            show_error("Usage: /notify <message>")
            return True

        message = " ".join(parts[1:])
        sent    = notify("Kairos", message)

        console.print()
        if sent:
            console.print(Text("  ✓ Notification sent.", style="green"))
        else:
            show_error("Notification failed. Check logs/notifications.log")
        console.print()
        return True
    
    # Unknown slash command
    show_error(f"Unknown command: {cmd}. Type /help for available commands.")
    return True

# ─── MAIN LOOP ─────────────────────────────────────────────────────────────

def run():
    show_welcome()

    history = []
    session = PromptSession(
        history = InMemoryHistory(),
        style   = PROMPT_STYLE,
    )

    while True:
        try:
            user_input = session.prompt(
                [("class:prompt", "  ⊱ You → ")]
            ).strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                show_farewell()
                break

            if user_input.startswith("/"):
                handle_slash_command(user_input)
                continue

            console.print()

            # Inject current working directory into every message
            # So Kairos knows where the user actually is
            import os
            cwd        = os.environ.get("KAIROS_LAUNCH_DIR", os.getcwd())
            contextual = f"[User is in directory: {cwd}]\n{user_input}"

            answer, history = run_planner(contextual, history)
            show_response(answer)

        except KeyboardInterrupt:
            show_farewell()
            break
        except Exception as e:
            show_error(f"Something went wrong: {str(e)}")