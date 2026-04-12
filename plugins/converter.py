"""
plugins/converter.py — Unit & Timezone Converter
Converts between common units and timezones.
No external libraries needed.

Actions:
    length      → meters, feet, miles, km, inches, cm
    weight      → kg, lbs, grams, ounces
    temperature → celsius, fahrenheit, kelvin
    timezone    → convert time between timezones
    currency    → basic currency rates (static — no API needed)
"""

from datetime import datetime
from zoneinfo import ZoneInfo

PLUGIN_NAME        = "converter"
PLUGIN_DESCRIPTION = "Convert units, temperatures, and timezones"
PLUGIN_ACTIONS     = ["length", "weight", "temperature", "timezone"]


def run(action: str, input: str) -> str:
    """
    Convert units.

    Input format: "value from_unit to_unit"
    Examples:
        length:      "100 meters feet"
        weight:      "75 kg lbs"
        temperature: "100 celsius fahrenheit"
        timezone:    "now IST UTC"
        timezone:    "14:30 EST IST"
    """
    if action == "length":
        return _convert_length(input)
    elif action == "weight":
        return _convert_weight(input)
    elif action == "temperature":
        return _convert_temperature(input)
    elif action == "timezone":
        return _convert_timezone(input)
    else:
        return f"Unknown action: {action}"


# ── Length ────────────────────────────────────────────────────────────────────

# All conversions to meters first
_LENGTH_TO_METERS = {
    "meter": 1, "meters": 1, "m": 1,
    "km": 1000, "kilometer": 1000, "kilometers": 1000,
    "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
    "mm": 0.001, "millimeter": 0.001,
    "mile": 1609.344, "miles": 1609.344,
    "foot": 0.3048, "feet": 0.3048, "ft": 0.3048,
    "inch": 0.0254, "inches": 0.0254, "in": 0.0254,
    "yard": 0.9144, "yards": 0.9144, "yd": 0.9144,
}

def _convert_length(input: str) -> str:
    try:
        parts = input.strip().lower().split()
        if len(parts) < 3:
            return "Format: '100 meters feet'"

        value    = float(parts[0])
        from_u   = parts[1]
        to_u     = parts[2]

        if from_u not in _LENGTH_TO_METERS:
            return f"Unknown unit: {from_u}"
        if to_u not in _LENGTH_TO_METERS:
            return f"Unknown unit: {to_u}"

        # Convert to meters then to target
        in_meters = value * _LENGTH_TO_METERS[from_u]
        result    = in_meters / _LENGTH_TO_METERS[to_u]

        return f"{value} {from_u} = {result:.4f} {to_u}"

    except ValueError:
        return "Invalid value. Format: '100 meters feet'"
    except Exception as e:
        return f"Conversion error: {e}"


# ── Weight ────────────────────────────────────────────────────────────────────

_WEIGHT_TO_KG = {
    "kg": 1, "kilogram": 1, "kilograms": 1,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "mg": 0.000001, "milligram": 0.000001,
    "lb": 0.453592, "lbs": 0.453592, "pound": 0.453592, "pounds": 0.453592,
    "oz": 0.0283495, "ounce": 0.0283495, "ounces": 0.0283495,
    "ton": 1000, "tons": 1000, "tonne": 1000,
}

def _convert_weight(input: str) -> str:
    try:
        parts = input.strip().lower().split()
        if len(parts) < 3:
            return "Format: '75 kg lbs'"

        value  = float(parts[0])
        from_u = parts[1]
        to_u   = parts[2]

        if from_u not in _WEIGHT_TO_KG:
            return f"Unknown unit: {from_u}"
        if to_u not in _WEIGHT_TO_KG:
            return f"Unknown unit: {to_u}"

        in_kg  = value * _WEIGHT_TO_KG[from_u]
        result = in_kg / _WEIGHT_TO_KG[to_u]

        return f"{value} {from_u} = {result:.4f} {to_u}"

    except ValueError:
        return "Invalid value. Format: '75 kg lbs'"
    except Exception as e:
        return f"Conversion error: {e}"


# ── Temperature ───────────────────────────────────────────────────────────────

def _convert_temperature(input: str) -> str:
    try:
        parts = input.strip().lower().split()
        if len(parts) < 3:
            return "Format: '100 celsius fahrenheit'"

        value  = float(parts[0])
        from_u = parts[1]
        to_u   = parts[2]

        # Convert to celsius first
        if from_u in ["c", "celsius"]:
            celsius = value
        elif from_u in ["f", "fahrenheit"]:
            celsius = (value - 32) * 5 / 9
        elif from_u in ["k", "kelvin"]:
            celsius = value - 273.15
        else:
            return f"Unknown unit: {from_u}. Use celsius, fahrenheit, kelvin"

        # Convert celsius to target
        if to_u in ["c", "celsius"]:
            result = celsius
        elif to_u in ["f", "fahrenheit"]:
            result = (celsius * 9 / 5) + 32
        elif to_u in ["k", "kelvin"]:
            result = celsius + 273.15
        else:
            return f"Unknown unit: {to_u}. Use celsius, fahrenheit, kelvin"

        return f"{value} {from_u} = {result:.2f} {to_u}"

    except ValueError:
        return "Invalid value. Format: '100 celsius fahrenheit'"
    except Exception as e:
        return f"Conversion error: {e}"


# ── Timezone ──────────────────────────────────────────────────────────────────

# Common timezone aliases
_TZ_ALIASES = {
    "IST":  "Asia/Kolkata",
    "UTC":  "UTC",
    "EST":  "America/New_York",
    "PST":  "America/Los_Angeles",
    "CST":  "America/Chicago",
    "MST":  "America/Denver",
    "GMT":  "Europe/London",
    "CET":  "Europe/Paris",
    "JST":  "Asia/Tokyo",
    "CST":  "Asia/Shanghai",
    "AEST": "Australia/Sydney",
}

def _convert_timezone(input: str) -> str:
    """
    Convert time between timezones.
    Input: "now IST UTC" or "14:30 EST IST"
    """
    try:
        parts = input.strip().upper().split()
        if len(parts) < 3:
            return "Format: 'now IST UTC' or '14:30 IST UTC'"

        time_str = parts[0]
        from_tz  = _TZ_ALIASES.get(parts[1], parts[1])
        to_tz    = _TZ_ALIASES.get(parts[2], parts[2])

        from_zone = ZoneInfo(from_tz)
        to_zone   = ZoneInfo(to_tz)

        if time_str == "NOW":
            # Use current time in source timezone
            now    = datetime.now(from_zone)
            result = now.astimezone(to_zone)
        else:
            # Parse HH:MM
            hour, minute = map(int, time_str.split(":"))
            now    = datetime.now(from_zone).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            result = now.astimezone(to_zone)

        from_str = now.strftime("%H:%M %Z")
        to_str   = result.strftime("%H:%M %Z")

        return f"{from_str} = {to_str}"

    except Exception as e:
        return f"Timezone error: {e}. Format: 'now IST UTC'"