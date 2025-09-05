from typing import List
from difflib import get_close_matches
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, tool
from crewai.agents.agent_builder.base_agent import BaseAgent
from node.tools import custom_tools as ct

# IMPORTANT: use package import (requires src/node/tools/__init__.py to exist)

@CrewBase
class Node:
    """Node crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    def toolset(self):
        # Print where we loaded the registry from + its keys
        print("[DEBUG] using custom_tools from:", ct.__file__)
        return ct.get_tool_functions()

    @property
    def tool_functions(self):
        # Back-compat for older CrewAI code-paths
        return self.toolset()

    # ---- CrewAI tool registration ----

    @tool
    def node_code_analyzer(self):
        """Run static analysis on Node.js source"""
        return self.toolset()["Node Code Analyzer"]()

    @tool
    def dependency_analyzer(self):
        """Inspect npm dependencies for issues"""
        return self.toolset()["Dependency Analyzer"]()

    @tool
    def watchdog_service_analyzer(self):
        """Profile the watchdog service"""
        return self.toolset()["Watchdog Service Analyzer"]()

    @tool
    def security_scanner(self):
        """Scan for security vulnerabilities"""
        return self.toolset()["Security Scanner"]()

    @tool
    def test_generator(self):
        """Generate unit tests"""
        return self.toolset()["Test Generator"]()

    @tool
    def node_version_migrator(self):
        """Assist in upgrading Node.js versions"""
        return self.toolset()["Node Version Migrator"]()

    @tool
    def esm_migration_tool(self):
        """Convert CommonJS modules to ESM"""
        return self.toolset()["ESM Migration Tool"]()

    @tool
    def native_module_migrator(self):
        """Handle migration of native modules"""
        return self.toolset()["Native Module Migrator"]()

    # ---- optional: validate agent tool names early (very helpful) ----
    def _validate_agent_tools(self):
        reg = self.toolset()
        reg_keys = set(reg.keys())
        missing = {}
        for agent_name, cfg in self.agents_config.items():
            for t in cfg.get("tools", []) or []:
                if t not in reg_keys:
                    # try to suggest a close match
                    suggestion = get_close_matches(t, list(reg_keys), n=1, cutoff=0.6)
                    missing.setdefault(agent_name, []).append((t, suggestion[0] if suggestion else None))
        if missing:
            print("\n[VALIDATION] The following agent tools are not registered:")
            for agent, entries in missing.items():
                for (bad, sug) in entries:
                    if sug:
                        print(f"  - {agent}: {bad!r}  (did you mean {sug!r}?)")
                    else:
                        print(f"  - {agent}: {bad!r}  (no close match)")
            # Raise a clean error before CrewAI deep-inits agents
            raise RuntimeError("Unregistered tools found in agents.yaml (see [VALIDATION] above)")

    @agent
    def researcher(self) -> Agent:
        self._validate_agent_tools()  # run once before agents are created
        return Agent(config=self.agents_config['researcher'], verbose=True)

    @agent
    def reporting_analyst(self) -> Agent:
        return Agent(config=self.agents_config['reporting_analyst'], verbose=True)

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config['research_task'])

    @task
    def reporting_task(self) -> Task:
        return Task(config=self.tasks_config['reporting_task'], output_file='report.md')

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)