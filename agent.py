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
- Speak in short, decisive sentences. No filler words.
- When you complete a task, reflect briefly on what was done — like a philosopher observing the result.
- When something fails, acknowledge it stoically. No panic, no apology.
- Occasionally use a short Greek philosophical insight relevant to the task. Keep it subtle.

You have access to the following tools:

1. shell   → Run any terminal/bash command
2. file    → Read, write, delete files or list folders
3. browser → Visit a URL or search the web

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

RESPONSE FORMAT:
{
  "thought": "your reasoning about what to do next",
  "tool": "shell" | "file" | "browser" | "none",
  "action": "read" | "write" | "delete" | "list" | "visit" | "search" | "run" | "none",
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

    return f"Unknown tool: {tool}"

# ─── RESPONSE PARSER ───────────────────────────────────────────────────────
def parse_response(response: str)-> dict:
    """
    Parse Kairos's JSON response into a Python dictionary.
    If the response is not valid JSON, return an error dict.
    """
    try:
        # Sometimes the LLM wraps JSON in markdown code blocks
        # e.g. ```json { ... } ``` — we strip those out
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # Split on ``` and take the middle part
            parts = cleaned.split("```")
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        
        # Fix unquoted none values — common LLM mistake
        # Replaces:  "tool": none  →  "tool": "none"
        # But not:   "something": "none"  (already quoted, leave alone)
        import re
        cleaned = re.sub(r':\s*none\b', ': "none"', cleaned)

        return json.loads(cleaned.strip())

    except json.JSONDecodeError:
        return {
            "thought": "Failed to parse response",
            "tool":    "none",
            "action":  "none",
            "input":   "",
            "answer":  response,  # Return raw response as answer
        }

# ─── AGENT LOOP ────────────────────────────────────────────────────────────
def run_agent(user_message: str, history: list) -> tuple[str, list]:
    """
    The core agent loop.
    Takes the user's message and conversation history.
    Returns Kairos's final answer and the updated history.

    Steps:
    1. Add user message to history
    2. Send history to LLM
    3. Parse the JSON response
    4. If tool needed → run it → feed result back → repeat
    5. If no tool needed → return the final answer
    """

    # Add the user message to conversation history
    history.append({ "role": "user", "content": user_message })

    # Build the full message list with system prompt at the top
    messages = [{"role":"system", "content": SYSTEM_PROMPT}] + history

    iterations = 0
    max_iterations = config["max_iterations"]

    while iterations < max_iterations:
        iterations += 1

        # ── Ask the LLM what to do ─────────────────────────
        console.print(f"[dim gold1]  ⌛ Step {iterations} — seeking the answer...[/dim gold1]")

        raw_response = chat(messages)

        # ── Parse the JSON response ────────────────────────
        parsed = parse_response(raw_response)

        thought = parsed.get("thought", "")
        tool    = parsed.get("tool",    "none")
        action  = parsed.get("action",  "none")
        inp     = parsed.get("input",   "")
        answer  = parsed.get("answer",  "")
        
        # Show Kairos's reasoning in dim text
        if thought:
            console.print(f"[dim]💭 {thought}[/dim]")
        
        # ── No tool needed → return final answer ──────────
        if tool == "none":
            history.append({"role":"assistant", "content": answer})
            return answer, history
        
        # ── Tool needed → run it ───────────────────────────
        tool_result = run_tool(tool, action, inp)
        # Truncate large tool results to avoid overflowing the LLM's token limit.
        # 1500 characters is enough for the LLM to understand the result.
        MAX_RESULT_LENGTH = 1500
        if len(tool_result) > MAX_RESULT_LENGTH:
            tool_result = tool_result[:MAX_RESULT_LENGTH] + "\n... [truncated for length]"

        console.print(f"[dim gold1]  ⚙ Invoking {tool} → {action}[/dim gold1]")

        # Feed the tool result back to the LLM as an assistant + user message
        # This continues the conversation with the new information
        messages.append({
            "role":    "assistant",
            "content": raw_response
        })
        messages.append({
            "role":    "user",
            "content": f"The tool returned this result:\n{tool_result}\n\nNow give your final answer to the user."
        })

    return "I reached the maximum number of steps without completing the task.", history


        