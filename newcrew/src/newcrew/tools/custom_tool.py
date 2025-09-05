from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field


class MyCustomToolInput(BaseModel):
    """Input schema for MyCustomTool."""
    argument: str = Field(..., description="Description of the argument.")

class MyCustomTool(BaseTool):
    """Simple demonstration tool returning a static string."""

    name: str = "my_custom_tool"
    description: str = (
        "Example tool for the template project. It simply echoes a canned response"
        " when invoked so we can verify tool wiring without external calls."
    )
    args_schema: Type[BaseModel] = MyCustomToolInput

    def _run(self, argument: str) -> str:  # pragma: no cover - trivial example
        return "this is an example of a tool output, ignore it and move along."
