"""
Guardrails: Programmatic hooks to validate inputs and outputs.
Implements safety checks before LLM processing and tool execution.
Includes prompt injection defense.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger("Guardrails")


@dataclass
class InjectionResult:
    """Result of injection detection scan."""

    is_safe: bool
    threats_detected: List[str] = field(default_factory=list)
    sanitized_text: str = ""
    severity: str = "none"  # "none", "low", "medium", "high"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class InjectionDefense:
    """
    Detects and blocks prompt injection attacks.
    Protects agents from malicious input manipulation.
    """

    # Common injection patterns
    INJECTION_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
        # (pattern, threat_name, severity)
        (
            re.compile(r"ignore\s+(all\s+)?(previous\s+)?(instructions?|rules?)", re.I),
            "instruction_override",
            "high",
        ),
        (
            re.compile(r"(disregard|forget)\s+your\s+(system|instructions?)", re.I),
            "system_bypass",
            "high",
        ),
        (re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I), "role_hijack", "high"),
        (
            re.compile(r"new\s+(task|instructions?):\s*", re.I),
            "task_injection",
            "medium",
        ),
        (re.compile(r"```system", re.I), "system_block_injection", "high"),
        (re.compile(r"\[INST\]|\[/INST\]", re.I), "llama_format_injection", "medium"),
        (
            re.compile(r"<\|im_start\|>|<\|im_end\|>", re.I),
            "chatml_format_injection",
            "medium",
        ),
        (
            re.compile(r"<\|system\|>|<\|user\|>|<\|assistant\|>", re.I),
            "role_tag_injection",
            "high",
        ),
        (
            re.compile(r"pretend\s+(you\s+are|to\s+be)", re.I),
            "persona_override",
            "medium",
        ),
        (re.compile(r"act\s+as\s+(if|though|a)", re.I), "behavior_override", "medium"),
        (
            re.compile(r"do\s+not\s+follow\s+(any|your|the)\s+", re.I),
            "rule_bypass",
            "high",
        ),
        (
            re.compile(r"override\s+(safety|security|rules?)", re.I),
            "safety_override",
            "high",
        ),
    ]

    # Dangerous command patterns
    DANGEROUS_COMMANDS: List[Tuple[re.Pattern, str]] = [
        (re.compile(r"rm\s+-rf", re.I), "destructive_command"),
        (re.compile(r"delete\s+all", re.I), "mass_delete"),
        (re.compile(r"DROP\s+TABLE", re.I), "sql_injection"),
        (re.compile(r"exec\s*\(", re.I), "code_execution"),
        (re.compile(r"eval\s*\(", re.I), "code_execution"),
    ]

    @classmethod
    def detect_injection(cls, input_text: str) -> InjectionResult:
        """
        Scan input for prompt injection attempts.

        Args:
            input_text: Text to scan

        Returns:
            InjectionResult with detection details
        """
        if not input_text:
            return InjectionResult(is_safe=True, sanitized_text="")

        threats = []
        max_severity = "none"
        severity_order = {"none": 0, "low": 1, "medium": 2, "high": 3}

        # Check injection patterns
        for pattern, threat_name, severity in cls.INJECTION_PATTERNS:
            if pattern.search(input_text):
                threats.append(threat_name)
                if severity_order[severity] > severity_order[max_severity]:
                    max_severity = severity

        # Check dangerous commands
        for pattern, threat_name in cls.DANGEROUS_COMMANDS:
            if pattern.search(input_text):
                threats.append(threat_name)
                max_severity = "high"

        is_safe = len(threats) == 0
        sanitized = cls.sanitize_input(input_text) if not is_safe else input_text

        result = InjectionResult(
            is_safe=is_safe,
            threats_detected=threats,
            sanitized_text=sanitized,
            severity=max_severity,
        )

        if not is_safe:
            logger.warning(
                f"INJECTION DETECTED: {len(threats)} threats, "
                f"severity: {max_severity}, patterns: {threats}"
            )

        return result

    @classmethod
    def sanitize_input(cls, text: str) -> str:
        """
        Remove or escape potentially dangerous patterns.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text
        """
        sanitized = text

        # Remove injection patterns
        for pattern, _, _ in cls.INJECTION_PATTERNS:
            sanitized = pattern.sub("[REMOVED]", sanitized)

        # Remove dangerous commands
        for pattern, _ in cls.DANGEROUS_COMMANDS:
            sanitized = pattern.sub("[BLOCKED]", sanitized)

        # Escape special tokens
        special_tokens = ["```", "<|", "|>", "[INST]", "[/INST]"]
        for token in special_tokens:
            sanitized = sanitized.replace(token, f"\\{token}")

        return sanitized

    @classmethod
    def check_role_hijack(cls, text: str, expected_role: str) -> bool:
        """
        Detect attempts to change agent's role.

        Args:
            text: Input text
            expected_role: The agent's actual role

        Returns:
            True if role hijack attempt detected
        """
        hijack_patterns = [
            r"you\s+are\s+(now\s+)?(?!{})".format(re.escape(expected_role)),
            r"act\s+as\s+(?!{})".format(re.escape(expected_role)),
            r"pretend\s+to\s+be\s+(?!{})".format(re.escape(expected_role)),
        ]

        for pattern in hijack_patterns:
            if re.search(pattern, text, re.I):
                logger.warning(
                    f"Role hijack attempt detected for role: {expected_role}"
                )
                return True

        return False


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
