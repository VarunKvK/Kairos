# ⚡ KAIROS (Καιρός) — Complete Project Brief
> God of the Opportune Moment — AI Agent built from scratch in Python on Linux.

---

## 🧠 What is Kairos?

Kairos is a locally-running, terminal-first AI agent that can:
- Write & execute code
- Manage files & folders
- Browse the web & do research
- Automate tasks & workflows
- Run complex multi-step tasks via a Planner
- Execute terminal commands on your Linux system

---

## 🖥️ System Info

| Key | Value |
|---|---|
| OS | Ubuntu 24.04 (Linux) |
| Python | 3.12 |
| Project Path | `~/Dev/Kairos` |
| Virtual Env | `venv` inside project folder |
| Activate venv | `source ~/Dev/Kairos/venv/bin/activate` |
| IDE | VSCode |

---

## 🤖 LLM Setup

| Provider | Model | Role |
|---|---|---|
| **Groq** | `llama-3.3-70b-versatile` | Primary (fastest, free tier) |
| **Gemini** | `gemini-2.0-flash` | Fallback 1 |
| **Mistral** | `mistral:latest` via Ollama | Fallback 2 (local, always free) |

- Auto-fallback is built in — if Groq fails it tries Gemini, then Mistral automatically
- A 1 second delay is added between fallback attempts
- History is trimmed to last 4 messages to stay within token limits

---

## 📦 Installed Libraries

```
ollama
rich
prompt_toolkit
playwright
requests
pathspec
python-dotenv
```

Playwright browser: **Chromium** installed via `playwright install chromium`

---

## 📁 Complete Project Structure

```
Kairos/
├── .env                  ← API keys (never commit)
├── .gitignore            ← Ignores .env, venv/, __pycache__/
├── config.py             ← All settings
├── llm.py                ← LLM brain with auto-fallback
├── agent.py              ← Agent loop (ReAct pattern)
├── planner.py            ← Planner for complex/multi-step tasks
├── main.py               ← Entry point
├── tools/
│   ├── __init__.py
│   ├── shell.py          ← Run terminal commands
│   ├── file.py           ← Read/write/delete files
│   └── browser.py        ← Browse web & search
└── ui/
    ├── __init__.py
    └── terminal.py       ← Terminal UI (gold, Greek themed)
```

---

## 📄 File by File Explanation

### `config.py`
Central configuration file. Stores:
- `provider` — which LLM to use (`groq`, `gemini`, `mistral`)
- `groq_api_key` and `gemini_api_key` — loaded from `.env`
- `models` — model name per provider
- `agent_name` — `Kairos`
- `max_iterations` — `10` (max agent loop steps before stopping)

### `.env`
```
GROQ_API_KEY=your_groq_key_here
GEMINI_API_KEY=your_gemini_key_here
```

### `llm.py`
Handles all LLM communication. Key details:
- Single `chat(messages)` function — all other files call this
- `FALLBACK_ORDER = ["groq", "gemini", "mistral"]`
- Each provider has its own private function: `_chat_groq()`, `_chat_gemini()`, `_chat_mistral()`
- Gemini requires message format conversion (no system role — prepended as user message, assistant → model)
- Uses `requests.Session()` explicitly to guarantee POST method
- History trimmed: `[messages[0]] + messages[-4:]` to stay within token limits
- 1 second `time.sleep()` between fallback attempts

### `tools/shell.py`
Runs terminal commands. Key details:
- Returns `ShellResult(stdout, stderr, success)`
- Uses `sys.executable` to get correct Python/pip path for the active venv
- Replaces bare `pip`/`python` calls with full paths automatically
- `timeout=60` seconds (increased from 30 for installs)
- Combines stdout + stderr when returncode != 0

### `tools/file.py`
File operations. Functions:
- `read_file(path)` → returns `FileResult(content, message, success)`
- `write_file(path, content)` → auto-creates missing parent folders
- `delete_file(path)`
- `list_folder(path)`
- All return `FileResult(content, message, success)`

### `tools/browser.py`
Web browsing. Key details:
- `visit_page(url, retries=3)` — visits URL, returns visible text
- `search_web(query)` — builds Google search URL, calls `visit_page()`
- Headless Chromium (no browser window)
- `ignore_https_errors=True` — handles SSL issues
- Blocks images/css/fonts for speed
- Timeout increases per retry: attempt 1=20s, 2=25s, 3=30s
- Returns `BrowserResult(url, content, message, success)`

### `agent.py`
The core ReAct agent loop. Key details:

**System Prompt personality:**
- Kairos speaks as the Greek god of the opportune moment
- Decisive, minimal, philosophical
- Always responds in strict JSON format

**JSON response format:**
```json
{
  "thought": "reasoning",
  "tool": "shell|file|browser|none",
  "action": "run|read|write|delete|list|visit|search|none",
  "input": "exact input for the tool",
  "answer": "final answer (only when tool is none)"
}
```

**File write format:** `filepath|content`
Example: `notes.txt|Hello World`

**Key rules in system prompt:**
- Never use `source` or activate virtual environments
- Use `pip` directly (shell.py handles correct path)
- Never run long-running servers directly — use `&` to background them
- After pip install, verify with `pip show package_name`
- Tool results truncated to 1500 characters max

**`run_tool()`** — routes tool/action to the right function
**`parse_response()`** — parses JSON, handles markdown code block wrapping
**`run_agent(user_message, history)`** — main loop, returns `(answer, history)`

### `planner.py`
Breaks complex tasks into subtasks. Key details:
- Analyzes task → returns `complexity: simple|complex`
- Simple tasks → go directly to `run_agent()`
- Complex tasks → breaks into max 6 subtasks → runs each through `run_agent()`
- Each subtask gets a **fresh history** with previous results injected as context
- Previous results injected: `Step N result: first 300 chars`
- Final summary generated by calling LLM after all subtasks complete
- `show_plan()` displays subtasks in gold panel before execution

**Planner rules:**
- Never use `source` or activate venvs
- Never open browser to verify — use curl
- Max 6 subtasks
- Each subtask must be fully self-contained with enough context

### `ui/terminal.py`
Greek-themed, Claude Code inspired terminal UI. Key details:
- **Color:** Gold (`gold1`) as primary accent
- **Welcome:** Instant load — no animation. Name + subtitle + provider info
- **Steps:** All visible as clean one-liners
- **Response:** Gold rule → answer text → dim gold rule. No panels.
- **Error:** `⚔ message` in red
- **Farewell:** Goethe quote + Greek dismissal line
- **`KairosLoader`** — animated `⌛` loader, transient (erases itself)
- **Prompt:** `⊱ You →` in gold

### `main.py`
```python
from ui.terminal import run

if __name__ == "__main__":
    run()
```

---

## 🔧 How to Run

```bash
cd ~/Dev/Kairos
source venv/bin/activate
python3 main.py
```

---

## 🏗️ Architecture Overview

```
You type a task
      ↓
  run_planner()          ← planner.py
      ↓
  Is it complex?
  YES → break into subtasks (max 6)
  NO  → go directly to agent
      ↓
  run_agent()            ← agent.py
      ↓
  LLM thinks → JSON response
      ↓
  run_tool()
  ├── shell  → run_command()     ← tools/shell.py
  ├── file   → read/write/etc    ← tools/file.py
  └── browser→ visit/search      ← tools/browser.py
      ↓
  Result fed back → LLM thinks again
      ↓
  tool: "none" → final answer shown
```

---

## ✅ What's Working

- [x] Terminal UI with Greek theme
- [x] LLM with auto-fallback (Groq → Gemini → Mistral)
- [x] Shell tool — runs any bash command
- [x] File tool — read, write, delete, list
- [x] Browser tool — visit URLs, search web
- [x] Agent loop (ReAct pattern)
- [x] Planner for complex multi-step tasks
- [x] Context window management (trimming)
- [x] Tool result truncation (1500 chars)
- [x] Correct pip/python path resolution for venv
- [x] Git initialized with .gitignore

---

## 🚀 What's Next (In Priority Order)

### 1. 🌐 REST API
Expose Kairos as an HTTP API using FastAPI so external tools can talk to it.

**Planned endpoints:**
```
POST /chat        → send a message, get a response
POST /plan        → trigger the planner directly  
GET  /status      → check if Kairos is running
GET  /history     → get conversation history
DELETE /history   → clear conversation history
```

**File to create:** `api.py`
**Library needed:** `fastapi`, `uvicorn`

---

### 2. 📦 Python SDK
A clean Python package that wraps the REST API so Kairos can be used programmatically.

```python
from kairos import Kairos

k = Kairos()
response = k.chat("list all files in my project")
print(response)
```

**Folder to create:** `sdk/`
**Files to create:** `sdk/__init__.py`, `sdk/client.py`

---

### 3. ⏰ Scheduled Tasks
Let Kairos run tasks automatically at set times using a scheduler.

```
"Every morning at 8am summarize my project folder"
"Every Friday clean up temp files"
```

**File to create:** `scheduler.py`
**Library needed:** `apscheduler`

---

### 4. 🤖 FRIDAY Feature
Kairos runs proactively in the background. Watches for triggers, monitors files, responds to events without you asking.

```
"Watch my Dev folder — if a new .py file appears, review it"
"If CPU goes above 90%, alert me and kill the heaviest process"
```

**File to create:** `friday.py`
**Library needed:** `watchdog`

---

## 💬 How to Continue in a New Chat

Paste this into the new chat:

> "I am building an AI agent called **Kairos** from scratch in Python on Linux.
> Here is the complete project brief: [paste this entire file].
> Everything listed under ✅ What's Working is already built and tested.
> We were about to build the **REST API** — `api.py` using FastAPI.
> Please continue from there following the same coding rules:
> - Build only what's needed, when it's needed
> - Explain every line of code
> - Keep code clean, modular and scalable
> - Give tasks in small executable chunks
> - IDE is VSCode, OS is Ubuntu 24.04"


Issue I faced:
⊱ You → Now run this command "curl -s -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what is 2 + 2", "use_planner": false}' \
  | python3 -m json.tool"

  The path ahead has been charted:                                                                   │
│                                                                                                       │
│    1. Run the shell command: curl -s -X POST http://127.0.0.1:8000/chat -H 'Content-Type:             │
│  application/json' -d '{"message": "what is 2 + 2", "use_planner": false}'                            │
│    2. Pipe the output of the curl command to python3 -m json.tool for formatting     

Task 2: Pipe the output of the curl command to python3 -m json.tool ...                            │
│                                                                                                       │
│    ❖ The curl command failed to resolve the host, resulting in an empty output that could not be      │
│  formatted as JSON.  

 Mortal, I, Kairos, shall impart upon thee the culmination of our endeavors. The query "what is 2 + 2" 
hath been posed to the realm of knowledge, and the answer, much like the whispers of the gods, is clear: 
the result is indeed 4. However, the mortal coil of technology hath faltered, for the curl command, a 
mere messenger, failed to resolve the host, thus yielding an empty output, devoid of the sacred JSON 
format. Thus, I present to thee a twofold truth: the mathematical certainty of 2 + 2, and the frailty of 
mortal technological pursuits.


Issue:
 ⊱ You → Now run this command ""

  ⚙ Consulting the planning mind...
  ⌛ Direct path chosen — no planning needed.
  ⌛ Step 1 — seeking the answer...
✗ groq failed: 429 Client Error: Too Many Requests for url: 
https://api.groq.com/openai/v1/chat/completions
→ Trying next provider...
✗ gemini failed: 429 Client Error: Too Many Requests for url: 
https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=AIzaSyD3O9YK
pegJzPuaUsaqtb-g1g7ygttQ6BE
→ Trying next provider...