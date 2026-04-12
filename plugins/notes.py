"""
plugins/notes.py — Quick Notes
Save, search and retrieve notes from anywhere.
Notes stored in ~/Dev/Kairos/data/notes.json

Actions:
    add      → add a new note
    list     → list all notes
    search   → search notes by keyword
    today    → show today's notes
    clear    → delete all notes
"""

import json
from datetime import datetime, date
from pathlib import Path

PLUGIN_NAME        = "notes"
PLUGIN_DESCRIPTION = "Save and retrieve quick notes, ideas and reminders"
PLUGIN_ACTIONS     = ["add", "list", "search", "today", "clear"]

# ── Storage ───────────────────────────────────────────────────────────────────

DATA_DIR   = Path(__file__).parent.parent / "data"
NOTES_FILE = DATA_DIR / "notes.json"

DATA_DIR.mkdir(exist_ok=True)


def _load() -> list[dict]:
    """Load notes from file."""
    try:
        content = NOTES_FILE.read_text().strip()
        if not content:
            return []
        return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(notes: list[dict]) -> None:
    """Save notes to file."""
    NOTES_FILE.write_text(json.dumps(notes, indent=2))


# ── Plugin Entry Point ────────────────────────────────────────────────────────

def run(action: str, input: str) -> str:
    """
    Execute a notes action.

    Input formats:
        add    → the note text
        list   → (empty)
        search → keyword to search
        today  → (empty)
        clear  → (empty)
    """
    if action == "add":
        return _add(input.strip())
    elif action == "list":
        return _list()
    elif action == "search":
        return _search(input.strip())
    elif action == "today":
        return _today()
    elif action == "clear":
        return _clear()
    else:
        return f"Unknown action: {action}"


# ── Actions ───────────────────────────────────────────────────────────────────

def _add(text: str) -> str:
    if not text:
        return "No note text provided."

    notes = _load()
    note  = {
        "id":         len(notes) + 1,
        "content":    text,
        "created_at": datetime.now().isoformat(),
        "date":       date.today().isoformat(),
    }
    notes.append(note)
    _save(notes)
    return f"Note #{note['id']} saved: {text}"


def _list() -> str:
    notes = _load()
    if not notes:
        return "No notes yet."

    lines = [f"  {len(notes)} note(s):"]
    for n in notes[-20:]:  # show last 20
        dt = n["created_at"][:10]
        lines.append(f"  [{n['id']}] {dt} — {n['content'][:80]}")

    return "\n".join(lines)


def _search(keyword: str) -> str:
    if not keyword:
        return "No search keyword provided."

    notes   = _load()
    matches = [
        n for n in notes
        if keyword.lower() in n["content"].lower()
    ]

    if not matches:
        return f"No notes found containing '{keyword}'."

    lines = [f"  {len(matches)} match(es) for '{keyword}':"]
    for n in matches:
        dt = n["created_at"][:10]
        lines.append(f"  [{n['id']}] {dt} — {n['content'][:80]}")

    return "\n".join(lines)


def _today() -> str:
    notes = _load()
    today = date.today().isoformat()

    todays = [n for n in notes if n.get("date") == today]

    if not todays:
        return f"No notes for today ({today})."

    lines = [f"  {len(todays)} note(s) today:"]
    for n in todays:
        lines.append(f"  [{n['id']}] {n['content'][:80]}")

    return "\n".join(lines)


def _clear() -> str:
    _save([])
    return "All notes cleared."