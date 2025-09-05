# src/node/tools/custom_tools.py
from typing import Callable, Dict

# import tool classes from the singular file in the same package
from .custom_tool import (
    NodeCodeAnalyzer,
    DependencyAnalyzer,
    WatchdogServiceAnalyzer,
    SecurityScanner,
    TestGenerator,
    NodeVersionMigrator,
)

# optional extras
try:
    from .esm_migration_tool import ESMMigrationTool
except Exception:
    from crewai.tools import BaseTool
    class ESMMigrationTool(BaseTool):
        name: str = "ESM Migration Tool"
        description: str = "Placeholder tool: real implementation unavailable"
        def _run(self, *args, **kwargs):  # type: ignore[override]
            return {"error": "ESM Migration Tool not installed"}

try:
    from .native_module_migrator import NativeModuleMigrator
except Exception:
    from crewai.tools import BaseTool
    class NativeModuleMigrator(BaseTool):
        name: str = "Native Module Migrator"
        description: str = "Placeholder tool: real implementation unavailable"
        def _run(self, *args, **kwargs):  # type: ignore[override]
            return {"error": "Native Module Migrator not installed"}


def _ctor(cls):
    return lambda: cls()

tool_functions: Dict[str, Callable[[], object]] = {
    "Node Code Analyzer": _ctor(NodeCodeAnalyzer),
    "Dependency Analyzer": _ctor(DependencyAnalyzer),
    "Watchdog Service Analyzer": _ctor(WatchdogServiceAnalyzer),
    "Security Scanner": _ctor(SecurityScanner),
    "Test Generator": _ctor(TestGenerator),
    "Node Version Migrator": _ctor(NodeVersionMigrator),
}
if ESMMigrationTool is not None:
    tool_functions["ESM Migration Tool"] = _ctor(ESMMigrationTool)
if NativeModuleMigrator is not None:
    tool_functions["Native Module Migrator"] = _ctor(NativeModuleMigrator)

def get_tool_functions() -> Dict[str, Callable[[], object]]:
    return tool_functions

# --- place this below your existing tool_functions dict ---

import unicodedata
from difflib import get_close_matches

def _normalize(name: str) -> str:
    # Normalize Unicode, collapse all whitespace to single spaces, trim ends
    if not isinstance(name, str):
        return ""
    name = unicodedata.normalize("NFKC", name)
    name = "".join(ch if not ch.isspace() else " " for ch in name)
    return name.strip()

# Build a normalized index once from your canonical keys
_normalized_index = { _normalize(k): k for k in tool_functions.keys() }

class _ToolMap(dict):
    # Tolerant lookup so CrewAI's tool_functions[tool] survives stray spaces/NBSP
    def __getitem__(self, key):
        # exact match first
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        # normalized fallback
        nkey = _normalize(key)
        ref = _normalized_index.get(nkey)
        if ref is not None:
            return dict.__getitem__(self, ref)
        # suggest a close match for fast fixes
        suggestion = get_close_matches(nkey, list(_normalized_index.keys()), n=1, cutoff=0.6)
        if suggestion:
            ref2 = _normalized_index[suggestion[0]]
            raise KeyError(f"{key!r} (closest: {ref2!r})")
        raise KeyError(key)

def get_tool_functions():
    # Debug so we KNOW the tolerant map is in use
    print("[DEBUG] tool registry module:", __file__)
    print("[DEBUG] tool registry keys:", list(tool_functions.keys()))
    return _ToolMap(tool_functions)

