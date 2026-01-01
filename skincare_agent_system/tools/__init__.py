"""
Base Tool Interface and Registry.
Agents use tools to perform specific tasks; they don't implement the logic directly.
This separation enables:
1. Reusability: Multiple agents can use the same tool.
2. Testability: Tools can be unit-tested in isolation.
3. Autonomy: Agents decide WHICH tool to use based on their goal.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Standardized result from any tool."""

    success: bool
    data: Any = None
    error: Optional[str] = None


class BaseTool(ABC):
    """Abstract base class for all tools."""

    name: str = "BaseTool"
    description: str = "Base tool interface"

    @abstractmethod
    def run(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass


class ToolRegistry:
    """
    Registry of available tools.
    Agents query this to find tools that match their goal.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Register a tool by name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all available tool names."""
        return list(self._tools.keys())

    def find_by_goal(self, goal: str) -> List[BaseTool]:
        """
        Find tools relevant to a goal.
        This is a simple keyword match; a real system might use embeddings.
        """
        matches = []
        goal_lower = goal.lower()
        for tool in self._tools.values():
            if any(
                keyword in goal_lower for keyword in tool.description.lower().split()
            ):
                matches.append(tool)
        return matches
