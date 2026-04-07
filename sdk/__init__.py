"""
sdk/__init__.py
Exposes the Kairos client at the package level.

Usage:
    from sdk import Kairos
    from sdk import KairosError   ← catch API errors specifically
"""

from sdk.client import Kairos, KairosError

__all__ = ["Kairos", "KairosError"]
__version__ = "1.0.0"