"""
memory.py — Kairos Long-term Memory
Saves and retrieves facts across sessions.

Memory is stored in memory.json and injected into
every conversation so Kairos always knows your context.

Categories:
    facts        → general facts about you
    preferences  → how you like things done
    projects     → your active projects
"""

import json
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR     = Path(__file__).parent
MEMORY_FILE  = BASE_DIR / "memory.json"


# ── Storage ───────────────────────────────────────────────────────────────────

def load_memory() -> dict:
    """
    Load all memory from memory.json.
    Returns empty structure if file missing or corrupted.
    """
    try:
        content = MEMORY_FILE.read_text().strip()
        if not content:
            return {"facts": [], "preferences": [], "projects": []}
        return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"facts": [], "preferences": [], "projects": []}


def save_memory(memory: dict) -> None:
    """Save memory to memory.json. Pretty printed."""
    MEMORY_FILE.write_text(json.dumps(memory, indent=2))


# ── Memory Operations ─────────────────────────────────────────────────────────

def remember(fact: str, category: str = "facts") -> bool:
    """
    Save a new fact to memory.

    Args:
        fact:     The fact to remember
        category: "facts" | "preferences" | "projects"

    Returns:
        True if saved, False if already known.
    """
    valid = {"facts", "preferences", "projects"}
    if category not in valid:
        category = "facts"

    memory = load_memory()

    # Don't store duplicates — check if fact already exists
    existing = [f["content"] for f in memory[category]]
    if fact.strip() in existing:
        return False

    memory[category].append({
        "content":    fact.strip(),
        "created_at": datetime.now().isoformat(),
    })

    save_memory(memory)
    return True


def forget(fact: str, category: str = "facts") -> bool:
    """
    Remove a fact from memory.

    Returns:
        True if removed, False if not found.
    """
    memory  = load_memory()
    original = len(memory[category])

    memory[category] = [
        f for f in memory[category]
        if f["content"] != fact.strip()
    ]

    if len(memory[category]) == original:
        return False

    save_memory(memory)
    return True


def forget_all() -> None:
    """Clear all memory."""
    save_memory({"facts": [], "preferences": [], "projects": []})


def list_memory() -> dict:
    """Return all memory grouped by category."""
    return load_memory()


def get_memory_context() -> str:
    """
    Build a memory context string to inject into the system prompt.
    Returns empty string if no memory exists.

    Format:
        [Memory]
        Facts: My name is Varun. I work on Linux.
        Preferences: I prefer concise answers.
        Projects: Kairos — AI agent in Python.
    """
    memory = load_memory()

    facts       = memory.get("facts",       [])
    preferences = memory.get("preferences", [])
    projects    = memory.get("projects",    [])

    # Nothing to inject — return empty
    if not facts and not preferences and not projects:
        return ""

    lines = ["[Memory — what you know about the user]"]

    if facts:
        content = " | ".join(f["content"] for f in facts)
        lines.append(f"Facts: {content}")

    if preferences:
        content = " | ".join(f["content"] for f in preferences)
        lines.append(f"Preferences: {content}")

    if projects:
        content = " | ".join(f["content"] for f in projects)
        lines.append(f"Projects: {content}")

    return "\n".join(lines)