# llm.py
# Handles all communication with the LLM providers.
# Kairos talks to Groq, Gemini, or Mistral through this file.

import ollama
import requests
from config import config
from rich.console import Console

import threading
import time

console = Console()

# ─── FALLBACK ORDER ────────────────────────────────────────────────────────
# Kairos will try each provider in this order if the previous one fails.
FALLBACK_ORDER = ["groq","gemini","gemma","mistral"]




def chat(messages: list) -> str:
    """
    Send a list of messages to the configured LLM provider.
    Returns the assistant's response as a string.

    'messages' follows the standard format:
    [
        { "role": "system",    "content": "You are Kairos..." },
        { "role": "user",      "content": "What is Python?"  },
        { "role": "assistant", "content": "Python is..."     },
    ]
    """

    primary = config["provider"]
    providers = [primary] + [p for p in FALLBACK_ORDER if p != primary]
    last_error = None

    for provider in providers:
        try:
            if provider == "groq":
                response = _chat_groq(messages)
            elif provider == "gemini":
                response = _chat_gemini(messages)
            elif provider == "gemma":
                response = _chat_gemma(messages)                
            elif provider == "mistral":
                response = _chat_mistral(messages)
            else:
                continue
            # If we're not using the primary, let the user know
            if provider != primary:
                console.print(f"[yellow]⚠ Switched to {provider} (fallback)[/yellow]")

            return response
        except Exception as e:
            last_error = e
            console.print(f"[red]✗ {provider} failed: {e}[/red]")
            console.print(f"[yellow]→ Trying next provider...[/yellow]")
            time.sleep(1)  # Small delay before trying next provider

    # If all providers fail, raise the last error
    raise RuntimeError(f"All providers failed. Last error: {last_error}")



# ─── GROQ ──────────────────────────────────────────────────────────────────

def _chat_groq(messages: list) -> str:
    """Send messages to Groq API and return the response."""

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['groq_api_key']}",
        "Content-Type":  "application/json",
    }

    trimmed_messages = [messages[0]] + messages[-4:] if len(messages) > 5 else messages
    body = {
        "model":    config["models"]["groq"],
        "messages": trimmed_messages,
    }

    session = requests.Session()
    response = session.post(url, headers = headers, json = body)
    response.raise_for_status() # Raises an error if the request failed

    return response.json()["choices"][0]["message"]["content"]

# ─── GEMINI ────────────────────────────────────────────────────────────────

def _chat_gemini(messages: list) -> str:
    """Send messages to Gemini API and return the response."""

    api_key = config["gemini_api_key"]
    model = config["models"]["gemini"]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    # Gemini uses a different message format than Groq/Mistral.
    # We convert the standard format to Gemini's format here.
    # Gemini uses a different message format — convert standard format to Gemini's
    trimmed = [messages[0]] + messages[-4:] if len(messages) > 5 else messages
    gemini_messages = []

    for msg in trimmed:
        if msg["role"] == "system":
            gemini_messages.append({
                "role":  "user",
                "parts": [{ "text": f"[System]: {msg['content']}" }]
            })
        elif msg["role"] == "user":
            gemini_messages.append({
                "role":  "user",
                "parts": [{ "text": msg["content"] }]
            })
        elif msg["role"] == "assistant":
            gemini_messages.append({
                "role":  "model",
                "parts": [{ "text": msg["content"] }]
            })

    body = {"contents" : gemini_messages}

    session = requests.Session()
    response = session.post(url , json = body)
    response.raise_for_status()

    return response.json()["candidates"][0]["content"]["parts"][0]["text"]

# ─── MISTRAL (OLLAMA) ──────────────────────────────────────────────────────

def _chat_mistral(messages: list, timeout: int =180) -> str:
    """
    Send messages to local Mistral via Ollama.
    Runs in a thread with a timeout so it never hangs forever.
    If it takes longer than `timeout` seconds, raises a RuntimeError.
    """
    result = {}     # Shared dict — the thread writes here, we read after
    error  = {}     # If the thread errors, it writes here
    
    def target():
        try:
            response = ollama.chat(
                model    = config["models"]["mistral"],
                messages = messages,
            )
            result["content"]= response["message"]["content"]
        except Exception as e:
            error["value"] = e

    # Run ollama.chat() in a background thread
    thread = threading.Thread(target = target, daemon=True)
    thread.start()

    # Wait up to `timeout` seconds for it to finish
    thread.join(timeout=timeout)

    if thread.is_alive():
        # Thread is still running after timeout — give up
        raise RuntimeError(f"Mistral timed out after {timeout} seconds.")

    if "value" in error:
        # Thread finished but threw an error
        raise error["value"]

    return result["content"]

# ─── GEMMA (OLLAMA) ────────────────────────────────────────────────────────

def _chat_gemma(messages: list, timeout: int = 180) -> str:
    """
    Send messages to local Gemma 4 via Ollama.
    Same thread+timeout pattern as Mistral — never hangs.
    Gemma is faster than Mistral for most tasks.
    """

    result = {}
    error  = {}

    def target():
        try:
            response = ollama.chat(
                model    = config["models"]["gemma"],
                messages = messages,
            )
            result["content"] = response["message"]["content"]
        except Exception as e:
            error["value"] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        raise RuntimeError(f"Gemma timed out after {timeout} seconds.")

    if "value" in error:
        raise error["value"]

    return result["content"]