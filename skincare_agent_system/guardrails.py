"""
Guardrails: Programmatic hooks to validate inputs and outputs.
Implements safety checks before LLM processing and tool execution.
"""

import logging
import re
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger("Guardrails")


class Guardrails:
    """
    Safety guardrails for the agent system.
    Provides callbacks for input validation and tool argument checking.
    """

    # Blocked keywords for input validation
    BLOCKED_KEYWORDS: Set[str] = {
        "ignore instructions",
        "bypass safety",
        "ignore system",
        "forget previous",
        "disregard rules",
        "jailbreak",
        "pretend you are",
        "act as if",
    }

    # PII patterns to detect
    PII_PATTERNS: List[re.Pattern] = [
        re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),  # Phone numbers
        re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),  # Credit cards
        re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),  # PAN numbers (India)
        re.compile(r"\b\d{12}\b"),  # Aadhaar-like numbers
    ]

    # Allowed tools and their parameter constraints
    TOOL_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
        "benefits_extractor": {
            "required_params": ["product_data"],
            "max_input_size": 10000,
        },
        "usage_extractor": {
            "required_params": ["product_data"],
            "max_input_size": 10000,
        },
        "faq_generator": {
            "required_params": ["product_data"],
            "allowed_params": ["product_data", "min_questions"],
            "max_questions": 50,
        },
        "product_comparison": {
            "required_params": ["product_a", "product_b"],
        },
    }

    @classmethod
    def before_model_callback(cls, input_text: str) -> Tuple[bool, str]:
        """
        Validate user input before sending to LLM.

        Args:
            input_text: The input text to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not input_text:
            return True, ""

        input_lower = input_text.lower()

        # Check for blocked keywords (prompt injection attempts)
        for keyword in cls.BLOCKED_KEYWORDS:
            if keyword in input_lower:
                logger.warning(
                    f"BLOCKED: Input contains forbidden keyword: '{keyword}'"
                )
                return False, f"Input blocked: contains forbidden pattern '{keyword}'"

        # Check for PII
        for pattern in cls.PII_PATTERNS:
            if pattern.search(input_text):
                logger.warning("BLOCKED: Input contains potential PII")
                return (
                    False,
                    "Input blocked: contains potential personally identifiable information",
                )

        # Check input length
        if len(input_text) > 50000:
            logger.warning("BLOCKED: Input exceeds maximum length")
            return False, "Input blocked: exceeds maximum allowed length"

        logger.info("Input validation passed")
        return True, ""

    @classmethod
    def before_tool_callback(
        cls, tool_name: str, args: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validate tool arguments before execution.

        Args:
            tool_name: Name of the tool being called
            args: Arguments being passed to the tool

        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.info(f"Validating tool call: {tool_name}")

        # Check if tool is known
        if tool_name not in cls.TOOL_CONSTRAINTS:
            # Allow unknown tools but log warning
            logger.warning(f"Unknown tool: {tool_name}. Allowing with caution.")
            return True, ""

        constraints = cls.TOOL_CONSTRAINTS[tool_name]

        # Check required parameters
        if "required_params" in constraints:
            for param in constraints["required_params"]:
                if param not in args:
                    logger.warning(f"Tool {tool_name} missing required param: {param}")
                    return False, f"Missing required parameter: {param}"

        # Check allowed parameters (if specified, only these are allowed)
        if "allowed_params" in constraints:
            for param in args.keys():
                if param not in constraints["allowed_params"]:
                    logger.warning(f"Tool {tool_name} has disallowed param: {param}")
                    return False, f"Disallowed parameter: {param}"

        # Check specific constraints
        if "max_questions" in constraints and "min_questions" in args:
            if args["min_questions"] > constraints["max_questions"]:
                return (
                    False,
                    f"min_questions exceeds max allowed: {constraints['max_questions']}",
                )

        if "max_input_size" in constraints and "product_data" in args:
            data_size = len(str(args["product_data"]))
            if data_size > constraints["max_input_size"]:
                return (
                    False,
                    f"product_data exceeds max size: {constraints['max_input_size']}",
                )

        logger.info(f"Tool validation passed for: {tool_name}")
        return True, ""

    @classmethod
    def check_output_safety(cls, output: str) -> Tuple[bool, str]:
        """
        Check if output contains unsafe content.

        Args:
            output: The generated output text

        Returns:
            Tuple of (is_safe, error_message)
        """
        if not output:
            return True, ""

        # Check for PII in output
        for pattern in cls.PII_PATTERNS:
            if pattern.search(output):
                logger.warning("UNSAFE OUTPUT: Contains potential PII")
                return False, "Output contains potential PII"

        return True, ""
