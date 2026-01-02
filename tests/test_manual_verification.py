import os
import unittest
from unittest.mock import MagicMock, patch

from skincare_agent_system.cognition.memory import MemorySystem

# Import system components
from skincare_agent_system.cognition.reasoning import TreeOfThoughts
from skincare_agent_system.infrastructure.aql import AgentQuery, QueryProcessor
from skincare_agent_system.tools import AgentRole, MCPRegistry, ToolResult
from skincare_agent_system.tools.content_tools import FAQGeneratorTool


class TestVerification(unittest.TestCase):
    """
    Consolidated verification tests migrated from verify_reasoning.py and verify_mcp.py.
    """

    def test_semantic_memory(self):
        print("\n--- Testing Semantic Memory ---")
        memory = MemorySystem()

        # 1. Add Documents
        memory.semantic.add_document(
            "Niacinamide is great for brightening skin and reducing pore size.",
            metadata={"source": "textbook"},
            tags=["ingredient", "brightening"],
        )
        memory.semantic.add_document(
            "Retinol helps with anti-aging by increasing cell turnover.",
            metadata={"source": "research"},
            tags=["ingredient", "aging"],
        )

        # 2. Retrieve
        results = memory.semantic.retrieve("brightening skin")
        self.assertTrue(len(results) > 0)
        self.assertIn("Niacinamide", results[0].content)

        # 3. Retrieve by tag boost
        results_tag = memory.semantic.retrieve("aging")
        self.assertTrue(len(results_tag) > 0)
        self.assertIn("Retinol", results_tag[0].content)

    def test_tot_structure(self):
        print("\n--- Testing Tree of Thoughts Structure ---")
        tot = TreeOfThoughts(max_depth=2, branching_factor=2)
        # Just verify instantiation and basic config
        self.assertEqual(tot.max_depth, 2)
        self.assertEqual(tot.branching_factor, 2)

    def test_mcp_registry(self):
        print("\n--- Testing MCP Registry ---")
        mcp = MCPRegistry()
        mcp.register(FAQGeneratorTool())

        # List Tools
        tools = mcp.list_tools()
        self.assertTrue(len(tools) > 0)
        self.assertIn("inputSchema", tools[0])

        # Call Tool (Validation Failure Expected)
        # We handle this by checking the result is not successful or has error
        # In the original script it printed "Call Result"
        result = mcp.call_tool("faq_generator", {"product_data": {}})
        # The tool catches validation errors and returns success=False
        self.assertFalse(result.success)
        self.assertIn("recoverable", str(result))

    def test_aql(self):
        print("\n--- Testing AQL ---")
        data = {
            "product": {
                "name": "GlowBoost",
                "price": 29.99,
                "ingredients": ["Vit C", "H2O"],
            }
        }

        q = AgentQuery(
            select=["name", "price"], from_source="product", where={"name": "GlowBoost"}
        )

        result = QueryProcessor.execute(q, data)
        self.assertEqual(result.get("name"), "GlowBoost")
        self.assertNotIn("ingredients", result)


if __name__ == "__main__":
    unittest.main()
