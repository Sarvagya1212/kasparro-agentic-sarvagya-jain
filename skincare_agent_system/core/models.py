import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- Transition States (User Requirement) ---
class AgentStatus(Enum):
    CONTINUE = "CONTINUE"  # Formerly SUCCESS
    RETRY = "RETRY"  # Formerly NEEDS_DATA or partial failure
    VALIDATION_FAILED = "VALIDATION_FAILED"  # Formerly FAILED in Validation
    COMPLETE = "COMPLETE"  # Formerly COMPLETED (System finish)
    ERROR = "ERROR"  # Catastrophic failure


class SystemState(Enum):
    IDLE = "IDLE"
    FETCHING_DATA = "FETCHING_DATA"
    ANALYZING = "ANALYZING"
    VALIDATING = "VALIDATING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


# --- Role & Prompt Engineering Models ---
class TaskPriority(str, Enum):
    SYSTEM = "SYSTEM"  # Validates safety/regulations (Highest)
    USER = "USER"  # Checks against system regulations
    HISTORY = "HISTORY"  # Context from previous turns
    TOOL = "TOOL"  # Output from tool execution


class TaskDirective(BaseModel):
    """Structured instruction for agents."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    priority: TaskPriority
    schema_definition: Optional[Dict[str, Any]] = (
        None  # Optional JSON schema for expected output
    )


# --- Strict Data Models (User Requirement) ---
class ProductData(BaseModel):
    """Strict schema for product data."""

    name: str
    brand: str
    concentration: Optional[str] = None
    key_ingredients: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    price: Optional[float] = None
    currency: str = "INR"
    size: Optional[str] = None
    skin_types: List[str] = Field(default_factory=list)
    side_effects: Optional[str] = None
    usage_instructions: Optional[str] = None  # data source might have 'how_to_use'


class ComparisonData(BaseModel):
    """Strict schema for comparison product."""

    name: str
    brand: str
    key_ingredients: List[str] = Field(default_factory=list)
    price: Optional[float] = None


class AnalysisResults(BaseModel):
    """Strict schema for analysis output."""

    benefits: List[str] = Field(default_factory=list)
    usage: str = ""
    comparison: Dict[str, Any] = Field(
        default_factory=dict
    )  # Keep nested dict for now complexity


class AgentContext(BaseModel):
    """Shared state object passed between agents."""

    # Typed Data Fields
    product_data: Optional[ProductData] = None
    comparison_data: Optional[ProductData] = (
        None  # Use ProductData schema for B as well
    )

    # Analysis results
    analysis_results: Optional[AnalysisResults] = None
    generated_questions: List[Any] = Field(default_factory=list)

    # Validation state
    validation_errors: List[str] = Field(default_factory=list)
    is_valid: bool = False

    # Metadata
    execution_history: List[str] = Field(default_factory=list)
    decision_log: List[Dict[str, str]] = Field(default_factory=list)

    def log_step(self, step_name: str):
        self.execution_history.append(step_name)

    def log_decision(self, agent_name: str, reason: str):
        self.decision_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "agent": agent_name,
                "reason": reason,
            }
        )


class AgentResult(BaseModel):
    """Standardized return object for all agents."""

    agent_name: str
    status: AgentStatus
    context: AgentContext
    message: str = ""
