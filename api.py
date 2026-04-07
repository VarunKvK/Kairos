"""
api.py — Kairos REST API
Exposes the Kairos agent and planner over HTTP using FastAPI.

Endpoints:
    POST /chat        → Send a message, get a response
    POST /plan        → Trigger the planner directly
    GET  /status      → Check if Kairos is running
    GET  /history     → Get conversation history
    DELETE /history   → Clear conversation history
"""

import time
import uvicorn

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from planner import run_planner
from agent import run_agent
from config import config


from scheduler import add_job, remove_job, list_jobs, run_job_now, start_scheduler, stop_scheduler
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from friday import (
    add_watch, remove_watch, list_watches,
    start_friday, stop_friday, LOG_FILE as FRIDAY_LOG
)


# ── App Setup ────────────────────────────────────────────────────────────────

# FastAPI() creates the application instance.
# title/version appear in the auto-generated docs at /docs
# app = FastAPI(
#     title="Kairos API",
#     description="God of the Opportune Moment — AI Agent REST Interface",
#     version="1.0.0",
# )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup and shutdown."""
    start_scheduler()   # ← start scheduler when API starts
    start_friday()
    yield
    stop_scheduler()    # ← stop scheduler when API shuts down
    stop_friday()


app = FastAPI(
    title="Kairos API",
    description="God of the Opportune Moment — AI Agent REST Interface",
    version="1.0.0",
    lifespan=lifespan,
)




# ── State ─────────────────────────────────────────────────────────────────────

# This holds the conversation history for the current session.
# It's a plain list — each item is a dict with "role" and "content".
# Lives in memory only — cleared on server restart or DELETE /history.

conversation_history: list[dict] = []

# Record when the server started - used in /status
server_start_time: float = time.time()


# ── Request / Response Models ─────────────────────────────────────────────────

# Pydantic models define the shape of incoming JSON bodies.
# FastAPI validates them automatically — wrong types return a 422 error.

class ChatRequest(BaseModel):
    """Body for POST /chat"""
    message : str                 # The user's message — required
    use_planner: bool = True      # Whether to run through planner — default True

class PlanRequest(BaseModel):
    """Body for POST /plan"""
    message : str                 # The task to plan and execute — required

class ChatResponse(BaseModel):
    """Shape of the response from /chat and /plan"""
    answer: str                   # Kairos's final answer
    history_length: int           # How many messages are in history now
    provider: str                 # Which LLM provider answered (from config)

class StatusResponse(BaseModel):
    """Shape of the response from /status"""
    status: str                 # Always "online" if reachable
    agent: str                  # Agent name from config
    provider: str                # Active LLM provider
    uptime_seconds: float       # Seconds since server started
    history_length: int         # Current number of messages in history

class HistoryResponse(BaseModel):
    """Shape of the response from GET /history"""
    history: list[dict]        # Full conversation history
    length: int                # Number of messages

class AddJobRequest(BaseModel):
    task:     str            # What Kairos should do
    schedule: str            # "every day at 08:00"
    job_id:   str = None     # Optional custom ID


class JobResponse(BaseModel):
    id:         str
    task:       str
    schedule:   str
    enabled:    bool
    created_at: str

class AddWatchRequest(BaseModel):
    folder:               str
    task:                 str
    event:                str  = "created"
    pattern:              str  = "*"
    watch_id:             str  = None
    cooldown_seconds:     int  = 30
    max_triggers_per_day: int  = 20
    local_only:           bool = True


class WatchResponse(BaseModel):
    id:                   str
    folder:               str
    pattern:              str
    event:                str
    task:                 str
    cooldown_seconds:     int
    max_triggers_per_day: int
    local_only:           bool
    enabled:              bool
    created_at:           str

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/status", response_model= StatusResponse)
def get_status():
    """
    GET /status
    Returns a health check with basic info about the running agent.
    Always returns 200 if the server is alive.
    """
    return StatusResponse(
        status = "online",
        agent = config["agent_name"],
        provider = config["provider"],
        uptime_seconds = round(time.time() - server_start_time, 2),
        history_length = len(conversation_history)
    )

@app.post("/chat", response_model= ChatResponse)
def post_chat(request: ChatRequest):
    """
    POST /chat
    Send a message to Kairos. Returns the agent's answer.

    Body:
        {
            "message": "your task here",
            "use_planner": true   ← optional, defaults to true
        }

    The planner decides whether the task is simple or complex.
    Simple → goes straight to agent.
    Complex → broken into subtasks, each run through agent.

    Conversation history is maintained across calls.
    """
    global conversation_history # We modify the module-level list

    if not request.message.strip():
        # Reject empty messages — nothing to process
        return HTTPException(status_code = 400, detail = "Message cannot be empty")

    try:
        if request.use_planner:
            # run_planner handles both simple and complex tasks.
            # It calls run_agent() internally.
            # Returns (answer, updated_history)
            answer, conversation_history = run_planner(
                request.message,
                conversation_history
            )
        else:
            # Skip the planner — go directly to the agent loop.
            # Useful for quick, known-simple tasks.
            answer,conversation_history = run_agent(
                request.message,
                conversation_history
            )

    except Exception as e:
        # Catch anything unexpected — network failures, LLM errors, etc.
        # Return 500 with the error message so the caller knows what happened.
        raise HTTPException(status_code=500, detail= str(e))
    
    # Safety net — if answer is blank, something went wrong upstream
    # Return a clear message instead of silent empty string
    if not answer or not answer.strip():
        answer = "Kairos completed the task but returned no answer. Check the server logs."
    
    return ChatResponse(
        answer = answer,
        history_length= len(conversation_history),
        provider= config['provider']
    )

@app.post("/plan", response_model= ChatResponse)
def post_plan(request: PlanRequest):
    """
    POST /plan
    Triggers the planner directly — always routes through run_planner().
    Identical to POST /chat with use_planner=true, but semantically clearer
    for callers who explicitly want planning behavior.

    Body:
        {
            "message": "your complex task here"
        }
    """
    global conversation_history

    if not request.message.strip():
        raise HTTPException(status_code = 400, detail = "Message cannot be empty.")
    
    try:
        answer,conversation_history = run_planner(
            request.message,
            conversation_history
        )
    except Exception as e:
        raise HTTPException(status_code = 500, detail= str(e))
    
    return ChatResponse(
        answer = answer,
        history_length = len(conversation_history),
        provider = config["provider"],
    )

@app.get("/history", response_model=HistoryResponse)
def get_history():
    """
    GET /history
    Returns the full conversation history for the current session.
    Each item has "role" (user/assistant/system) and "content".
    """
    return HistoryResponse(
        history=conversation_history,
        length=len(conversation_history),
    )

@app.delete("/history")
def delete_history():
    """
    DELETE /history
    Clears the conversation history entirely.
    Kairos starts fresh on the next /chat call.
    Returns a plain confirmation message.
    """
    global conversation_history
    conversation_history = []   # Reset to empty list

    # JSONResponse lets us return a plain dict without a Pydantic model
    return JSONResponse(content={"message": "History cleared.", "length": 0})


# ── Scheduler Endpoints ───────────────────────────────────────────────────────

@app.post("/jobs", response_model=JobResponse)
def post_add_job(request: AddJobRequest):
    """
    POST /jobs
    Add a new scheduled job.

    Body:
        {
            "task": "summarize my Dev folder",
            "schedule": "every day at 08:00",
            "job_id": "morning_summary"   ← optional
        }
    """
    try:
        job = add_job(
            task=request.task,
            schedule=request.schedule,
            job_id=request.job_id,
        )
        return JobResponse(**job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/jobs")
def get_jobs():
    """
    GET /jobs
    List all scheduled jobs.
    """
    return {"jobs": list_jobs(), "count": len(list_jobs())}


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    removed = remove_job(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    # Explicit JSONResponse instead of plain dict
    return JSONResponse(content={"message": f"Job '{job_id}' removed."})


@app.post("/jobs/{job_id}/run")
def post_run_job(job_id: str):
    """
    POST /jobs/{job_id}/run
    Run a job immediately outside its schedule.
    """
    try:
        result = run_job_now(job_id)
        return {"job_id": job_id, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/jobs/logs")
def get_logs(lines: int = 50):
    """
    GET /jobs/logs?lines=50
    Returns the last N lines from the scheduler log file.
    Default is 50 lines.
    """
    from scheduler import LOG_FILE

    if not LOG_FILE.exists():
        return JSONResponse(content={"logs": [], "message": "No logs yet."})

    # Read last N lines efficiently
    all_lines = LOG_FILE.read_text().splitlines()
    last_lines = all_lines[-lines:]

    return JSONResponse(content={
        "lines":    len(last_lines),
        "logs":     last_lines,
    })

# ── FRIDAY Endpoints ──────────────────────────────────────────────────────────

@app.post("/watches", response_model=WatchResponse)
def post_add_watch(request: AddWatchRequest):
    """
    POST /watches
    Add a new filesystem watch.

    Body:
        {
            "folder": "~/Dev/Kairos",
            "pattern": "*.py",
            "event": "created",
            "task": "review the new python file at {filepath}",
            "cooldown_seconds": 30,
            "max_triggers_per_day": 20,
            "local_only": true
        }
    """
    try:
        watch = add_watch(
            folder=request.folder,
            task=request.task,
            event=request.event,
            pattern=request.pattern,
            watch_id=request.watch_id,
            cooldown_seconds=request.cooldown_seconds,
            max_triggers_per_day=request.max_triggers_per_day,
            local_only=request.local_only,
        )
        return WatchResponse(**watch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/watches")
def get_watches():
    """
    GET /watches
    List all active filesystem watches.
    """
    watches = list_watches()
    return {"watches": watches, "count": len(watches)}


@app.delete("/watches/{watch_id}")
def delete_watch(watch_id: str):
    """
    DELETE /watches/{watch_id}
    Remove a filesystem watch by ID.
    """
    removed = remove_watch(watch_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Watch '{watch_id}' not found.")
    return JSONResponse(content={"message": f"Watch '{watch_id}' removed."})


@app.get("/watches/logs")
def get_friday_logs(lines: int = 50):
    """
    GET /watches/logs?lines=50
    Returns the last N lines from the FRIDAY log file.
    """
    if not FRIDAY_LOG.exists():
        return JSONResponse(content={"logs": [], "message": "No logs yet."})

    all_lines  = FRIDAY_LOG.read_text().splitlines()
    last_lines = all_lines[-lines:]

    return JSONResponse(content={"lines": len(last_lines), "logs": last_lines})


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run the API server directly: python3 api.py
    # host="0.0.0.0" → accessible from other machines on your network
    # host="127.0.0.1" → localhost only (more secure for local dev)
    # reload=False → no auto-reload (we're not in dev mode inside the agent)
    uvicorn.run(
        "api:app",          # Module name : FastAPI instance name
        host="127.0.0.1",   # Localhost only — change to 0.0.0.0 to expose
        port=8000,
        reload=True,
    )