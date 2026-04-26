# ⚡ KAIROS — Complete Project Status
> Last updated: April 2026 | For context continuity in new chats

---

## 🧠 What is Kairos?

Kairos is a locally-running, terminal-first AI agent built from scratch in Python on Linux that can:
- Write & execute code
- Manage files & folders
- Browse the web & do research
- Automate tasks & workflows
- Run complex multi-step tasks via a Planner
- Execute terminal commands on your Linux system
- Watch filesystem events and react autonomously (FRIDAY)
- Run scheduled tasks automatically
- Send desktop notifications
- Remember facts across sessions

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
| Global Command | `kairos` (from anywhere) |
| API Port | `8765` |

---

## 🤖 LLM Setup

| Provider | Model | Role |
|---|---|---|
| **Groq** | `llama-3.3-70b-versatile` | Primary |
| **Gemini 2.0** | `gemini-2.0-flash` | Fallback 1 |
| **Gemini 1.5** | `gemini-1.5-flash-latest` | Fallback 2 |
| **phi4-mini** | via Ollama | Fallback 3 (local) |
| **Mistral** | `mistral:latest` via Ollama | Fallback 4 (local) |

**Fallback order:** `["groq", "gemini", "gemini15", "gemma", "mistral"]`

- Rate limit (429) → waits 10 seconds before trying next
- Local models use threading with 180s timeout
- History trimmed to last 4 messages

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
fastapi
uvicorn
apscheduler
watchdog
plyer
duckduckgo-search
setuptools
```

---

## 📁 Complete Project Structure

```
Kairos/
├── .env                      ← API keys (never commit)
├── .env.example              ← Template for API keys
├── .gitignore
├── requirements.txt
├── setup.py                  ← Makes SDK installable
├── LICENSE
├── README.md
├── config.py                 ← All settings
├── main.py                   ← Entry point (starts API + UI)
├── server.py                 ← Standalone API server (used by systemd)
├── api.py                    ← REST API (FastAPI) — port 8765
├── agent.py                  ← ReAct agent loop
├── planner.py                ← Multi-step task planner
├── llm.py                    ← LLM brain with auto-fallback
├── memory.py                 ← Long-term memory
├── scheduler.py              ← Scheduled tasks (APScheduler)
├── friday.py                 ← Filesystem watcher (watchdog)
├── notifications.py          ← Desktop notifications (plyer)
├── plugin_manager.py         ← Plugin loader and registry
├── jobs.json                 ← Persisted scheduled jobs (git-ignored)
├── watches.json              ← Persisted FRIDAY watches (git-ignored)
├── memory.json               ← Long-term memory store (git-ignored)
├── test_sdk.py               ← SDK test script
├── sdk/
│   ├── __init__.py
│   └── client.py             ← Python SDK client
├── tools/
│   ├── __init__.py
│   ├── shell.py              ← Run terminal commands
│   ├── file.py               ← File operations
│   ├── browser.py            ← Web browsing + DuckDuckGo search
│   └── git.py                ← Git operations
├── plugins/
│   ├── __init__.py
│   ├── calculator.py         ← Safe math evaluation
│   ├── system.py             ← CPU/RAM/disk/process info
│   ├── weather.py            ← Weather via wttr.in
│   ├── notes.py              ← Quick notes system
│   ├── converter.py          ← Unit/temperature/timezone converter
│   └── timer.py              ← Countdown timers with popup window
├── data/
│   └── notes.json            ← Notes storage (git-ignored)
├── logs/
│   ├── scheduler.log         ← Scheduled job logs (git-ignored)
│   ├── friday.log            ← FRIDAY event logs (git-ignored)
│   └── notifications.log     ← Notification logs (git-ignored)
└── ui/
    ├── __init__.py
    └── terminal.py           ← Terminal UI (gold, Greek themed)
```

---

## 📄 Key File Details

### `config.py`
```python
{
    "provider": "groq",
    "groq_api_key": from .env,
    "gemini_api_key": from .env,
    "agent_name": "Kairos",
    "max_iterations": 6,
    "api_port": 8765,
    "api_host": "127.0.0.1",
    "models": {
        "groq":     "llama-3.3-70b-versatile",
        "gemini":   "gemini-2.0-flash",
        "gemini15": "gemini-1.5-flash-latest",
        "mistral":  "mistral:latest",
        "gemma":    "phi4-mini",
    }
}
```

### `main.py`
- Checks if API already running on port 8765
- If yes → connects to existing (systemd)
- If no → starts its own in background thread
- Always starts terminal UI
- Shows CWD in welcome screen

### `server.py`
- Standalone API entry point
- Used by systemd service
- No terminal UI

### `api.py` — Endpoints
```
POST   /chat              → send message
POST   /plan              → trigger planner
GET    /status            → health check
GET    /history           → conversation history
DELETE /history           → clear history
POST   /jobs              → add scheduled job
GET    /jobs              → list jobs
DELETE /jobs/{id}         → remove job
POST   /jobs/{id}/run     → run job now
GET    /jobs/logs         → scheduler logs
POST   /watches           → add FRIDAY watch
GET    /watches           → list watches
DELETE /watches/{id}      → remove watch
GET    /watches/logs      → FRIDAY logs
```

### `llm.py`
- `FALLBACK_ORDER = ["groq", "gemini", "gemini15", "gemma", "mistral"]`
- Rate limit (429) → `time.sleep(10)` before next provider
- Other errors → `time.sleep(1)` before next provider
- Local models use `threading.Thread` with `timeout=180`
- `_chat_gemini()` and `_chat_gemini15()` — separate functions
- `import threading` at top

### `agent.py`
- `_build_system_prompt()` — dynamic, includes CWD, loaded plugins
- `parse_response()` — fixes unquoted `none` with regex, extracts JSON
- `run_tool()` — routes to shell/file/browser/git/plugin
- `run_agent()` — injects memory context into system prompt
- `_loaded_plugins = load_plugins()` at module level
- `SYSTEM_PROMPT = _build_system_prompt()` built once at import
- Plugin call format: `tool="plugin"`, `action="plugin_name"`, `input="sub_action|actual_input"`

### `planner.py`
- `run_planner(user_message, history=None)` — accepts external history
- `PLANNER_PROMPT` — tool-aware, max 4 subtasks, absolute paths
- Simple → direct to agent
- Complex → max 4 subtasks → each run through agent
- Subtask context injection from previous results

### `tools/browser.py`
- `visit_page(url, retries=3)` — Playwright headless Chromium
- `search_web(query)` — **DuckDuckGo search library** (not Playwright)
- Blocks images/css/fonts for speed
- Returns `BrowserResult(url, content, message, success)`
- ⚠️ CURRENT BUG: `visit_page` import error — browser.py needs fixing

### `tools/git.py`
- `git_status(repo_path)` → current status
- `git_log(repo_path, limit, since, author)` → commit history
- `git_diff(repo_path, staged, commit)` → show changes
- `git_branches(repo_path)` → list branches
- `git_info(repo_path)` → full repo summary
- `git_commit_message(repo_path)` → staged diff for commit msg

### `tools/shell.py`
- `run_command(command, timeout=60)` → `ShellResult`
- Expands `~/` to full home path
- Sets `DISPLAY` and `DBUS_SESSION_BUS_ADDRESS` for GUI commands
- Uses `sys.executable` for correct pip/python path

### `memory.py`
- `remember(fact, category)` → saves to memory.json
- `forget(fact, category)` → removes from memory
- `forget_all()` → clears everything
- `list_memory()` → returns all memory
- `get_memory_context()` → builds string for system prompt injection
- Categories: `facts`, `preferences`, `projects`

### `scheduler.py`
- Uses APScheduler `BackgroundScheduler`
- `start_scheduler()` → called in API lifespan
- `stop_scheduler()` → called on shutdown
- Sends desktop notification on job completion
- Logs to `logs/scheduler.log`
- Uses explicit file handler (not basicConfig)

### `friday.py`
- Uses watchdog `Observer`
- `start_friday()` → starts observer first, then registers watches
- `_register_watch()` → returns watchdog watch object, stored in `scheduled_watches`
- `run_task_silently()` → suppresses Rich output, optionally forces local models
- Sends desktop notification on event
- Logs to `logs/friday.log`
- Uses explicit file handler (not basicConfig)

### `notifications.py`
- `notify(title, message, timeout)` → desktop notification
- `notify_friday(event, filepath, result)` → FRIDAY preset
- `notify_scheduler(job_id, task, result)` → scheduler preset
- `notify_agent(task, result)` → agent preset
- `notify_error(source, error)` → error preset
- `_ensure_display_env()` → sets DISPLAY/DBUS for background threads

### `plugin_manager.py`
- `load_plugins()` → scans `plugins/` folder, imports valid plugins
- `list_plugins()` → returns info about all loaded plugins
- `run_plugin(name, action, input)` → executes a plugin
- `get_plugin_prompt_section()` → builds system prompt addition
- Valid plugin must have: `PLUGIN_NAME`, `PLUGIN_DESCRIPTION`, `PLUGIN_ACTIONS`, `run()`

### `ui/terminal.py`
- `_api(method, endpoint, body)` → all slash commands go through API
- Slash commands: `/watch`, `/job`, `/memory`, `/notify`, `/plugins`, `/open`, `/timer`
- `/open` handles: URLs, search queries, shortcuts, relative paths, CWD-relative paths
- CWD injected into every user message: `[User is in directory: {cwd}]\n{message}`
- History passed to `run_planner(user_input, history)` correctly

### `plugins/timer.py`
- Opens a **separate terminal window** with live countdown automatically
- Uses `gnome-terminal` (falls back to xterm, konsole, xfce4-terminal)
- Writes bash script to `/tmp/kairos_timer_{id}.sh`
- Sends desktop notification when done
- `_timers` dict tracks active timers

---

## ✅ What's Working

- [x] Terminal UI with Greek theme, shows CWD
- [x] Global `kairos` command from anywhere
- [x] LLM auto-fallback (Groq → Gemini → Gemini15 → phi4-mini → Mistral)
- [x] Rate limit detection — waits 10s before fallback
- [x] Shell tool (with ~ expansion, DISPLAY env)
- [x] File tool
- [x] Browser tool (visit_page with Playwright)
- [x] DuckDuckGo search (no bot detection)
- [x] Git tool (status, log, diff, branches, info, commit_message)
- [x] Agent loop (ReAct pattern)
- [x] Better Planner (tool-aware, max 4 subtasks, absolute paths)
- [x] REST API (FastAPI, port 8765, 14 endpoints)
- [x] Python SDK (installable via pip install -e .)
- [x] systemd service (auto-start on boot, auto-restart on crash)
- [x] Scheduled Tasks (APScheduler, /job commands via API)
- [x] FRIDAY filesystem watcher (/watch commands via API)
- [x] Desktop Notifications (plyer)
- [x] Long-term Memory (/memory commands, injected into prompt)
- [x] Plugin System (auto-loads from plugins/)
- [x] Plugins: calculator, system, weather, notes, converter, timer
- [x] Timer with auto-opening terminal window
- [x] /open command (files, folders, URLs, search, shortcuts)
- [x] CWD awareness (injected into every message)

---

## 🐛 Current Bug To Fix

### `tools/browser.py` — Import Error

```
ImportError: cannot import name 'visit_page' from 'tools.browser'
```

The file got corrupted when adding DuckDuckGo changes.

**What the file should contain:**

```python
"""
tools/browser.py — Web browsing and search
visit_page() → Playwright headless Chromium
search_web() → DuckDuckGo search library (no bot detection)
"""

import asyncio
from dataclasses import dataclass
from playwright.async_api import async_playwright
from duckduckgo_search import DDGS


@dataclass
class BrowserResult:
    url:     str
    content: str
    message: str
    success: bool


def visit_page(url: str, retries: int = 3) -> BrowserResult:
    """Visit a URL using headless Chromium. Returns visible text."""
    for attempt in range(retries):
        try:
            timeout = 20 + (attempt * 5)
            content = asyncio.run(_visit(url, timeout))
            return BrowserResult(
                url     = url,
                content = content,
                message = "OK",
                success = True,
            )
        except Exception as e:
            if attempt == retries - 1:
                return BrowserResult(
                    url     = url,
                    content = "",
                    message = str(e),
                    success = False,
                )


async def _visit(url: str, timeout: int) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
            ignore_https_errors=True,
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        await page.route(
            "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf}",
            lambda r: r.abort()
        )
        await page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
        content = await page.inner_text("body")
        await browser.close()
        return content[:5000]


def search_web(query: str) -> BrowserResult:
    """
    Search using DuckDuckGo library.
    No bot detection — clean results directly.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))

        if not results:
            return BrowserResult(
                url     = f"ddg:{query}",
                content = "No results found.",
                message = "No results.",
                success = False,
            )

        lines = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'No title')}")
            lines.append(f"   {r.get('href', '')}")
            lines.append(f"   {r.get('body', '')[:200]}")
            lines.append("")

        return BrowserResult(
            url     = f"ddg:{query}",
            content = "\n".join(lines),
            message = "Search complete.",
            success = True,
        )

    except Exception as e:
        return BrowserResult(
            url     = f"ddg:{query}",
            content = "",
            message = f"Search failed: {e}",
            success = False,
        )
```

---

## 🚀 What's Next (In Order)

```
1.  ✅ systemd service
2.  ✅ Long-term memory (B1)
3.  ✅ Desktop Notifications (C2)
4.  ✅ Better Planner (B2)
5.  ✅ Git Integration (C5)
6.  ✅ Plugin System (C4)
7.  ✅ Starter plugins (calculator, system, weather)
8.  ✅ Utility plugins (notes, converter, timer)
9.  ⏳ Fix browser.py import bug          ← DO THIS FIRST
10. ⏳ Voice Input (C1)
11. ⏳ Multi-agent (C6)
12. ⏳ Excel Tool
13. ⏳ Notion Tool
14. ⏳ Browser Extension
15. ⏳ Telegram Bot (notifications + control)
16. ⏳ Web Dashboard (C3)
```

---

## 🔧 How to Run

```bash
# Start everything (API + terminal UI)
kairos

# Or manually
cd ~/Dev/Kairos
source venv/bin/activate
python3 main.py

# API only (systemd manages this automatically)
sudo systemctl start kairos
sudo systemctl status kairos

# View logs
journalctl -u kairos -f
tail -f ~/Dev/Kairos/logs/scheduler.log
tail -f ~/Dev/Kairos/logs/friday.log
```

---

## 🌐 API

```
Base URL: http://127.0.0.1:8765
Docs:     http://127.0.0.1:8765/docs
```

---

## ⌨️ Slash Commands

```
/help                          → show all commands
/watch add <folder> <pattern> <event> "<task>"
/watch list
/watch remove <id>
/job add "<task>" | "<schedule>"
/job list
/job remove <id>
/job run <id>
/memory add <facts|preferences|projects> <content>
/memory list
/memory forget <content>
/memory clear
/plugins                       → list loaded plugins
/notify <message>              → send desktop notification
/open <file|folder|url>        → open in GUI
/open search <query>           → open browser with search
/open <shortcut>               → downloads, dev, kairos, home, etc.
```

---

## 💬 How to Continue in New Chat

> "I am building an AI agent called **Kairos** from scratch in Python on Linux.
> Here is the complete project status: [paste this document].
> Everything under ✅ What's Working is built and tested.
> The current bug to fix is the `tools/browser.py` import error.
> After fixing that we move to **Voice Input (C1)** using `faster-whisper`.
> Please continue following these rules:
> - Build only what's needed, when it's needed
> - Explain every line of code
> - Keep code clean, modular and scalable
> - Give tasks in small executable chunks
> - IDE is VSCode, OS is Ubuntu 24.04"