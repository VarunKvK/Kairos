# main.py
# Entry point for Kairos.
# Starts the REST API in a background thread, then launches the terminal UI.
# Exiting the terminal UI stops everything cleanly.

import time
import threading
import uvicorn
from ui.terminal import run

def start_api():
    """
    Start the FastAPI server in a background thread.
    log_level="warning" silences per-request logs so they
    don't clutter the terminal UI output.
    """
    uvicorn.run(
        'api:app',
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        reload=False,
    )


if __name__ == "__main__":
    # Start API as a daemon thread
    # daemon=True means it dies automatically when main.py exits
    # so you never have orphan processes left behind
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    # Give uvicorn 1 second to bind to the port
    # before the terminal UI loads
    time.sleep(1)

    # Launch the terminal UI — this blocks until the user exits
    run()