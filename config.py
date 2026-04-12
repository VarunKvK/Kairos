# config.py
# Central configuration for Kairos.
# All settings live here — API keys, LLM choice, and defaults.

import os
from dotenv import load_dotenv

load_dotenv()

config = {

    # ─── LLM SETTINGS ─────────────────────────────────────────
    # Set "provider" to switch between LLMs.
    # Options: "groq", "gemini", "mistral"
    "provider": "groq",
    # "provider": "gemma",


    # ─── API KEYS ─────────────────────────────────────────────
    "groq_api_key": os.getenv("GROK_API_KEY"),
    "gemini_api_key": os.getenv("GEMINI_API_KEY"),

    # ─── MODEL NAMES ──────────────────────────────────────────
    # The specific model to use per provider.
    "models": {
        "groq":"llama-3.3-70b-versatile",  # Fast & capable, free on Groq
        "gemini":  "gemini-2.5-flash",
        "gemini15": "gemini-flash-latest",          # Fast & free on Gemini
        "mistral": "mistral:latest",            # Local fallback via Ollama
        "gemma": "phi4-mini",            # Local fallback via Ollama
    },

    # ─── AGENT SETTINGS ───────────────────────────────────────
    "agent_name": "Kairos",
    "max_iterations": 6,  # Max steps Kairos takes before stopping

    "api_port": 8765,
    "api_host": "127.0.0.1",
}