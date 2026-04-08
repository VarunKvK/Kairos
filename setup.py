"""
setup.py — Makes Kairos SDK installable as a package.
After running: pip install -e .
You can use: from sdk import Kairos
from anywhere on this machine.
"""

from setuptools import setup, find_packages

setup(
    name="kairos-sdk",
    version="1.0.0",
    description="Python SDK for the Kairos AI Agent",
    author="Varun Krishnan",
    packages=find_packages(),
    install_requires=[
        "requests",
    ],
    python_requires=">=3.12",
)