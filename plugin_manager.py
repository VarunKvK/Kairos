"""
plugin_manager.py — Kairos Plugin System
Automatically loads plugins from the plugins/ folder.

Each plugin is a .py file that defines:
    PLUGIN_NAME        → tool name the agent uses
    PLUGIN_DESCRIPTION → what the tool does (injected into system prompt)
    PLUGIN_ACTIONS     → list of valid actions
    run(action, input) → executes the plugin

The plugin manager:
    1. Scans plugins/ folder on startup
    2. Imports each valid plugin
    3. Registers it with the agent
    4. Injects its description into the system prompt

Adding a new tool to Kairos:
    1. Drop a .py file into plugins/
    2. Restart Kairos
    Done.
"""

import importlib.util
import traceback
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

PLUGINS_DIR = Path(__file__).parent / "plugins"

# ── Registry ──────────────────────────────────────────────────────────────────

# Stores all loaded plugins
# { plugin_name: module }
_registry: dict = {}

# ── Loader ────────────────────────────────────────────────────────────────────
def load_plugins() -> list[str]:
    """
    Scan plugins/ folder and load all valid plugins.
    Called once at startup.

    A valid plugin must have:
        PLUGIN_NAME        (str)
        PLUGIN_DESCRIPTION (str)
        PLUGIN_ACTIONS     (list)
        run()              (callable)

    Returns list of successfully loaded plugin names.
    """
    loaded = []

    if not PLUGINS_DIR.exists():
        PLUGINS_DIR.mkdir(exist_ok=True)
        return []

    for plugin_file in sorted(PLUGINS_DIR.glob("*.py")):
        # Skip __init__.py and private files
        if plugin_file.name.startswith("_"):
            continue

        try:
            # Load the module from file path
            spec   = importlib.util.spec_from_file_location(
                plugin_file.stem,
                plugin_file,
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Validate required attributes
            required = ["PLUGIN_NAME", "PLUGIN_DESCRIPTION", "PLUGIN_ACTIONS", "run"]
            missing  = [r for r in required if not hasattr(module, r)]

            if missing:
                print(f"  [plugins] Skipping {plugin_file.name} — missing: {missing}")
                continue

            # Register the plugin
            name = module.PLUGIN_NAME
            _registry[name] = module
            loaded.append(name)
            print(f"  [plugins] Loaded: {name} ({plugin_file.name})")

        except Exception as e:
            print(f"  [plugins] Failed to load {plugin_file.name}: {e}")
            traceback.print_exc()

    return loaded

def get_plugin(name: str):
    """Get a loaded plugin by name. Returns None if not found."""
    return _registry.get(name)


def list_plugins() -> list[dict]:
    """
    Return info about all loaded plugins.
    Used by /plugins command in terminal UI.
    """
    result = []
    for name, module in _registry.items():
        result.append({
            "name":        name,
            "description": module.PLUGIN_DESCRIPTION,
            "actions":     module.PLUGIN_ACTIONS,
        })
    return result


def run_plugin(name: str, action: str, input: str) -> str:
    """
    Execute a plugin by name.

    Args:
        name:   plugin name (e.g. "weather")
        action: action to perform (e.g. "current")
        input:  input string for the plugin

    Returns:
        Plugin output as string.
        Error message if plugin not found or fails.
    """
    plugin = get_plugin(name)

    if not plugin:
        available = ", ".join(_registry.keys()) or "none"
        return f"Plugin '{name}' not found. Available: {available}"

    if action not in plugin.PLUGIN_ACTIONS:
        return (
            f"Invalid action '{action}' for plugin '{name}'. "
            f"Valid actions: {', '.join(plugin.PLUGIN_ACTIONS)}"
        )

    try:
        return plugin.run(action, input)
    except Exception as e:
        return f"Plugin '{name}' failed: {e}"


def get_plugin_prompt_section() -> str:
    """
    Build the system prompt section describing all loaded plugins.
    Injected into agent system prompt so LLM knows about plugins.

    Returns empty string if no plugins loaded.
    """
    if not _registry:
        return ""

    lines = ["5. plugin → Run a loaded plugin tool"]
    lines.append("   Available plugins:")

    for name, module in _registry.items():
        actions = ", ".join(module.PLUGIN_ACTIONS)
        lines.append(f"   - {name}: {module.PLUGIN_DESCRIPTION}")
        lines.append(f"     actions: {actions}")

    lines.append(
        '\n   Example: tool "plugin", action "weather", input "current|London"'
    )

    return "\n".join(lines)