"""
scheduler.py — Kairos Scheduled Tasks
Runs Kairos tasks automatically on a schedule.

Schedules supported:
    "every X minutes"        → runs every X minutes
    "every X hours"          → runs every X hours
    "every hour"             → runs every 60 minutes
    "every day at HH:MM"     → runs daily at given time
    "every monday at HH:MM"  → runs weekly on given day

Jobs are persisted in jobs.json so they survive restarts.
Results are logged to logs/scheduler.log.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from planner import run_planner


# ── Paths ─────────────────────────────────────────────────────────────────────

# Base directory — wherever scheduler.py lives
BASE_DIR  = Path(__file__).parent
JOBS_FILE = BASE_DIR / "jobs.json"
LOGS_DIR  = BASE_DIR / "logs"
LOG_FILE  = LOGS_DIR / "scheduler.log"

# Make sure logs folder exists
LOGS_DIR.mkdir(exist_ok=True)


# ── Logging ───────────────────────────────────────────────────────────────────

# We use Python's built-in logging — separate from Rich console
# so scheduled task results go to a file, not the terminal
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("kairos.scheduler")


# ── Scheduler Instance ────────────────────────────────────────────────────────

# BackgroundScheduler runs in a background thread
# It doesn't block the main thread or the API
scheduler = BackgroundScheduler()


# ── Job Storage ───────────────────────────────────────────────────────────────

def load_jobs() -> list[dict]:
    """
    Load all jobs from jobs.json.
    Returns empty list if file is missing or corrupted.
    """
    try:
        content = JOBS_FILE.read_text().strip()
        if not content:
            return []
        return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_jobs(jobs: list[dict]) -> None:
    """
    Save all jobs to jobs.json.
    Pretty-printed so it's human-readable.
    """
    JOBS_FILE.write_text(json.dumps(jobs, indent=2))


def get_job(job_id: str) -> dict | None:
    """
    Find and return a single job by ID.
    Returns None if not found.
    """
    jobs = load_jobs()
    for job in jobs:
        if job["id"] == job_id:
            return job
    return None


# ── Schedule Parser ───────────────────────────────────────────────────────────

# Maps weekday names to cron day-of-week numbers
WEEKDAYS = {
    "monday":    "mon",
    "tuesday":   "tue",
    "wednesday": "wed",
    "thursday":  "thu",
    "friday":    "fri",
    "saturday":  "sat",
    "sunday":    "sun",
}

def parse_schedule(schedule: str):
    """
    Convert a human-readable schedule string into an APScheduler trigger.

    Supported formats:
        "every X minutes"        → IntervalTrigger(minutes=X)
        "every X hours"          → IntervalTrigger(hours=X)
        "every hour"             → IntervalTrigger(hours=1)
        "every day at HH:MM"     → CronTrigger(hour=HH, minute=MM)
        "every monday at HH:MM"  → CronTrigger(day_of_week='mon', hour=HH, minute=MM)

    Raises ValueError if the format isn't recognised.
    """
    s = schedule.strip().lower()

    # ── "every X minutes" ─────────────────────────────────
    match = re.match(r"every (\d+) minutes?", s)
    if match:
        mins = int(match.group(1))
        return IntervalTrigger(minutes=mins)

    # ── "every X hours" ───────────────────────────────────
    match = re.match(r"every (\d+) hours?", s)
    if match:
        hrs = int(match.group(1))
        return IntervalTrigger(hours=hrs)

    # ── "every hour" ──────────────────────────────────────
    if s == "every hour":
        return IntervalTrigger(hours=1)

    # ── "every day at HH:MM" ──────────────────────────────
    match = re.match(r"every day at (\d{1,2}):(\d{2})", s)
    if match:
        hour   = int(match.group(1))
        minute = int(match.group(2))
        return CronTrigger(hour=hour, minute=minute)

    # ── "every <weekday> at HH:MM" ────────────────────────
    match = re.match(r"every (\w+) at (\d{1,2}):(\d{2})", s)
    if match:
        day_name = match.group(1)
        hour     = int(match.group(2))
        minute   = int(match.group(3))

        if day_name not in WEEKDAYS:
            raise ValueError(
                f"Unknown day: '{day_name}'. "
                f"Use: {', '.join(WEEKDAYS.keys())}"
            )
        return CronTrigger(day_of_week=WEEKDAYS[day_name], hour=hour, minute=minute)

    raise ValueError(
        f"Cannot parse schedule: '{schedule}'. "
        "Supported formats: "
        "'every X minutes', 'every X hours', 'every hour', "
        "'every day at HH:MM', 'every monday at HH:MM'"
    )


# ── Job Execution ─────────────────────────────────────────────────────────────

def execute_job(job_id: str, task: str) -> None:
    """
    Called by APScheduler when a job's time comes.
    Runs silently — all output goes to log file, not terminal.
    """
    log.info(f"[{job_id}] Starting task: {task}")

    try:
        # Redirect all Rich console output to /dev/null
        # so scheduled jobs don't pollute the terminal UI
        import io
        from rich.console import Console as RichConsole

        # Create a silent console that writes nowhere
        silent_console = RichConsole(file=io.StringIO(), highlight=False)

        # Patch the module-level consoles temporarily
        import agent
        import planner

        original_agent_console   = agent.console
        original_planner_console = planner.console

        agent.console   = silent_console
        planner.console = silent_console

        try:
            answer, _ = run_planner(task, [])
        finally:
            # Always restore — even if run_planner crashes
            agent.console   = original_agent_console
            planner.console = original_planner_console

        log.info(f"[{job_id}] Completed. Result: {answer[:500]}")

    except Exception as e:
        log.error(f"[{job_id}] Failed: {e}")

# ── Public API ────────────────────────────────────────────────────────────────

def add_job(task: str, schedule: str, job_id: str = None) -> dict:
    """
    Add a new scheduled job.

    Args:
        task:     The task for Kairos to run (e.g. "summarize my Dev folder")
        schedule: Human-readable schedule (e.g. "every day at 08:00")
        job_id:   Optional custom ID. Auto-generated if not provided.

    Returns:
        The job dict that was created and saved.

    Raises:
        ValueError if the schedule format is invalid.
    """
    # Parse first — fail early if schedule is invalid
    trigger = parse_schedule(schedule)

    # Generate a unique ID if none provided
    if not job_id:
        job_id = str(uuid.uuid4())[:8]

    job = {
        "id":         job_id,
        "task":       task,
        "schedule":   schedule,
        "enabled":    True,
        "created_at": datetime.now().isoformat(),
    }

    # Save to jobs.json
    jobs = load_jobs()

    # Prevent duplicate IDs
    if any(j["id"] == job_id for j in jobs):
        raise ValueError(f"Job with ID '{job_id}' already exists.")

    jobs.append(job)
    save_jobs(jobs)

    # Register with APScheduler immediately
    scheduler.add_job(
        func=execute_job,
        trigger=trigger,
        id=job_id,
        args=[job_id, task],
        replace_existing=True,
    )

    log.info(f"Job added: [{job_id}] '{task}' — {schedule}")
    return job


def remove_job(job_id: str) -> bool:
    """
    Remove a job by ID.
    Removes from both jobs.json and APScheduler.

    Returns:
        True if removed, False if job not found.
    """
    jobs = load_jobs()
    original_count = len(jobs)

    # Filter out the job with this ID
    jobs = [j for j in jobs if j["id"] != job_id]

    if len(jobs) == original_count:
        # Nothing was removed — job didn't exist
        return False

    save_jobs(jobs)

    # Remove from APScheduler if it's registered
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass  # Job might not be in scheduler if it was disabled

    log.info(f"Job removed: [{job_id}]")
    return True


def list_jobs() -> list[dict]:
    """
    Return all saved jobs from jobs.json.
    """
    return load_jobs()


def run_job_now(job_id: str) -> str:
    """
    Run a job immediately, outside its schedule.
    Useful for testing a job without waiting for its trigger time.

    Returns:
        The result string from Kairos.

    Raises:
        ValueError if job not found.
    """
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job '{job_id}' not found.")

    log.info(f"[{job_id}] Manual trigger.")

    # Run synchronously so the API can return the result
    answer, _ = run_planner(job["task"], [])
    log.info(f"[{job_id}] Manual result: {answer[:500]}")
    return answer


def start_scheduler() -> None:
    """
    Start the APScheduler and reload all saved jobs.
    Call this once when the application starts.
    Safe to call multiple times — checks if already running.
    """
    if scheduler.running:
        return

    scheduler.start()

    # Reload all saved jobs into APScheduler
    jobs = load_jobs()
    reloaded = 0

    for job in jobs:
        if not job.get("enabled", True):
            continue  # Skip disabled jobs
        try:
            trigger = parse_schedule(job["schedule"])
            scheduler.add_job(
                func=execute_job,
                trigger=trigger,
                id=job["id"],
                args=[job["id"], job["task"]],
                replace_existing=True,
            )
            reloaded += 1
        except Exception as e:
            log.error(f"Failed to reload job [{job['id']}]: {e}")

    log.info(f"Scheduler started. {reloaded} job(s) loaded.")


def stop_scheduler() -> None:
    """
    Gracefully stop the APScheduler.
    Called on application shutdown.
    """
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("Scheduler stopped.")