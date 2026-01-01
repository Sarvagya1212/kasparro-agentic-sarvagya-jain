"""
Base Tool Interface, Registry, and Role-Based Access.
Implements tooling best practices:
1. Role-based tool availability
2. Simplified definitions with self-documenting names
3. Graceful error handling with descriptive messages
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel

logger = logging.getLogger("Tools")


class ToolResult(BaseModel):
    """Standardized result from any tool."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # For categorization
    recoverable: bool = True  # Can agent retry?


class AgentRole(Enum):
    """Agent roles for tool access control."""
    COORDINATOR = "coordinator"
    DELEGATOR = "delegator"
    BENEFITS_WORKER = "benefits_worker"
    USAGE_WORKER = "usage_worker"
    FAQ_WORKER = "faq_worker"
    COMPARISON_WORKER = "comparison_worker"
    VALIDATION_WORKER = "validation_worker"
    GENERATION_AGENT = "generation_agent"
    VERIFIER = "verifier"
    DATA_AGENT = "data_agent"


# Role to allowed tools mapping (Limit Tool Availability)
ROLE_TOOL_ACCESS: Dict[AgentRole, Set[str]] = {
    AgentRole.BENEFITS_WORKER: {"benefits_extractor"},
    AgentRole.USAGE_WORKER: {"usage_extractor"},
    AgentRole.FAQ_WORKER: {"faq_generator"},
    AgentRole.COMPARISON_WORKER: {"product_comparison"},
    AgentRole.DELEGATOR: {"benefits_extractor", "usage_extractor", "faq_generator", "product_comparison"},
    AgentRole.GENERATION_AGENT: set(),  # No tools, uses templates
    AgentRole.VERIFIER: set(),  # No tools, verification logic
    AgentRole.DATA_AGENT: set(),  # No tools, data loading
    AgentRole.COORDINATOR: set(),  # Orchestration only
    AgentRole.VALIDATION_WORKER: set(),  # Validation logic only
}


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    Implements graceful error handling.
    """

    name: str = "BaseTool"
    description: str = "Base tool interface"

    @abstractmethod
    def _execute(self, **kwargs) -> Any:
        """Internal execution logic. Override in subclasses."""
        pass

    def run(self, **kwargs) -> ToolResult:
        """
        Execute the tool with graceful error handling.
        Returns descriptive errors for self-correction.
        """
        try:
            result = self._execute(**kwargs)
            return ToolResult(success=True, data=result)
        except ValueError as e:
            # Validation/input errors - recoverable
            logger.warning(f"Tool {self.name} validation error: {e}")
            return ToolResult(
                success=False,
                error=f"Invalid input: {str(e)}. Check your parameters.",
                error_type="validation_error",
                recoverable=True
            )
        except KeyError as e:
            # Missing data - recoverable with different input
            logger.warning(f"Tool {self.name} missing key: {e}")
            return ToolResult(
                success=False,
                error=f"Missing required field: {str(e)}. Ensure all required data is provided.",
                error_type="missing_data",
                recoverable=True
            )
        except TypeError as e:
            # Type mismatch - check input format
            logger.warning(f"Tool {self.name} type error: {e}")
            return ToolResult(
                success=False,
                error=f"Type mismatch: {str(e)}. Check input data types.",
                error_type="type_error",
                recoverable=True
            )
        except Exception as e:
            # Unexpected error - may not be recoverable
            logger.error(f"Tool {self.name} unexpected error: {e}")
            return ToolResult(
                success=False,
                error=f"Unexpected error in {self.name}: {str(e)}. This may require investigation.",
                error_type="unexpected_error",
                recoverable=False
            )


class ToolRegistry:
    """
    Registry with role-based access control.
    Limits tool availability per agent role.
    """

    def __init__(self, role: Optional[AgentRole] = None):
        """
        Initialize registry with optional role restriction.

        Args:
            role: If set, only tools allowed for this role are accessible
        """
        self._tools: Dict[str, BaseTool] = {}
        self._role = role
        self._access_log: List[Dict[str, Any]] = []

    def register(self, tool: BaseTool):
        """Register a tool by name."""
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name with access control.
        Returns None if tool doesn't exist or access is denied.
        """
        tool = self._tools.get(name)
        if not tool:
            logger.warning(f"Tool not found: {name}")
            return None

        # Check role-based access
        if self._role:
            allowed = ROLE_TOOL_ACCESS.get(self._role, set())
            if name not in allowed:
                logger.warning(
                    f"Access denied: Role {self._role.value} cannot use tool {name}"
                )
                self._access_log.append({
                    "tool": name,
                    "role": self._role.value,
                    "access": "denied"
                })
                return None

            self._access_log.append({
                "tool": name,
                "role": self._role.value,
                "access": "granted"
            })

        return tool

    def list_tools(self) -> List[str]:
        """List available tool names (respecting role)."""
        if self._role:
            allowed = ROLE_TOOL_ACCESS.get(self._role, set())
            return [name for name in self._tools.keys() if name in allowed]
        return list(self._tools.keys())

    def list_all_tools(self) -> List[str]:
        """List all registered tools (ignoring role)."""
        return list(self._tools.keys())

    def find_by_goal(self, goal: str) -> List[BaseTool]:
        """Find tools relevant to a goal (with access control)."""
        matches = []
        goal_lower = goal.lower()
        allowed = ROLE_TOOL_ACCESS.get(self._role, set()) if self._role else None

        for tool in self._tools.values():
            # Check access
            if allowed is not None and tool.name not in allowed:
                continue

            # Keyword match
            if any(
                keyword in goal_lower
                for keyword in tool.description.lower().split()
            ):
                matches.append(tool)

        return matches

    def get_access_log(self) -> List[Dict[str, Any]]:
        """Get tool access log for auditing."""
        return self._access_log.copy()

    def set_role(self, role: AgentRole):
        """Change the role for access control."""
        self._role = role
        logger.info(f"Registry role set to: {role.value}")


def create_role_based_toolbox(role: AgentRole) -> ToolRegistry:
    """
    Create a toolbox restricted to a specific role.

    Args:
        role: The agent role to restrict tools for

    Returns:
        ToolRegistry with role-based access control
    """
    from .content_tools import (
        BenefitsExtractorTool,
        ComparisonTool,
        FAQGeneratorTool,
        UsageExtractorTool,
    )

    registry = ToolRegistry(role=role)
    registry.register(BenefitsExtractorTool())
    registry.register(UsageExtractorTool())
    registry.register(FAQGeneratorTool())
    registry.register(ComparisonTool())
    return registry
