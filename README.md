# Perfect — No Sensitive Files Exposed ✅

Your `.gitignore` is protecting everything correctly. No API keys, no personal data in the repo.

---

## Step 1 — Write a Proper `README.md`

```bash
nano ~/Dev/Kairos/README.md
```

Replace everything with this:

```markdown
# ⚡ KAIROS — AI Agent Built From Scratch

> **Kairos** (Καιρός) — Greek god of the opportune moment.

A locally-running, terminal-first AI agent built from scratch in Python that can:

- 🧠 Execute code and manage files
- 🌐 Browse the web and search
- 📅 Schedule tasks and automate workflows  
- 👁️ Watch filesystem events (FRIDAY)
- 🔌 Extend with plugins
- 💾 Remember facts across sessions
- 🎯 Plan and execute multi-step tasks

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Ubuntu/Debian Linux (tested on Ubuntu 24.04)
- Ollama (optional — for local models)

### Install

```bash
# Clone the repo
git clone https://github.com/YourUsername/Kairos.git
cd Kairos

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set up environment variables
cp .env.example .env
nano .env  # Add your API keys
```

### API Keys

Get free API keys:

- **Groq:** https://console.groq.com (fastest, recommended)
- **Google Gemini:** https://aistudio.google.com/app/apikey

Add them to `.env`:

```bash
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
```

### Run

```bash
# Start Kairos
python3 main.py

# Or install globally
pip install -e .
kairos  # run from anywhere
```

---

## 🎯 What Can It Do?

```
You → what files are in my current directory?
Kairos → [lists files using shell tool]

You → search for "Python async best practices" and summarize the top result
Kairos → [searches DuckDuckGo, visits page, summarizes]

You → watch my Downloads folder and summarize any new PDFs
Kairos → [sets up FRIDAY watch, auto-processes files]

You → remind me to take a break in 25 minutes
Kairos → [schedules task, sends desktop notification]
```

---

## 🛠️ Architecture

```
Kairos/
├── agent.py          — ReAct agent loop
├── planner.py        — Multi-step task planner  
├── llm.py            — LLM with auto-fallback
├── memory.py         — Long-term memory system
├── scheduler.py      — Scheduled tasks (APScheduler)
├── friday.py         — Filesystem watcher (watchdog)
├── api.py            — REST API (FastAPI)
├── tools/            — Shell, File, Browser, Git
├── plugins/          — Calculator, System, Weather, Notes, Timer, Converter
└── ui/terminal.py    — Terminal interface
```

---

## 🔧 Configuration

Edit `config.py`:

```python
config = {
    "provider": "groq",      # groq, gemini, phi, mistral
    "max_iterations": 6,     # max agent steps
    "api_port": 8765,
}
```

---

## 🔌 Plugins

Kairos auto-loads plugins from `plugins/`. Included:

- **calculator** — Safe math evaluation
- **system** — CPU/RAM/disk/process info
- **weather** — Weather lookup via wttr.in
- **notes** — Quick notes system
- **converter** — Unit/temp/timezone conversion
- **timer** — Countdown timers with popup

### Create Your Own Plugin

```python
# plugins/myplugin.py

PLUGIN_NAME = "myplugin"
PLUGIN_DESCRIPTION = "Does something useful"
PLUGIN_ACTIONS = ["action1", "action2"]

def run(action: str, input_data: str) -> str:
    if action == "action1":
        return "Result from action1"
    return "Unknown action"
```

Restart Kairos — auto-loaded.

---

## 📡 API

Kairos runs a REST API on port 8765:

```bash
# Send a message
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what is 2+2?"}'

# Add a scheduled job
curl -X POST http://127.0.0.1:8765/jobs \
  -H "Content-Type: application/json" \
  -d '{"task": "summarize news", "schedule": "every day at 08:00"}'
```

Full API docs: http://127.0.0.1:8765/docs

---

## 🐧 Systemd Service (Auto-start)

```bash
# Create service file
sudo nano /etc/systemd/system/kairos.service
```

```ini
[Unit]
Description=Kairos AI Agent API
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/Dev/Kairos
ExecStart=/home/youruser/Dev/Kairos/venv/bin/python3 server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable kairos
sudo systemctl start kairos
```

---

## 🧠 Memory System

Kairos remembers facts across sessions:

```
/memory add facts My name is Alice
/memory add preferences I prefer concise answers
/memory add projects Working on a web scraper
/memory list
```

Memory is injected into every conversation.

---

## ⚙️ FRIDAY — Filesystem Watcher

Watch folders and auto-execute tasks:

```
/watch add ~/Downloads *.pdf created "summarize {filepath}"
/watch list
/watch remove <id>
```

---

## 🎨 Tech Stack

- **LLM:** Groq (llama-3.3-70b), Google Gemini 2.5 Flash
- **Local Fallback:** Ollama (phi4-mini, mistral, gemma4)
- **Web:** Playwright (headless Chromium), DuckDuckGo Search
- **UI:** Rich, prompt_toolkit
- **API:** FastAPI
- **Scheduler:** APScheduler
- **Watcher:** Watchdog
- **Notifications:** Plyer

---

## 📝 License

MIT

---

## 🙏 Credits

Built by [VarunKvK](https://github.com/VarunKvK)

Inspired by Claude Code and the ReAct paper.

---

## 🐛 Known Issues

- Browser tool requires X11/Wayland (no headless server support yet)
- FRIDAY watches don't auto-restore on restart
- Voice input planned but not implemented

---

## 🗺️ Roadmap

- [ ] Voice input (faster-whisper)
- [ ] Multi-agent coordination
- [ ] Excel/Notion integrations
- [ ] Browser extension
- [ ] Telegram bot
- [ ] Web dashboard

---

## 💬 Contributing

PRs welcome! See open issues or propose new features.