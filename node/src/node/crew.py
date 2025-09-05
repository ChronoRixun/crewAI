from typing import List
from difflib import get_close_matches
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
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