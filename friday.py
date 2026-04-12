"""
friday.py — Kairos FRIDAY (Filesystem Reactive Intelligence Day-to-day Assistant)
Watches your filesystem and reacts to events automatically.

Watches supported:
    "created"  → a new file appeared
    "modified" → a file was changed
    "deleted"  → a file was removed
    "any"      → any of the above

Safeguards built in:
    - cooldown_seconds     → minimum gap between triggers (default 30s)
    - max_triggers_per_day → daily cap per watch (default 20)
    - local_only           → use only local models, never Groq/Gemini (default True)
    - pattern filtering    → only react to specific file types (e.g. *.py)

Results logged to logs/friday.log
"""
import fnmatch
import json
import logging
import os
import uuid
from datetime import datetime, date
from pathlib import Path
from threading import Lock

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from planner import run_planner
from notifications import notify_friday

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR     = Path(__file__).parent
WATCHES_FILE = BASE_DIR / "watches.json"
LOGS_DIR     = BASE_DIR / "logs"
LOG_FILE     = LOGS_DIR / "friday.log"

LOGS_DIR.mkdir(exist_ok=True)


# ── Logging ───────────────────────────────────────────────────────────────────

# Don't use basicConfig — it's a one-time global setup and scheduler.py
# calls it first. Use an explicit file handler instead so friday.log
# always goes to the right place regardless of import order.

log = logging.getLogger("kairos.friday")
log.setLevel(logging.INFO)

# Only add the handler once — avoid duplicate log entries on reload
if not log.handlers:
    _file_handler = logging.FileHandler(LOG_FILE)
    _file_handler.setLevel(logging.INFO)
    _file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    log.addHandler(_file_handler)


# ── State ─────────────────────────────────────────────────────────────────────

# watchdog Observer — single instance manages all watches
observer = Observer()

# Lock prevents race conditions when multiple events fire simultaneously
# e.g. two files created at the same time
state_lock = Lock()

# Tracks the last time each watch fired
# { watch_id: datetime }
last_trigger: dict[str, datetime] = {}

# Tracks how many times each watch has fired today
# { watch_id: { "date": date, "count": int } }
trigger_counts: dict[str, dict] = {}

# ── Watch Storage ─────────────────────────────────────────────────────────────

def load_watches() -> list[dict]:
    """Load all watches from watches.json."""
    try:
        content = WATCHES_FILE.read_text().strip()
        if not content:
            return []
        return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_watches(watches: list[dict]) -> None:
    """Save all watches to watches.json."""
    WATCHES_FILE.write_text(json.dumps(watches, indent=2))


def get_watch(watch_id: str) -> dict | None:
    """Find a single watch by ID. Returns None if not found."""
    for watch in load_watches():
        if watch["id"] == watch_id:
            return watch
    return None

# ── Safeguard Checks ──────────────────────────────────────────────────────────

def is_on_cooldown(watch_id: str, cooldown_seconds: int) -> bool:
    """
    Returns True if this watch fired too recently.
    Prevents the same watch from spamming LLM calls.
    """
    if watch_id not in last_trigger:
        return False

    elapsed = (datetime.now() - last_trigger[watch_id]).total_seconds()
    return elapsed < cooldown_seconds


def is_daily_cap_reached(watch_id: str, max_per_day: int) -> bool:
    """
    Returns True if this watch has hit its daily trigger limit.
    Resets automatically at midnight.
    """
    today = date.today()

    if watch_id not in trigger_counts:
        return False

    entry = trigger_counts[watch_id]

    # Reset count if it's a new day
    if entry["date"] != today:
        trigger_counts[watch_id] = {"date": today, "count": 0}
        return False

    return entry["count"] >= max_per_day


def record_trigger(watch_id: str) -> None:
    """
    Record that a watch just fired.
    Updates last_trigger time and increments daily count.
    """
    today = date.today()
    last_trigger[watch_id] = datetime.now()

    if watch_id not in trigger_counts or trigger_counts[watch_id]["date"] != today:
        trigger_counts[watch_id] = {"date": today, "count": 1}
    else:
        trigger_counts[watch_id]["count"] += 1


# ── LLM Routing ───────────────────────────────────────────────────────────────

def run_task_silently(task: str, local_only: bool) -> str:
    """
    Run a task through Kairos silently.
    Returns answer string — never raises.
    """
    import io
    import llm as llm_module
    import agent
    import planner as planner_module
    from rich.console import Console as RichConsole

    silent = RichConsole(file=io.StringIO(), highlight=False)

    original_agent_console   = agent.console
    original_planner_console = planner_module.console

    agent.console          = silent
    planner_module.console = silent

    original_fallback = llm_module.FALLBACK_ORDER
    if local_only:
        llm_module.FALLBACK_ORDER = ["gemma", "mistral"]

    try:
        result = run_planner(task, [])

        # run_planner returns (answer, history) tuple
        # but guard against unexpected return types
        if isinstance(result, tuple):
            answer = result[0]
        elif isinstance(result, str):
            answer = result
        else:
            answer = str(result)

        return answer

    finally:
        agent.console          = original_agent_console
        planner_module.console = original_planner_console
        llm_module.FALLBACK_ORDER = original_fallback
    
# ── Event Handler ─────────────────────────────────────────────────────────────

class KairosEventHandler(FileSystemEventHandler):
    """
    watchdog event handler for a single watch.
    One instance per watch — each knows its own config.
    """

    def __init__(self, watch: dict):
        super().__init__()
        self.watch_id        = watch["id"]
        self.pattern         = watch.get("pattern", "*")
        self.event_type      = watch.get("event", "any")
        self.task_template   = watch["task"]
        self.cooldown        = watch.get("cooldown_seconds", 30)
        self.max_per_day     = watch.get("max_triggers_per_day", 20)
        self.local_only      = watch.get("local_only", True)

    def _should_handle(self, event_type: str, filepath: str) -> bool:
        """
        Decide whether to handle this filesystem event.
        Checks: event type, file pattern, cooldown, daily cap.
        """
        # Check event type matches what the watch wants
        if self.event_type != "any" and event_type != self.event_type:
            return False

        # Check file matches the pattern (e.g. *.py)
        filename = Path(filepath).name
        if not fnmatch.fnmatch(filename, self.pattern):
            return False

        # Thread-safe safeguard checks
        with state_lock:
            if is_on_cooldown(self.watch_id, self.cooldown):
                log.info(f"[{self.watch_id}] Cooldown active — skipping {filepath}")
                return False

            if is_daily_cap_reached(self.watch_id, self.max_per_day):
                log.warning(f"[{self.watch_id}] Daily cap reached — skipping {filepath}")
                return False

            # All checks passed — record this trigger
            record_trigger(self.watch_id)

        return True
    
    def _handle(self, event_type: str, filepath: str) -> None:
        """
        Handle a filesystem event that passed all checks.
        Builds the task, runs it through Kairos, logs the result.
        """
        # Replace {filepath} placeholder in task template
        task = self.task.replace("{filepath}", event_path)
        task = f"[Watched folder: {self.folder}]\n{task}"

        log.info(f"[{self.watch_id}] {event_type.upper()}: {filepath}")
        log.info(f"[{self.watch_id}] Running task: {task}")

        try:
            result = run_task_silently(task, self.local_only)
            log.info(f"[{self.watch_id}] Result: {result[:500]}")

            notify_friday(event_type, filepath, result)
        except Exception as e:
            log.error(f"[{self.watch_id}] Task failed: {e}")
            from notifications import notify_error
            notify_error("FRIDAY", str(e))

    # ── watchdog callbacks ─────────────────────────────────

    def on_created(self, event):
        # Log every creation event — even ones we skip
        # This confirms watchdog is detecting files
        log.info(f"[{self.watch_id}] RAW EVENT: created → {event.src_path} (is_dir={event.is_directory})")
        if not event.is_directory:
            if self._should_handle("created", event.src_path):
                self._handle("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            if self._should_handle("modified", event.src_path):
                self._handle("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            if self._should_handle("deleted", event.src_path):
                self._handle("deleted", event.src_path)

# ── Public API ────────────────────────────────────────────────────────────────

def add_watch(
    folder:              str,
    task:                str,
    event:               str  = "created",
    pattern:             str  = "*",
    watch_id:            str  = None,
    cooldown_seconds:    int  = 30,
    max_triggers_per_day:int  = 20,
    local_only:          bool = True,
) -> dict:
    """
    Add a new filesystem watch.

    Args:
        folder:               Path to watch (e.g. "~/Dev/Kairos")
        task:                 Task template — use {filepath} as placeholder
        event:                "created" | "modified" | "deleted" | "any"
        pattern:              File pattern (e.g. "*.py", "*.log", "*")
        watch_id:             Optional custom ID — auto-generated if not given
        cooldown_seconds:     Minimum seconds between triggers (default 30)
        max_triggers_per_day: Daily trigger cap (default 20)
        local_only:           If True, skip Groq/Gemini — use local models only

    Returns:
        The watch dict that was created and saved.

    Raises:
        ValueError for invalid event type or folder.
    """
    # Validate event type
    valid_events = {"created", "modified", "deleted", "any"}
    if event not in valid_events:
        raise ValueError(f"Invalid event '{event}'. Use: {valid_events}")

    # Expand ~ to full home path
    folder_path = Path(folder).expanduser().resolve()

    if not folder_path.exists():
        raise ValueError(f"Folder does not exist: {folder_path}")

    if not folder_path.is_dir():
        raise ValueError(f"Path is not a folder: {folder_path}")

    # Generate ID if not provided
    if not watch_id:
        watch_id = str(uuid.uuid4())[:8]

    watch = {
        "id":                   watch_id,
        "folder":               str(folder_path),
        "pattern":              pattern,
        "event":                event,
        "task":                 task,
        "cooldown_seconds":     cooldown_seconds,
        "max_triggers_per_day": max_triggers_per_day,
        "local_only":           local_only,
        "enabled":              True,
        "created_at":           datetime.now().isoformat(),
    }

    # Prevent duplicate IDs
    watches = load_watches()
    if any(w["id"] == watch_id for w in watches):
        raise ValueError(f"Watch with ID '{watch_id}' already exists.")

    watches.append(watch)
    save_watches(watches)

    try:
        _register_watch(watch)
    except Exception as e:
        log.error(f"Could not register watch [{watch_id}] with observer: {e}")

    log.info(f"Watch added: [{watch_id}] {folder} — {event} {pattern}")
    return watch


def remove_watch(watch_id: str) -> bool:
    """Remove a watch by ID."""
    watches  = load_watches()
    original = len(watches)
    watches  = [w for w in watches if w["id"] != watch_id]

    if len(watches) == original:
        return False

    save_watches(watches)

    # Properly unschedule from watchdog
    if watch_id in scheduled_watches:
        try:
            observer.unschedule(scheduled_watches[watch_id])
            del scheduled_watches[watch_id]
        except Exception as e:
            log.error(f"Failed to unschedule [{watch_id}]: {e}")

    # Clean up state
    last_trigger.pop(watch_id, None)
    trigger_counts.pop(watch_id, None)

    log.info(f"Watch removed: [{watch_id}]")
    return True


def list_watches() -> list[dict]:
    """Return all saved watches."""
    return load_watches()

scheduled_watches: dict = {}

def _register_watch(watch: dict) -> None:
    """
    Register a single watch with the watchdog Observer.
    Works whether observer is running or not.
    """
    handler = KairosEventHandler(watch)
    folder  = watch["folder"]

    # Schedule returns a watch object we need to keep
    # so we can unschedule it later
    watchdog_watch = observer.schedule(handler, folder, recursive=True)
    scheduled_watches[watch["id"]] = watchdog_watch
    log.info(f"Registered watch [{watch['id']}] on {folder}")


def start_friday() -> None:
    """
    Start the FRIDAY filesystem watcher.
    Always starts the observer first, then registers watches.
    """
    if observer.is_alive():
        return

    # Start observer FIRST
    observer.start()
    log.info("FRIDAY observer started.")

    # Register saved watches — skip any already registered
    watches = load_watches()
    loaded  = 0

    for watch in watches:
        if not watch.get("enabled", True):
            continue
        # Skip if already registered — prevents double registration
        if watch["id"] in scheduled_watches:
            continue
        try:
            _register_watch(watch)
            loaded += 1
        except Exception as e:
            log.error(f"Failed to load watch [{watch['id']}]: {e}")

    log.info(f"FRIDAY ready. {loaded} watch(es) active.")    

def stop_friday() -> None:
    """
    Gracefully stop the FRIDAY watcher.
    Called on application shutdown.
    """
    if observer.is_alive():
        observer.stop()
        observer.join()
        log.info("FRIDAY stopped.")