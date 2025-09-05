import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "newcrew" / "src"))

from newcrew.crew import Newcrew
from newcrew.tools.custom_tool import MyCustomTool
from crewai import Task
from crewai.tasks.task_output import TaskOutput


def test_newcrew_runs_with_custom_tool(monkeypatch):
    crew = Newcrew().crew()
    researcher = crew.agents[0]
    assert any(isinstance(t, MyCustomTool) for t in researcher.tools)

    def fake_execute(self, *args, **kwargs):
        if self.agent and getattr(self.agent, "tools", None):
            result = self.agent.tools[0].run(argument="test")
        else:
            result = "no tools"
        return TaskOutput(description="done", raw=result, agent=self.agent.role)

    monkeypatch.setattr(Task, "execute_sync", fake_execute)
    output = crew.kickoff()
    assert (
        output.tasks_output[0].raw
        == "this is an example of a tool output, ignore it and move along."
    )
