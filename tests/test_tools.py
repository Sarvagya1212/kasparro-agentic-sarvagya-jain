"""
Tests for Tooling Best Practices.
Run with: pytest tests/test_tools.py
"""

import pytest

from skincare_agent_system.tools import (
    AgentRole,
    BaseTool,
    ROLE_TOOL_ACCESS,
    ToolRegistry,
    ToolResult,
    create_role_based_toolbox,
)
from skincare_agent_system.tools.content_tools import (
    BenefitsExtractorTool,
    FAQGeneratorTool,
    create_default_toolbox,
)


class TestRoleBasedAccess:
    """Tests for role-based tool access control."""

    def test_benefits_worker_has_limited_access(self):
        """Benefits worker should only access benefits_extractor."""
        toolbox = create_role_based_toolbox(AgentRole.BENEFITS_WORKER)

        # Should have access
        assert toolbox.get("benefits_extractor") is not None

        # Should NOT have access
        assert toolbox.get("faq_generator") is None
        assert toolbox.get("product_comparison") is None

    def test_delegator_has_full_access(self):
        """Delegator should access all content tools."""
        toolbox = create_role_based_toolbox(AgentRole.DELEGATOR)

        assert toolbox.get("benefits_extractor") is not None
        assert toolbox.get("usage_extractor") is not None
        assert toolbox.get("faq_generator") is not None
        assert toolbox.get("product_comparison") is not None

    def test_verifier_has_no_tools(self):
        """Verifier should not have tool access."""
        toolbox = create_role_based_toolbox(AgentRole.VERIFIER)

        tools = toolbox.list_tools()
        assert len(tools) == 0

    def test_access_log_tracks_denials(self):
        """Access log should track denied attempts."""
        toolbox = create_role_based_toolbox(AgentRole.BENEFITS_WORKER)

        # Attempt denied access
        toolbox.get("faq_generator")

        log = toolbox.get_access_log()
        denied = [e for e in log if e["access"] == "denied"]
        assert len(denied) >= 1


class TestGracefulErrorHandling:
    """Tests for graceful tool error handling."""

    def test_missing_input_returns_error(self):
        """Missing input should return descriptive error."""
        tool = BenefitsExtractorTool()
        result = tool.run(product_data=None)

        assert result.success is False
        assert "required" in result.error.lower()
        assert result.error_type == "validation_error"
        assert result.recoverable is True

    def test_wrong_type_returns_error(self):
        """Wrong type should return descriptive error."""
        tool = BenefitsExtractorTool()
        result = tool.run(product_data="not a dict")

        assert result.success is False
        assert "type" in result.error.lower() or "dict" in result.error.lower()
        assert result.recoverable is True

    def test_valid_input_succeeds(self):
        """Valid input should succeed."""
        tool = BenefitsExtractorTool()
        result = tool.run(product_data={
            "benefits": ["Brightening", "Hydrating"],
            "key_ingredients": ["Vitamin C"]
        })

        assert result.success is True
        assert result.data is not None


class TestSimplifiedDefinitions:
    """Tests for simplified tool definitions."""

    def test_tool_has_clear_name(self):
        """Tools should have self-documenting names."""
        tool = BenefitsExtractorTool()

        assert tool.name == "benefits_extractor"
        assert "benefits" in tool.name

    def test_tool_has_description(self):
        """Tools should have descriptions."""
        tool = FAQGeneratorTool()

        assert tool.description is not None
        assert len(tool.description) > 0

    def test_tool_docstring_documents_interface(self):
        """Tool docstrings should document input/output."""
        tool = FAQGeneratorTool()

        docstring = tool.__class__.__doc__
        assert "Input" in docstring
        assert "Output" in docstring


class TestToolRegistry:
    """Tests for ToolRegistry functionality."""

    def test_list_tools_respects_role(self):
        """list_tools should respect role restrictions."""
        toolbox = create_role_based_toolbox(AgentRole.BENEFITS_WORKER)

        tools = toolbox.list_tools()
        assert "benefits_extractor" in tools
        assert "faq_generator" not in tools

    def test_list_all_tools_ignores_role(self):
        """list_all_tools should show all registered tools."""
        toolbox = create_role_based_toolbox(AgentRole.BENEFITS_WORKER)

        all_tools = toolbox.list_all_tools()
        assert "benefits_extractor" in all_tools
        assert "faq_generator" in all_tools

    def test_find_by_goal_respects_role(self):
        """find_by_goal should respect role restrictions."""
        toolbox = create_role_based_toolbox(AgentRole.BENEFITS_WORKER)

        matches = toolbox.find_by_goal("extract benefits")
        tool_names = [t.name for t in matches]

        assert "benefits_extractor" in tool_names
        # FAQ also matches "extract" but should be filtered by role
        assert "faq_generator" not in tool_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
