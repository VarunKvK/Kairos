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
        answer, history = run_planner(user_input)
    finally:
        # Always restore original print even if something fails
        console.print = original_print

    return answer, history


# ─── MAIN LOOP ─────────────────────────────────────────────────────────────

def run():
    """
    The main loop of Kairos.
    Keeps asking for input and running the agent until the user types 'exit'.
    """

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

            console.print()
            answer, history = run_planner(user_input)
            show_response(answer)

        except KeyboardInterrupt:
            show_farewell()
            break

        except Exception as e:
            show_error(f"Something went wrong: {str(e)}")