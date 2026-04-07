<div align="center">

# ⚡ KAIROS (Καιρός)

**God of the Opportune Moment**

*A locally-running, terminal-first AI agent built from scratch in Python on Linux.*

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![Linux](https://img.shields.io/badge/OS-Ubuntu%2024.04-orange?style=flat-square&logo=ubuntu)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

</div>

---

## 🧠 What is Kairos?

Kairos is an AI agent that runs entirely on your Linux machine. It can think, 
plan, and act — writing code, managing files, browsing the web, and automating 
tasks through a beautiful terminal interface.

Named after the Greek god of the opportune moment — Kairos acts precisely when 
needed, never before, never after.

---

## ✨ Features

- 🖥️ **Terminal UI** — Greek-themed, gold-accented terminal interface
- 🤖 **ReAct Agent Loop** — thinks, acts, observes, repeats until done
- 🧩 **Smart Planner** — breaks complex tasks into subtasks automatically
- 🔧 **Tool Use** — shell commands, file operations, web browsing
- 🌐 **REST API** — expose Kairos over HTTP with FastAPI
- 🐍 **Python SDK** — use Kairos programmatically in any Python script
- ⏰ **Scheduled Tasks** — run tasks automatically on a schedule
- 👁️ **FRIDAY** — background filesystem watcher that reacts to events
- 🔄 **Auto-Fallback LLM** — Groq → Gemini → phi4-mini → Mistral

---

## 🤖 LLM Providers

| Provider | Model | Role |
|---|---|---|
| **Groq** | `llama-3.3-70b-versatile` | Primary (fastest) |
| **Gemini** | `gemini-2.0-flash` | Fallback 1 |
| **phi4-mini** | via Ollama | Fallback 2 (local) |
| **Mistral** | via Ollama | Fallback 3 (local) |

Kairos automatically falls back to the next provider if one fails.
Local models (phi4-mini, Mistral) are free and run entirely on your machine.

---

## 🖥️ System Requirements

| | |
|---|---|
| OS | Ubuntu 24.04 (Linux) |
| Python | 3.12+ |
| RAM | 8GB minimum (16GB recommended) |
| Ollama | Required for local model fallback |

---

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/kairos.git
cd kairos
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Install Ollama + local models

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull local fallback models
ollama pull phi4-mini
ollama pull mistral
```

### 5. Set up API keys

```bash
cp .env.example .env
```

Edit `.env` and add your keys:
```
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

Get your keys:
- Groq (free): https://console.groq.com
- Gemini (free): https://aistudio.google.com

### 6. Run Kairos

```bash
python3 main.py
```

This starts both the terminal UI and the REST API simultaneously.

---

## 📁 Project Structure

```
Kairos/
├── .env.example          ← API key template
├── requirements.txt      ← Python dependencies
├── config.py             ← All settings
├── main.py               ← Entry point (starts UI + API)
├── llm.py                ← LLM brain with auto-fallback
├── agent.py              ← ReAct agent loop
├── planner.py            ← Multi-step task planner
├── api.py                ← REST API (FastAPI)
├── scheduler.py          ← Scheduled tasks (APScheduler)
├── friday.py             ← Background filesystem watcher
├── sdk/
│   ├── __init__.py       ← Package exports
│   └── client.py         ← Python SDK client
├── tools/
│   ├── shell.py          ← Run terminal commands
│   ├── file.py           ← File operations
│   └── browser.py        ← Web browsing
├── logs/                 ← Auto-created, git-ignored
└── ui/
    └── terminal.py       ← Terminal UI
```

---

## 🌐 REST API

The API runs at `http://127.0.0.1:8000` when Kairos is active.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat` | Send a message |
| `POST` | `/plan` | Trigger planner directly |
| `GET` | `/status` | Health check |
| `GET` | `/history` | Conversation history |
| `DELETE` | `/history` | Clear history |
| `POST` | `/jobs` | Add scheduled job |
| `GET` | `/jobs` | List all jobs |
| `DELETE` | `/jobs/{id}` | Remove a job |
| `POST` | `/jobs/{id}/run` | Run job immediately |
| `GET` | `/jobs/logs` | View scheduler logs |
| `POST` | `/watches` | Add filesystem watch |
| `GET` | `/watches` | List all watches |
| `DELETE` | `/watches/{id}` | Remove a watch |
| `GET` | `/watches/logs` | View FRIDAY logs |

Interactive docs: `http://127.0.0.1:8000/docs`

---

## 🐍 Python SDK

```python
from sdk import Kairos

k = Kairos()

# Chat
response = k.chat("list all python files in my project")
print(response)

# Check status
info = k.status()
print(info["provider"])

# Clear history
k.clear_history()
```

---

## ⏰ Scheduled Tasks

```bash
# Add a daily task
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "task": "summarize my Dev folder",
    "schedule": "every day at 08:00",
    "job_id": "morning_summary"
  }'
```

Supported schedules:
- `"every 30 minutes"`
- `"every 2 hours"`
- `"every hour"`
- `"every day at 08:00"`
- `"every monday at 09:00"`

---

## 👁️ FRIDAY — Background Watcher

```bash
# Watch for new Python files
curl -X POST http://127.0.0.1:8000/watches \
  -H "Content-Type: application/json" \
  -d '{
    "folder": "~/Dev/Kairos",
    "pattern": "*.py",
    "event": "created",
    "task": "review the new python file at {filepath}",
    "cooldown_seconds": 30,
    "local_only": true
  }'
```

---

## 🏗️ Architecture

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
  ├── shell  → run_command()
  ├── file   → read/write/etc
  └── browser→ visit/search
      ↓
  Result fed back → LLM thinks again
      ↓
  tool: "none" → final answer shown
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

*"The archer who misses his mark does not blame the target."*

**Built with Python. Runs on Linux. Thinks with AI.**

</div>