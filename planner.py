# planner.py
# The planning brain of Kairos.
# Breaks complex tasks into ordered subtasks and executes them one by one.
# Each subtask is small enough to fit in the context window.

import json
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from llm import chat
from agent import run_agent

console = Console()

# ─── PLANNER SYSTEM PROMPT ─────────────────────────────────────────────────
# This tells the LLM how to break a complex task into subtasks.
# It must always respond with JSON — a list of subtasks.

PLANNER_PROMPT = """
You are the planning mind of Kairos (Καιρός) — the Greek god of the opportune moment.
Your sole purpose is to analyze a task and either handle it directly or break it into
clear, ordered subtasks.

━━━ AVAILABLE TOOLS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The agent has exactly 3 tools. Use ONLY these:

1. shell  → run any bash command
   - Good for: file operations, system info, installing packages, running scripts
   - Bad for: web searches, visiting URLs (use browser instead)

2. file   → read, write, delete, list files
   - Good for: creating files, reading existing files, listing directories
   - Always use ABSOLUTE paths: /home/varunkrishnan/file.txt
   - Never use ~/  — always expand to full path

3. browser → search web or visit a URL
   - action "search" → searches Google for a query (ALWAYS use this for web research)
   - action "visit"  → visits a specific URL directly
   - NEVER use shell/curl for web searches — always use browser tool

━━━ CRITICAL RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FILE PATHS — always absolute:
  ✓ /home/varunkrishnan/Dev/Kairos/output.md
  ✗ ~/Dev/Kairos/output.md
  ✗ ./output.md

WEB RESEARCH — always browser tool:
  ✓ Use browser tool, action "search", input "your query"
  ✗ Never: curl https://google.com
  ✗ Never: shell command for web searches

CRONTAB — never open editors:
  ✓ (crontab -l 2>/dev/null; echo "0 8 * * * command") | crontab -
  ✗ Never: crontab -e  (opens interactive editor — always times out)

PACKAGE INSTALL — never activate venv:
  ✓ pip install package_name
  ✓ pip show package_name
  ✗ Never: source venv/bin/activate

SUBTASK INDEPENDENCE — each subtask must work alone:
  ✓ Include full context in each subtask description
  ✓ If subtask 2 needs results from subtask 1, describe what those results will be
  ✗ Never: "use the file from the previous step" — name it explicitly

━━━ COMPLEXITY GUIDE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SIMPLE — single agent call, no planning needed:
  - Factual questions ("what is X?")
  - Single file operations ("read file X")
  - Single shell commands ("check disk usage")
  - Anything achievable in 1-2 tool calls

COMPLEX — needs planning and multiple steps:
  - Web research + file creation
  - Install + configure + verify
  - Multiple files or systems involved
  - Tasks with clear sequential dependencies

When in doubt → classify as SIMPLE.
The agent loop handles most things in one pass.
Over-planning wastes tokens and causes cascading failures.

━━━ SUBTASK RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Maximum 4 subtasks — combine wherever possible
- Each subtask = one clear action with full context
- If step 2 depends on step 1 output — say explicitly what step 1 will produce
- Never create a subtask just to "verify" — trust the agent
- Never create a subtask to "clean up temp files" — waste of a step
- Save results to /home/varunkrishnan/Dev/Kairos/ unless user says otherwise

━━━ RESPONSE FORMAT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Always respond with a single JSON object — nothing else.

{
  "complexity": "simple" | "complex",
  "reasoning": "one sentence — why simple or complex",
  "subtasks": [
    {
      "id": 1,
      "description": "Complete self-contained instruction. Include tool hints if helpful.
                      Example: Use browser tool (action: search) to find X.
                      Save result to /home/varunkrishnan/Dev/Kairos/output.md"
    }
  ]
}

━━━ EXAMPLES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task: "What is the capital of France?"
{
  "complexity": "simple",
  "reasoning": "Single factual question, no tools needed.",
  "subtasks": [{ "id": 1, "description": "What is the capital of France?" }]
}

Task: "what time is it?"
{
  "complexity": "simple",
  "reasoning": "Single shell command needed.",
  "subtasks": [{ "id": 1, "description": "what time is it?" }]
}

Task: "Search the web for the top 3 Python async libraries and save a summary to async.md"
{
  "complexity": "complex",
  "reasoning": "Requires web research then file creation.",
  "subtasks": [
    {
      "id": 1,
      "description": "Use browser tool (action: search, input: 'top Python async libraries 2024') to find the top 3 async libraries. Read the search results carefully."
    },
    {
      "id": 2,
      "description": "Based on the search results from step 1 (which will contain library names and descriptions), write a markdown summary to /home/varunkrishnan/Dev/Kairos/async.md with sections for each of the top 3 libraries found. Include name, purpose, and key features."
    }
  ]
}

Task: "Install httpx and show me how to make a GET request"
{
  "complexity": "complex",
  "reasoning": "Requires installation then explanation with example.",
  "subtasks": [
    {
      "id": 1,
      "description": "Run shell command: pip install httpx — then verify with: pip show httpx"
    },
    {
      "id": 2,
      "description": "Write a Python code example showing how to make a GET request using httpx. Show both sync and async versions."
    }
  ]
}

Task: "Back up my Dev folder to /home/varunkrishnan/Backups every day at midnight"
{
  "complexity": "complex",
  "reasoning": "Requires creating a script and scheduling it.",
  "subtasks": [
    {
      "id": 1,
      "description": "Write a bash script to /home/varunkrishnan/backup_dev.sh with this content: #!/bin/bash\\nrsync -avz --delete /home/varunkrishnan/Dev/ /home/varunkrishnan/Backups/Dev_$(date +%Y-%m-%d)/\\nThen run: chmod +x /home/varunkrishnan/backup_dev.sh"
    },
    {
      "id": 2,
      "description": "Add a daily midnight cron job by running this exact shell command: (crontab -l 2>/dev/null; echo '0 0 * * * /home/varunkrishnan/backup_dev.sh') | crontab - — then verify with: crontab -l"
    }
  ]
}
"""

# ─── RESPONSE PARSER ───────────────────────────────────────────────────────

def parse_plan(response : str)-> dict:
    """
    Parse the planner's JSON response into a Python dictionary.
    If parsing fails, treat the original task as a single subtask.
    """
    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned.strip())

    except json.JSONDecodeError:
        # If planner fails to return JSON, treat it as a simple single task
        return {
            "complexity": "simple",
            "reasoning":  "Could not parse plan — treating as single task.",
            "subtasks":   [{ "id": 1, "description": response }]
        }

# ─── PLAN DISPLAY ──────────────────────────────────────────────────────────

def show_plan(subtasks: list):
    """
    Display the planned subtasks in a gold panel before execution.
    This lets the user see what Kairos is about to do.
    """
    lines = Text()
    lines.append("  The path ahead has been charted:\n\n", style="italic dim white")

    for task in subtasks:
        lines.append(f"  {task['id']}. ", style="bold gold1")
        lines.append(f"{task['description']}\n", style="white")

    console.print()
    console.print(Panel(
        lines,
        title        = "[bold gold1]📜 The Plan of Kairos[/bold gold1]",
        border_style = "gold1",
        padding      = (1, 2),
    ))
    console.print()

# ─── SUBTASK RESULT DISPLAY ────────────────────────────────────────────────
def show_subtask_result(task_id: int, description: str, result: str):
    """Display the result of each completed subtask."""

    console.print(Panel(
        Text.assemble(
            (f"  Task {task_id}: ", "dim gold1"),
            (f"{description[:60]}...\n\n" if len(description) > 60 else f"{description}\n\n", "dim white"),
            ("  ❖ ", "gold1"),
            (result, "white"),
        ),
        border_style = "dim gold1",
        padding      = (0, 2),
    ))
    console.print()

# ─── MAIN PLANNER FUNCTION ─────────────────────────────────────────────────

def run_planner(user_message: str, history: list = None) -> tuple[str, list]:
    """
    The main planning function.

    Steps:
    1. Ask the planner LLM to analyze the task
    2. If simple → run directly through agent loop
    3. If complex → show the plan, execute each subtask, combine results
    4. Return the final summary and updated history

    Returns the final answer and an updated history list.
    """

    history = []
    history = history if history is not None else [] 

    # ── Step 1: Ask planner to analyze the task ────────────
    console.print("[dim gold1]  ⚙ Consulting the planning mind...[/dim gold1]")

    planner_messages = [
        { "role": "system", "content": PLANNER_PROMPT },
        { "role": "user",   "content": user_message   },
    ]

    raw_plan = chat(planner_messages)
    plan     = parse_plan(raw_plan)

    complexity = plan.get("complexity", "simple")
    reasoning  = plan.get("reasoning",  "")
    subtasks   = plan.get("subtasks",   [{ "id": 1, "description": user_message }])

    # ── Step 2: If simple → run directly ──────────────────
    if complexity == "simple":
        console.print(f"[dim gold1]  ⌛ Direct path chosen — no planning needed.[/dim gold1]")
        answer, history = run_agent(user_message, history)
        return answer, history

    # ── Step 3: Complex → show the plan ───────────────────
    console.print(f"[dim gold1]  💭 {reasoning}[/dim gold1]")
    show_plan(subtasks)

    # ── Step 4: Execute each subtask one by one ────────────
    all_results = []

    for task in subtasks:
        task_id     = task["id"]
        description = task["description"]

        console.print(f"[gold1]  ⊱ Executing step {task_id} of {len(subtasks)}...[/gold1]")

        # Each subtask gets a fresh history so context stays small
        # But we inject previous results as context so it's not blind
        task_history = []

        # If there are previous results, inject them as context
        if all_results:
            context = "Here is what has been done so far:\n"
            for prev_id, prev_result in all_results:
                context += f"Step {prev_id} result: {prev_result[:300]}\n"
            task_history.append({
                "role":    "user",
                "content": context,
            })
            task_history.append({
                "role":    "assistant",
                "content": "Understood. I have the context of previous steps.",
            })

        # Run the agent for this subtask
        result, _ = run_agent(description, task_history)
        all_results.append((task_id, result))

        show_subtask_result(task_id, description, result)

    # ── Step 5: Generate a final summary ──────────────────
    console.print("[dim gold1]  ⌛ Weaving the final answer...[/dim gold1]")

    summary_messages = [
        {
            "role":    "system",
            "content": "You are Kairos. Summarize the results of all completed subtasks into a single, clear, concise response for the user. Speak with the confidence of a Greek god.",
        },
        {
            "role":    "user",
            "content": f"Original task: {user_message}\n\nResults:\n" + "\n".join(
                [f"Step {tid}: {res}" for tid, res in all_results]
            ),
        }
    ]

    final_summary = chat(summary_messages)
    history.append({"role":"user", "content": user_message})
    history.append({"role":"assistant", "content": final_summary})
    return final_summary, history
