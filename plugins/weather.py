"""
plugins/weather.py — Weather Information
Gets current weather using wttr.in (no API key needed).
wttr.in is a free weather service that returns plain text.
"""

import requests

PLUGIN_NAME        = "weather"
PLUGIN_DESCRIPTION = "Get current weather for any city — no API key needed"
PLUGIN_ACTIONS     = ["current", "forecast"]


def run(action: str, input: str) -> str:
    """
    Get weather information.

    Actions:
        current  → current weather for a city
        forecast → 3 day forecast for a city

    Input: city name e.g. "London", "New York", "Chennai"
    """
    city = input.strip()

    if not city:
        return "Please provide a city name."

    if action == "current":
        return _get_current(city)
    elif action == "forecast":
        return _get_forecast(city)
    else:
        return f"Unknown action: {action}"


def _get_current(city: str) -> str:
    """Get current weather using wttr.in"""
    try:
        # format=3 gives: City: ⛅ +28°C
        url      = f"https://wttr.in/{city}?format=3"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return f"Weather — {response.text.strip()}"
        else:
            return f"Could not get weather for '{city}'."

    except requests.exceptions.ConnectionError:
        return "No internet connection."
    except Exception as e:
        return f"Weather error: {e}"


def _get_forecast(city: str) -> str:
    """Get 3-day forecast using wttr.in"""
    try:
        # format=v2 gives a nice text forecast
        url      = f"https://wttr.in/{city}?format=v2"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            # Truncate to keep it manageable
            return response.text.strip()[:1000]
        else:
            return f"Could not get forecast for '{city}'."

    except requests.exceptions.ConnectionError:
        return "No internet connection."
    except Exception as e:
        return f"Forecast error: {e}"   