# main.py
import time
import threading
import requests
import uvicorn
from ui.terminal import run


def is_api_running() -> bool:
    """
    Check if the Kairos API is already running on port 8765.
    Returns True if it's up, False if not.
    """
    try:
        response = requests.get("http://127.0.0.1:8765/status", timeout=2)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


def start_api():
    """Start the FastAPI server in a background thread."""
    uvicorn.run(
        "api:app",
        host="127.0.0.1",
        port=8765,
        log_level="warning",
        reload=False,
    )


if __name__ == "__main__":
    if is_api_running():
        # systemd already started the API — don't start another one
        print("  ⚡ Kairos API already running — connecting...")
    else:
        # No API running — start one in background thread
        api_thread = threading.Thread(target=start_api, daemon=True)
        api_thread.start()
        time.sleep(1)

    # Always start the terminal UI
    run()