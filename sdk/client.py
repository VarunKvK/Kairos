"""
sdk/client.py — Kairos Python SDK
Wraps the Kairos REST API into a clean Python interface.

Usage:
    from sdk import Kairos

    k = Kairos()                          # connects to localhost:8000
    k = Kairos(base_url="http://x.x.x.x:8000")  # remote instance

Methods:
    k.chat(message, use_planner=True)  → str
    k.plan(message)                    → str
    k.status()                         → dict
    k.get_history()                    → list
    k.clear_history()                  → bool
"""

import requests


class KairosError(Exception):
    """
    Raised when the Kairos API returns an error response.
    Wraps the HTTP status code and detail message together
    so callers get useful information in one exception.
    """
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail      = detail
        # e.g. "KairosError 500: All providers failed."
        super().__init__(f"KairosError {status_code}: {detail}")


class Kairos:
    """
    Python client for the Kairos REST API.

    All methods are synchronous — they block until the API responds.
    This matches how Kairos works internally (one task at a time).

    Args:
        base_url: The URL where the Kairos API is running.
                  Defaults to localhost on port 8000.
        timeout:  How many seconds to wait for a response before giving up.
                  Kairos can be slow on complex tasks — default is 120s.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout:  int = 120,
    ):
        # Strip trailing slash so url joins always work cleanly
        # e.g. "http://localhost:8000/" → "http://localhost:8000"
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

        # Reuse one session for all requests — faster than creating
        # a new connection every time (TCP connection reuse)
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ── Private Helpers ───────────────────────────────────────────────────

    def _post(self, endpoint: str, body: dict) -> dict:
        """
        Internal POST helper.
        Sends JSON body to the given endpoint.
        Raises KairosError on any non-2xx response.
        Raises ConnectionError if the API server isn't running.
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.post(url, json=body, timeout=self.timeout)
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot reach Kairos API at {self.base_url}. "
                "Is the server running? → python3 api.py"
            )

        # If the API returned an error, raise it with the detail message
        if not response.ok:
            detail = response.json().get("detail", response.text)
            raise KairosError(response.status_code, detail)

        return response.json()

    def _get(self, endpoint: str) -> dict:
        """
        Internal GET helper.
        Same pattern as _post but for read-only endpoints.
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot reach Kairos API at {self.base_url}. "
                "Is the server running? → python3 api.py"
            )

        if not response.ok:
            detail = response.json().get("detail", response.text)
            raise KairosError(response.status_code, detail)

        return response.json()

    def _delete(self, endpoint: str) -> dict:
        """
        Internal DELETE helper.
        Same pattern — used only for clearing history.
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.delete(url, timeout=self.timeout)
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot reach Kairos API at {self.base_url}. "
                "Is the server running? → python3 api.py"
            )

        if not response.ok:
            detail = response.json().get("detail", response.text)
            raise KairosError(response.status_code, detail)

        return response.json()

    # ── Public Methods ────────────────────────────────────────────────────

    def chat(self, message: str, use_planner: bool = True) -> str:
        """
        Send a message to Kairos and get a response.

        Args:
            message:     The task or question for Kairos.
            use_planner: If True, routes through the planner (default).
                         Set to False to skip planning for simple tasks.

        Returns:
            Kairos's answer as a plain string.

        Example:
            answer = k.chat("what files are in my home folder?")
            print(answer)
        """
        data = self._post("/chat", {
            "message":     message,
            "use_planner": use_planner,
        })
        # The API returns {"answer": "...", "history_length": N, "provider": "..."}
        # We return just the answer string — simplest possible interface
        return data["answer"]

    def plan(self, message: str) -> str:
        """
        Send a task directly to the planner.
        Always routes through run_planner() regardless of complexity.

        Args:
            message: The complex task to plan and execute.

        Returns:
            Kairos's final summary as a plain string.

        Example:
            result = k.plan("research Python async patterns and write a summary")
            print(result)
        """
        data = self._post("/plan", {"message": message})
        return data["answer"]

    def status(self) -> dict:
        """
        Check if the Kairos API is online.

        Returns a dict with:
            status          → "online"
            agent           → "Kairos"
            provider        → active LLM provider
            uptime_seconds  → seconds since server started
            history_length  → current number of messages in history

        Example:
            info = k.status()
            print(info["provider"])   # "groq"
            print(info["uptime_seconds"])
        """
        return self._get("/status")

    def get_history(self) -> list:
        """
        Get the full conversation history from the API.

        Returns a list of message dicts:
            [
                {"role": "user",      "content": "..."},
                {"role": "assistant", "content": "..."},
            ]

        Example:
            history = k.get_history()
            for msg in history:
                print(f"{msg['role']}: {msg['content'][:80]}")
        """
        data = self._get("/history")
        # API returns {"history": [...], "length": N}
        # We return just the list
        return data["history"]

    def clear_history(self) -> bool:
        """
        Clear the conversation history on the API server.
        Kairos will start fresh on the next chat() call.

        Returns:
            True if cleared successfully.

        Example:
            k.clear_history()
        """
        self._delete("/history")
        return True

    # ── Convenience ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        """Shows useful info when you print the client object."""
        return f"Kairos(base_url='{self.base_url}', timeout={self.timeout}s)"