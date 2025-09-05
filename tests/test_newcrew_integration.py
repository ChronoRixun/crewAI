"""Integration test for the example crew and custom tool."""

# mypy: ignore-errors

import sys
from pathlib import Path

# Ensure the example project and library are importable
root = Path(__file__).resolve().parents[1]
sys.path.append(str(root / "src"))
sys.path.append(str(root / "newcrew" / "src"))

from newcrew import Newcrew  # noqa: E402
from newcrew.tools import MyCustomTool  # noqa: E402


class DummyLLM:
    """Simple stand-in LLM that avoids external API calls."""

    stop: list[str] = []

    def call(self, *args, **kwargs) -> str:  # pragma: no cover - trivial
        return "dummy response"

    def supports_stop_words(self) -> bool:  # pragma: no cover - trivial
        return True


def test_newcrew_runs_with_custom_tool(tmp_path):
    """Crew should kick off and expose the custom tool."""

    crew_instance = Newcrew().crew()

    # Replace each agent's LLM with the dummy implementation to stay offline
    for agent in crew_instance.agents:
        agent.llm = DummyLLM()
        agent.function_calling_llm = DummyLLM()

    result = crew_instance.kickoff(inputs={"topic": "test", "current_year": "2024"})

    # Crew execution returns a CrewOutput with task outputs
    assert result is not None
    assert len(result.tasks_output) == len(crew_instance.tasks)

    # Ensure custom tool is registered on the researcher agent and works
    researcher = crew_instance.agents[0]
    assert any(isinstance(tool, MyCustomTool) for tool in researcher.tools)
    tool_output = researcher.tools[0].run(argument="data")
    assert "tool output" in tool_output
