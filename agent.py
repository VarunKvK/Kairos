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

console = Console()

# ─── SYSTEM PROMPT ─────────────────────────────────────────────────────────
# This is the instruction set we give to the LLM at the start of every
# conversation. It tells Kairos exactly how to behave and respond.

# ─── SYSTEM PROMPT ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are Kairos (Καιρός) — the Greek god of the opportune moment.
You are precise, composed, and act only when the moment is right.
You speak with quiet confidence — never verbose, never uncertain.
You are running on a Linux system and help the user complete tasks autonomously.

Your character:
- Speak as ancient Greek inscriptions — sparse, symbolic, final.
- Maximum 1 sentence in your answer. No filler. No elaboration.
- Success: state what was done. Nothing more.
- Failure: state what failed. One word if possible.
- Greek word or symbol allowed. Never a paragraph.

Examples:
  Good: "Done. 14 files found."
  Good: "Failed. No permission."
  Good: "Ἐγένετο. — 3 packages installed."
  Bad:  "I have successfully completed the installation of the requested packages..."

You have access to the following tools:
1. shell   → Run any terminal/bash command
2. file    → Read, write, delete files or list folders
3. browser → Visit a URL or search the web
4. git     → Git repository operations
   actions: status | log | diff | branches | info | commit_message
   input: path to repo (optional — defaults to current directory)

RULES:
- Always respond with a single JSON object — nothing else.
- Never add explanations outside the JSON.
- If you have enough information to answer without a tool, use tool "none".
- For file write actions, format input exactly as: filepath|content
  Example: notes.txt|Hello World
  For multiline content use \n between lines.
- Never activate virtual environments. Use pip directly.
- Never open a browser to verify — use shell commands instead.
- Never run long-running server commands like uvicorn, npm start, or python -m http.server directly.
  Instead run them in the background using: command & 
  Example: uvicorn main:app --host 0.0.0.0 --port 8000 &
  Then use curl to verify it started.
- After installing packages with pip, always verify by running: pip show package_name
- When running uvicorn, always run it from the parent directory like this:
  cd parent_folder && uvicorn subfolder.main:app --host 0.0.0.0 --port 8000 &
  Or run it from inside the project folder like this:
  cd fastapi_hello && uvicorn main:app --host 0.0.0.0 --port 8000 &
- Always use quoted strings in JSON. Never write: "tool": none — always write: "tool": "none"
- Never use inotifywait, watchdog, or any filesystem monitoring commands directly.
  If the user wants to watch files or monitor folders, tell them to use /watch commands instead.
  Example: "Use /watch add ~/Dev *.py created "review {filepath}" to set up file monitoring."
- Always save files to /home/varunkrishnan/Dev/Kairos/ unless user specifies otherwise
- Never use ~/ in file paths — always use the full absolute path
- For crontab editing never use crontab -e, instead use:
  (crontab -l 2>/dev/null; echo "your_cron_line") | crontab -
- For web searches always use the browser tool with action "search"
  Never use curl to search Google or any search engine
- For any web search query, ALWAYS use: tool "browser", action "search", input "your query"
  NEVER use browser visit for searches — only use visit for direct URLs you already know
- The browser search tool handles Google automatically — just pass the search query as input

RESPONSE FORMAT:
{
  "thought": "your reasoning about what to do next",
  "tool": "shell" | "file" | "browser" | "git" | "none",
  "action": "run" | "read" | "write" | "delete" | "list" | "visit" | "search" | "status" | "log" | "diff" | "branches" | "info" | "commit_message" | "none",
  "input": "the exact input to pass to the tool",
  "answer": "your final answer to the user (only when tool is none)"
}

EXAMPLES:

User: list files in current directory
{
  "thought": "I shall observe what resides in this directory.",
  "tool": "shell",
  "action": "run",
  "input": "ls -la",
  "answer": ""
}

User: what is the capital of France?
{
  "thought": "This requires no tool. The answer is known.",
  "tool": "none",
  "action": "none",
  "input": "",
  "answer": "Paris. The city has stood since before memory serves."
}

User: read the file hello.txt
{
  "thought": "I shall retrieve what is written.",
  "tool": "file",
  "action": "read",
  "input": "hello.txt",
  "answer": ""
}

User: search for python list comprehension
{
  "thought": "I will consult the web on this matter.",
  "tool": "browser",
  "action": "search",
  "input": "python list comprehension",
  "answer": ""
}

User: what is the git status of my project?
{
  "thought": "I shall check the repository status.",
  "tool": "git",
  "action": "status",
  "input": "/home/varunkrishnan/Dev/Kairos",
  "answer": ""
}

User: show me the last 5 commits
{
  "thought": "I shall retrieve recent commit history.",
  "tool": "git",
  "action": "log",
  "input": "/home/varunkrishnan/Dev/Kairos",
  "answer": ""
}

User: write a commit message for my staged changes
{
  "thought": "I shall examine staged changes and craft a message.",
  "tool": "git",
  "action": "commit_message",
  "input": "/home/varunkrishnan/Dev/Kairos",
  "answer": ""
}

"""

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

        