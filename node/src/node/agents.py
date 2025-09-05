# agents.py
from crewai import Agent
from crewai.project import CrewBase
from pathlib import Path
import yaml

# Import your existing tools
from tools.custom_tools import (
    NodeCodeAnalyzer,
    DependencyAnalyzer,
    WatchdogServiceAnalyzer,
    SecurityScanner,
    TestGenerator,
    NodeVersionMigrator,
)
from tools.esm_migration_tool import ESMMigrationTool
from tools.native_module_migrator import NativeModuleMigrator

def _load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

from tools.custom_tools import get_tool_functions

# Do NOT create instances here. Expose the callable registry to CrewAI:
TOOL_FUNCTIONS = get_tool_functions()

@CrewBase
class Node:
    """Shim that exposes Agents defined in config/agents.yaml"""
    agents_config = _load_yaml(str(Path("config/agents.yaml")))

    # helper to build Agent from a yaml block
    def _build(self, key: str) -> Agent:
        cfg = self.agents_config[key]
        tool_objs = [TOOL_REGISTRY[name] for name in cfg.get("tools", [])]
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg.get("backstory", ""),
            tools=tool_objs,
            verbose=cfg.get("verbose", False),
            allow_delegation=cfg.get("allow_delegation", False),
        )

    # One method per agent key (names must match what your crew/tasks expect)
    def code_analyst(self) -> Agent:              return self._build("code_analyst")
    def modernization_specialist(self) -> Agent:  return self._build("modernization_specialist")
    def dependency_manager(self) -> Agent:        return self._build("dependency_manager")
    def testing_engineer(self) -> Agent:          return self._build("testing_engineer")
    def security_auditor(self) -> Agent:          return self._build("security_auditor")
    def build_config_specialist(self) -> Agent:   return self._build("build_config_specialist")
    def performance_optimizer(self) -> Agent:     return self._build("performance_optimizer")