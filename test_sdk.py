"""
test_sdk.py
Quick test of every SDK method.
Run with: python3 test_sdk.py
Make sure api.py is running first.
"""

from sdk import Kairos, KairosError

def run_tests():
    k = Kairos()
    print(f"Connected: {k}\n")

    # ── Test 1: Status ────────────────────────────────────
    print("── Test 1: Status ──")
    info = k.status()
    print(f"  Status:   {info['status']}")
    print(f"  Provider: {info['provider']}")
    print(f"  Uptime:   {info['uptime_seconds']}s\n")

    # ── Test 2: Simple chat (no planner) ──────────────────
    print("── Test 2: Chat (no planner) ──")
    answer = k.chat("say exactly: Kairos online.", use_planner=False)
    print(f"  Answer: {answer}\n")

    # ── Test 3: Check history grew ────────────────────────
    print("── Test 3: History ──")
    history = k.get_history()
    print(f"  Messages in history: {len(history)}")
    for msg in history:
        print(f"  [{msg['role']}]: {msg['content'][:60]}")\

    # ── Test 4: Clear history ─────────────────────────────
    print("\n── Test 4: Clear History ──")
    cleared = k.clear_history()
    print(f"  Cleared: {cleared}")
    print(f"  History now: {len(k.get_history())} messages\n")

    # ── Test 5: Error handling ────────────────────────────
    print("── Test 5: Error Handling ──")
    try:
        k2 = Kairos(base_url="http://127.0.0.1:9999")  # wrong port
        k2.status()
    except ConnectionError as e:
        print(f"  Caught expected error: {e}\n")

    print("── All tests passed ──")

if __name__ == "__main__":
    run_tests()