# ui/terminal.py
# Kairos terminal UI — minimal, Claude Code inspired, Greek accents.

import time
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich.align import Align
from agent import run_agent
from planner import run_planner
from config import config

from scheduler import add_job, remove_job, list_jobs, run_job_now
from friday import add_watch, remove_watch, list_watches
from memory import remember, forget, forget_all, list_memory

console = Console()

# ─── PROMPT STYLE ──────────────────────────────────────────────────────────
PROMPT_STYLE = Style.from_dict({
    "prompt": "#d4af37 bold",
})


# ─── WELCOME SCREEN ────────────────────────────────────────────────────────

def show_welcome():
    """
    Clean, instant welcome — no animation.
    Claude Code style: just text, no heavy panels.
    """

    console.print()
    console.print(Text("  ⚡ KAIROS  Κ Α Ι Ρ Ο Σ", style="bold gold1"))
    console.print(Text("  God of the Opportune Moment", style="italic dim white"))
    console.print()
    console.print(Text(f"  Provider  {config['provider'].upper()}  ·  {config['models'][config['provider']]}", style="dim white"))
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
        task    = params.get("task",    "A file event occurred at {filepath}. Briefly describe what happened.")

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

        watch = add_watch(
            folder=folder,
            task=task,
            event=event,
            pattern=pattern,
        )

        console.print()
        console.print(Text(f"  ✓ Watch active [{watch['id']}]", style="green"))
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
            watches = list_watches()
            console.print()
            if not watches:
                console.print(Text("  No active watches.", style="dim white"))
            else:
                console.print(Text(f"  {len(watches)} active watch(es):", style="gold1"))
                for w in watches:
                    console.print(Text(f"  [{w['id']}] {w['folder']} — {w['event']} {w['pattern']}", style="dim white"))
                    console.print(Text(f"    Task: {w['task'][:80]}", style="dim white"))
            console.print()
            return True

        # ── /watch remove <id> ────────────────────────
        if sub == "remove":
            if len(parts) < 3:
                show_error("Usage: /watch remove <id>")
                return True
            watch_id = parts[2]
            removed  = remove_watch(watch_id)
            if removed:
                console.print()
                console.print(Text(f"  ✓ Watch '{watch_id}' removed.", style="green"))
                console.print()
            else:
                show_error(f"Watch '{watch_id}' not found.")
            return True

        # ── /watch add <folder> <pattern> <event> "<task>" ──
        if sub == "add":
            rest   = inp[len("/watch add"):].strip()
            tokens = rest.split(None, 3)

            if len(tokens) < 4:
                show_error('Usage: /watch add <folder> <pattern> <event> "<task>"')
                show_error('Example: /watch add ~/Dev/Kairos *.py created "review {filepath}"')
                return True

            folder  = tokens[0]
            pattern = tokens[1]
            event   = tokens[2]
            task    = tokens[3].strip('"')

            try:
                watch = add_watch(
                    folder=folder,
                    task=task,
                    event=event,
                    pattern=pattern,
                )
                console.print()
                console.print(Text(f"  ✓ Watch added [{watch['id']}]", style="green"))
                console.print(Text(f"    Folder:  {watch['folder']}", style="dim white"))
                console.print(Text(f"    Pattern: {watch['pattern']}", style="dim white"))
                console.print(Text(f"    Event:   {watch['event']}", style="dim white"))
                console.print(Text(f"    Task:    {watch['task'][:80]}", style="dim white"))
                console.print()
            except ValueError as e:
                show_error(str(e))
            return True

        # ── Natural language fallback ─────────────────
        # If subcommand isn't list/remove/add — treat the
        # entire /watch input as a natural language request
        # and let the LLM extract folder, pattern, event, task
        _handle_watch_natural_language(inp)
        return True

    # ── /job ──────────────────────────────────────────────
    if cmd == "/job":
        if len(parts) < 2:
            show_error("Usage: /job add|list|remove|run ...")
            return True

        sub = parts[1].lower()

        if sub == "list":
            jobs = list_jobs()
            console.print()
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
            job_id  = parts[2]
            removed = remove_job(job_id)
            if removed:
                console.print()
                console.print(Text(f"  ✓ Job '{job_id}' removed.", style="green"))
                console.print()
            else:
                show_error(f"Job '{job_id}' not found.")
            return True

        if sub == "run":
            if len(parts) < 3:
                show_error("Usage: /job run <id>")
                return True
            job_id = parts[2]
            try:
                console.print()
                console.print(Text(f"  ⌛ Running job '{job_id}'...", style="dim gold1"))
                result = run_job_now(job_id)
                show_response(result)
            except ValueError as e:
                show_error(str(e))
            return True

        if sub == "add":
            # Format: /job add "task description" | "every day at 08:00"
            if len(parts) < 3:
                show_error('Usage: /job add "<task>" | "<schedule>"')
                return True

            # Everything after "/job add" — split on " | "
            rest = inp[len("/job add"):].strip()

            if " | " not in rest:
                show_error('Usage: /job add "<task>" | "<schedule>"')
                return True

            task_part, schedule_part = rest.split(" | ", 1)
            task     = task_part.strip().strip('"')
            schedule = schedule_part.strip().strip('"')

            try:
                job = add_job(task=task, schedule=schedule)
                console.print()
                console.print(Text(f"  ✓ Job added [{job['id']}]", style="green"))
                console.print(Text(f"    Task:     {job['task'][:80]}", style="dim white"))
                console.print(Text(f"    Schedule: {job['schedule']}", style="dim white"))
                console.print()
            except ValueError as e:
                show_error(str(e))
            return True

        show_error(f"Unknown /job subcommand: {sub}. Use add|list|remove|run.")
        return True
    # ── /memory ───────────────────────────────────────────────
    if cmd == "/memory":
        if len(parts) < 2:
            show_error("Usage: /memory add|list|forget|clear")
            return True

        sub = parts[1].lower()

        if sub == "list":
            mem = list_memory()
            console.print()
            total = sum(len(v) for v in mem.values())
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
            # /memory add <category> <fact>
            # /memory add facts My name is Varun
            if len(parts) < 4:
                show_error('Usage: /memory add <facts|preferences|projects> <content>')
                return True
            category = parts[2].lower()
            fact     = " ".join(parts[3:]) if len(parts) > 3 else parts[2]
            saved    = remember(fact, category)
            console.print()
            if saved:
                console.print(Text(f"  ✓ Remembered: {fact}", style="green"))
            else:
                console.print(Text(f"  Already known: {fact}", style="dim white"))
            console.print()
            return True

        if sub == "forget":
            if len(parts) < 3:
                show_error('Usage: /memory forget <fact>')
                return True
            fact    = " ".join(parts[2:])
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

        show_error(f"Unknown /memory subcommand: {sub}")
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

            # ── Handle slash commands before LLM ──────────
            if user_input.startswith("/"):
                handle_slash_command(user_input)
                continue

            # ── Normal message → agent ────────────────────
            console.print()
            answer, history = run_planner(user_input, history)  # ← history passed
            show_response(answer)

        except KeyboardInterrupt:
            show_farewell()
            break

        except Exception as e:
            show_error(f"Something went wrong: {str(e)}")