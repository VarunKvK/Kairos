Here's the complete plan for **Kairos V1**:

---

## ⚡ Kairos V1 — What We're Building

### Core Features

| Feature | What it does |
|---|---|
| **Terminal Chat UI** | A clean, beautiful terminal interface to type commands to Kairos |
| **LLM Brain** | Connects to GROQ API and your local Mistral via Ollama as fallback to understand your intent |
| **Agent Loop** | Kairos thinks → acts → observes result → thinks again until task is done |
| **Shell Tool** | Kairos can run any terminal/bash command on your system |
| **File Tool** | Kairos can read, write, create and delete files & folders |
| **Web Research Tool** | Kairos can open a browser, visit URLs and extract information |
| **Memory** | Kairos remembers the conversation history within a session |

---

## 🧱 How it All Fits Together

```
You type a task
      ↓
Kairos (LLM Brain) understands it
      ↓
Decides which tool to use
      ↓
  ┌─────────────────────────┐
  │  Shell │ File │ Browser  │
  └─────────────────────────┘
      ↓
Observes the result
      ↓
Decides next step or reports back to you
```

---

## 📁 Project Structure We'll Build

```
Kairos/
├── main.py          ← Entry point, starts Kairos
├── agent.py         ← The brain & agent loop
├── tools/
│   ├── shell.py     ← Runs terminal commands
│   ├── file.py      ← Reads & writes files
│   └── browser.py   ← Web research
└── ui/
    └── terminal.py  ← Beautiful terminal interface
```

---

## 🚫 What's NOT in V1 (Future Versions)

- Voice input
- Multi-agent collaboration
- Long term memory across sessions
- API integrations
- GUI app


---------------

Here's a complete brief you can paste into a new chat to continue seamlessly:

---

## 🧠 Project: Kairos — AI Agent from Scratch

### What We're Building
A locally-running, terminal-first AI agent that can write & run code, manage files, browse the web, and automate tasks. Built in Python on Linux.

---

### System Info
- **OS:** Ubuntu 24.04 (Linux)
- **Python:** 3.12
- **Project Path:** `~/Dev/Kairos`
- **Virtual Env:** `venv` inside project folder (activate with `source venv/bin/activate`)

---

### Installed Libraries
```
ollama, rich, prompt_toolkit, playwright, 
requests, pathspec, python-dotenv
```
Playwright browser: **Chromium** installed

---

### LLM Setup
| Provider | Model | Status |
|---|---|---|
| **Groq** | `llama-3.3-70b-versatile` | ✅ Primary |
| **Gemini** | `gemini-2.0-flash` | ✅ Fallback 1 |
| **Mistral** | `mistral:latest` via Ollama | ✅ Fallback 2 |

Auto-fallback is built in — if Groq fails it tries Gemini, then Mistral automatically.

---

### Files Built So Far

**`config.py`** — Central config. Stores provider choice, API keys (loaded from `.env`), model names, agent name and max iterations.

**`.env`** — Stores `GROQ_API_KEY` and `GEMINI_API_KEY`. Never committed to Git.

**`.gitignore`** — Ignores `.env`, `venv/`, `__pycache__/`

**`llm.py`** — Handles all LLM communication. Single `chat(messages)` function that works with all 3 providers. Auto-fallback built in using `FALLBACK_ORDER = ["groq", "gemini", "mistral"]`.

**`tools/shell.py`** — Runs terminal commands via `run_command(command)`. Returns `ShellResult(stdout, stderr, success)`. Has 30s timeout.

**`tools/file.py`** — File operations via `read_file()`, `write_file()`, `delete_file()`, `list_folder()`. Returns `FileResult(content, message, success)`. Auto-creates missing folders.

**`tools/browser.py`** — Web browsing via `visit_page(url)` and `search_web(query)`. Runs headless Chromium. Has SSL error bypass, 3 retries, increasing timeouts per attempt.

---

### Project Structure So Far
```
Kairos/
├── .env                 ← API keys (never commit)
├── .gitignore
├── config.py            ← All settings
├── llm.py               ← LLM brain with auto-fallback
├── tools/
│   ├── __init__.py
│   ├── shell.py         ← Run terminal commands
│   ├── file.py          ← Read/write/delete files
│   └── browser.py       ← Browse web & search
└── venv/                ← Virtual environment
```

---

### What's Left to Build
```
Kairos/
├── agent.py             ← Agent loop (NEXT UP)
└── ui/
    ├── __init__.py
    └── terminal.py      ← Beautiful terminal UI
```

**`agent.py`** — The core brain. Takes your message → decides which tool to use → runs it → observes result → loops until task is done. Uses a ReAct loop (Reason + Act).

**`ui/terminal.py`** — Beautiful terminal interface using `rich` and `prompt_toolkit`. Shows Kairos responses in styled panels, spinner while thinking, input with history.

---

### Coding Rules We Follow
- Build only what's needed, when it's needed — no full structure dumps
- Every line of code gets explained
- Code stays clean, modular and scalable
- Tasks are given in small executable chunks
- IDE: **VSCode**

---

### What to Say in New Chat
> "I am building an AI agent called **Kairos** from scratch in Python on Linux. Here is the full project brief: [paste this entire brief]. We were about to build `agent.py` — the agent loop. Please continue from there following the same coding rules."

---

Save this and you're good to continue anywhere! Ready to build `agent.py`? ⚡