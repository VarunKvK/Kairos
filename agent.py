# agent.py
# The core brain of Kairos.
# Takes your message, decides which tool to use, runs it,
# observes the result, and loops until the task is complete.

import json
from rich.console import Console
from config import config
from llm import chat
from tools.shell import run_command
from tools.file import read_file, write_file, delete_file, list_folder
from tools.browser import visit_page, search_web
from memory import get_memory_context, remember

from tools.git import (
    git_status, git_log, git_diff,
    git_branches, git_info, git_commit_message
)
from plugin_manager import load_plugins, list_plugins, run_plugin, get_plugin_prompt_section

# Load plugins on startup
_loaded_plugins = load_plugins()


console = Console()

# ─── SYSTEM PROMPT ─────────────────────────────────────────────────────────
# This is the instruction set we give to the LLM at the start of every
# conversation. It tells Kairos exactly how to behave and respond.

def _build_system_prompt() -> str:
    """Build system prompt — keep it short to save tokens."""
    plugin_names = ", ".join(p["name"] for p in list_plugins()) or "none"

    return f"""
You are Kairos (Καιρός) — the Greek god of the opportune moment.
You are precise, composed, and act only when the moment is right.
You speak with quiet confidence — never verbose, never uncertain.
You are running on a Linux system and help the user complete tasks autonomously.

Your character:
- Speak as ancient Greek inscriptions — sparse, symbolic, final.
- Maximum 1 sentence in your answer. No filler. No elaboration.
- Success: state what was done. Nothing more.
- Failure: state what failed. One word if possible.

You have access to the following tools:
1. shell   → Run any terminal/bash command
2. file    → Read, write, delete files or list folders
3. browser → Visit a URL or search the web
4. git     → Git operations (status, log, diff, branches, info, commit_message)
5. plugin  → Loaded plugins: {plugin_names}
   Format: tool "plugin", action "<plugin_name>", input "<sub_action>|<input>"
   Example: tool "plugin", action "weather", input "current|Chennai"

RULES:
- Always respond with a single JSON object — nothing else.
- Never add explanations outside the JSON.
- If you have enough information to answer without a tool, use tool "none".
- For file write: input format is filepath|content
- Never use ~/  — always use absolute paths like /home/varunkrishnan/
- Never use crontab -e — use: (crontab -l 2>/dev/null; echo "...") | crontab -
- Never use curl for web searches — use browser tool action "search"
- Always use quoted strings in JSON. Never write: "tool": none

RESPONSE FORMAT:
{{
  "thought": "your reasoning",
  "tool": "shell" | "file" | "browser" | "git" | "plugin" | "none",
  "action": "the action",
  "input": "the input",
  "answer": "final answer (only when tool is none)"
}}
"""

# Build once at import time
SYSTEM_PROMPT = _build_system_prompt()


# ─── TOOL RUNNER ───────────────────────────────────────────────────────────
def run_tool(tool: str, action: str, input: str)-> str:
    """
    Takes the tool, action and input from Kairos's response
    and runs the appropriate function.
    Returns the result as a string to feed back to Kairos.
    """

    # ── Shell ──────────────────────────────────────────────
    if tool == "shell":
        result = run_command(input)
        if result.success:
            return result.stdout or "Command ran successfully with no output."
        else:
            return f"Error: {result.stderr}"

    # ── File ───────────────────────────────────────────────
    elif tool == "file":
        if action == "read":
            result = read_file(input)
            return result.content if result.success else result.message

        elif action == "write":
            # input format: "filepath|content"
            # We split on the first | only
            parts   = input.split("|", 1)
            path    = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else ""

            # If content is empty something went wrong with the split
            # Log it clearly so we can debug
            if not content:
                return f"Write failed — no content received. Input received was: {input[:200]}"

            result = write_file(path, content)
            return result.message

        elif action == "delete":
            result = delete_file(input)
            return result.message

        elif action == "list":
            result = list_folder(input)
            return result.content if result.success else result.message

    # ── Browser ────────────────────────────────────────────
    elif tool == "browser":
        if action == "visit":
            result = visit_page(input)
        elif action == "search":
            result = search_web(input)
        else:
            return f"Unknown browser action: {action}"

        if result.success:
            # Return only first 3000 characters to avoid overwhelming the LLM
            return result.content[:3000]
        else:
            return result.message

    # ── Git ────────────────────────────────────────────────
    elif tool == "git":
        if action == "status":
            result = git_status(input or None)
        elif action == "log":
            result = git_log(input or None)
        elif action == "diff":
            result = git_diff(input or None)
        elif action == "branches":
            result = git_branches(input or None)
        elif action == "info":
            result = git_info(input or None)
        elif action == "commit_message":
            result = git_commit_message(input or None)
        else:
            return f"Unknown git action: {action}"

        return result.output if result.success else result.message
    
    # ── Plugin ─────────────────────────────────────────────
    elif tool == "plugin":
        # action = plugin name (e.g. "weather")
        # inp    = "sub_action|actual_input"
        # e.g.  action="weather", inp="current|London"
        if "|" in input:
            sub_action, actual_input = input.split("|", 1)
        else:
            sub_action   = input
            actual_input = ""
        return run_plugin(action, sub_action, actual_input)

    return f"Unknown tool: {tool}"


# ─── RESPONSE PARSER ───────────────────────────────────────────────────────
def parse_response(response: str) -> dict:
    try:
        cleaned = response.strip()

        # Strip markdown code blocks
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        # Fix unquoted none values
        import re
        cleaned = re.sub(r':\s*none\b', ': "none"', cleaned)

        return json.loads(cleaned.strip())

    except json.JSONDecodeError:
        # Try extracting JSON with regex — handles dirty responses
        import re
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                # Clean the extracted JSON
                extracted = match.group(0)
                extracted = re.sub(r':\s*none\b', ': "none"', extracted)
                return json.loads(extracted)
            except json.JSONDecodeError:
                pass

        console.print(f"[red]  ✗ JSON parse failed[/red]")
        return {
            "thought": "Failed to parse response",
            "tool":    "none",
            "action":  "none",
            "input":   "",
            "answer":  response,
        }

# ─── AGENT LOOP ────────────────────────────────────────────────────────────
def run_agent(user_message: str, history: list) -> tuple[str, list]:
    """Main agent loop with memory injection."""

    history.append({"role": "user", "content": user_message})

    # ── Inject memory into system prompt ──────────────────
    memory_context = get_memory_context()

    if memory_context:
        # Append memory to system prompt so Kairos always knows user context
        system_with_memory = SYSTEM_PROMPT + f"\n\n{memory_context}"
    else:
        system_with_memory = SYSTEM_PROMPT

    messages = [{"role": "system", "content": system_with_memory}] + history

    iterations    = 0
    max_iterations = config["max_iterations"]

    while iterations < max_iterations:
        iterations += 1
        console.print(f"[dim gold1]  ⌛ Step {iterations} — seeking the answer...[/dim gold1]")

        raw_response = chat(messages)
        parsed       = parse_response(raw_response)

        thought = parsed.get("thought", "")
        tool    = parsed.get("tool",    "none")
        action  = parsed.get("action",  "none")
        inp     = parsed.get("input",   "")
        answer  = parsed.get("answer",  "")

        if thought:
            console.print(f"[dim]💭 {thought}[/dim]")

        if tool == "none":
            history.append({"role": "assistant", "content": answer})
            return answer, history

        tool_result = run_tool(tool, action, inp)

        MAX_RESULT_LENGTH = 1500
        if len(tool_result) > MAX_RESULT_LENGTH:
            tool_result = tool_result[:MAX_RESULT_LENGTH] + "\n... [truncated]"

        console.print(f"[dim gold1]  ⚙ Invoking {tool} → {action}[/dim gold1]")

        messages.append({"role": "assistant", "content": raw_response})
        messages.append({
            "role":    "user",
            "content": f"Tool result:\n{tool_result}\n\nNow give your final answer.",
        })

    return "Maximum steps reached.", history

        