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
Your sole purpose is to analyze a complex task and break it into clear, ordered subtasks.

Each subtask must:
- Be small and focused — achievable in a single agent step
- Be self contained — not depend on memory of previous subtasks
- Include enough context so the agent knows exactly what to do

IMPORTANT RULES FOR SUBTASKS:
- For shell commands: never use "source" or activate virtual environments.
  Instead use the full path to pip e.g. "pip install fastapi uvicorn"
- For writing files: always specify the exact file path and full content inline.
- Never include steps to open a browser or verify via browser — use shell commands instead.
- Maximum 6 subtasks. Keep it focused and lean.
- Each subtask description must be detailed enough to execute without any prior context.

RULES:
- Always respond with a single JSON object — nothing else.
- Never add explanations outside the JSON.

RESPONSE FORMAT:
{
  "complexity": "simple" | "complex",
  "reasoning": "why you classified it this way",
  "subtasks": [
    {
      "id": 1,
      "description": "exact detailed instruction for the agent to execute"
    }
  ]
}

EXAMPLES:

Task: "What is the capital of France?"
{
  "complexity": "simple",
  "reasoning": "Single factual question requiring no tools.",
  "subtasks": [
    { "id": 1, "description": "What is the capital of France?" }
  ]
}

Task: "Search the web for FastAPI and create a hello world project"
{
  "complexity": "complex",
  "reasoning": "Requires web research, file creation, dependency installation and code writing.",
  "subtasks": [
    {
      "id": 1,
      "description": "Search the web for FastAPI and summarize what it is and its key benefits."
    },
    {
      "id": 2,
      "description": "Create a folder called fastapi_hello using shell command: mkdir -p fastapi_hello"
    },
    {
      "id": 3,
      "description": "Install fastapi and uvicorn using shell command: pip install fastapi uvicorn"
    },
    {
      "id": 4,
      "description": "Write a file at fastapi_hello/main.py with this exact content: from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\ndef read_root():\n    return {'message': 'Hello from Kairos!'}"
    },
    {
      "id": 5,
      "description": "Read the file fastapi_hello/main.py and confirm its contents are correct."
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
