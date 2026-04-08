"""
server.py — Kairos API Server
Standalone entry point for running just the REST API.
Used by systemd to run Kairos as a background service.

Does NOT start the terminal UI.
Does NOT require an active terminal session.
Runs forever until stopped by systemd.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="127.0.0.1",   # localhost only — change to 0.0.0.0 to expose on network
        port=8000,
        log_level="info",   # more verbose than main.py — logs go to systemd journal
        reload=False,
    )