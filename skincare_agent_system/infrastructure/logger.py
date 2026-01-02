"""
Structured Logging for Skincare Agent System.
Provides JSON-formatted logs for production monitoring.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredLogger:
    """Structured logger with JSON output for observability."""

    def __init__(self, name: str, log_dir: str = "logs"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Prevent duplicate handlers
        if not self.logger.handlers:
            # Console handler with human-readable formatting
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

            # File handler for JSON logs (if logs dir exists)
            if os.path.exists(log_dir):
                file_handler = logging.FileHandler(f'{log_dir}/system.log')
                self.logger.addHandler(file_handler)

    def _build_log_entry(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None) -> str:
        """Build structured JSON log entry."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "logger": self.name,
            "message": message,
            **(extra or {})
        }
        return json.dumps(log_data)

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info with structured data."""
        self.logger.info(self._build_log_entry("INFO", message, extra))

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning with structured data."""
        self.logger.warning(self._build_log_entry("WARNING", message, extra))

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log error with structured data."""
        self.logger.error(self._build_log_entry("ERROR", message, extra))

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug with structured data."""
        self.logger.debug(self._build_log_entry("DEBUG", message, extra))

    # --- Specialized Agent Logging ---

    def agent_action(self, agent_name: str, action: str, result: str):
        """Log agent action with context."""
        self.info(f"Agent action: {agent_name}.{action}", extra={
            "agent": agent_name,
            "action": action,
            "result": result,
            "type": "agent_action"
        })

    def proposal_collected(self, agent_name: str, confidence: float, action: str):
        """Log proposal collection."""
        self.info(f"Proposal: {agent_name} -> {action}", extra={
            "agent": agent_name,
            "confidence": confidence,
            "action": action,
            "type": "proposal"
        })

    def proposal_selected(self, agent_name: str, confidence: float, reason: str):
        """Log proposal selection."""
        self.info(f"Selected: {agent_name} (confidence={confidence:.2f})", extra={
            "agent": agent_name,
            "confidence": confidence,
            "reason": reason,
            "type": "selection"
        })

    def workflow_phase(self, phase: str, step: int):
        """Log workflow phase transition."""
        self.info(f"Phase: {phase} (step {step})", extra={
            "phase": phase,
            "step": step,
            "type": "workflow"
        })

    def validation_result(self, passed: bool, errors: int):
        """Log validation result."""
        status = "PASSED" if passed else "FAILED"
        self.info(f"Validation: {status}", extra={
            "passed": passed,
            "error_count": errors,
            "type": "validation"
        })


# Global logger instance
system_logger = StructuredLogger("SAS")


def get_logger(name: str = "SAS") -> StructuredLogger:
    """Get or create a structured logger."""
    return StructuredLogger(name)
