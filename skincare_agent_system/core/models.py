import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


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
    schema_definition: Optional[Dict[str, Any]] = None


# --- Strict Data Models (User Requirement) ---
class ProductData(BaseModel):
    """Strict schema for product data with validation."""

    name: str = Field(..., min_length=1, description="Product name")
    brand: str = Field(..., min_length=1, description="Brand name")
    concentration: Optional[str] = None
    key_ingredients: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    price: Optional[float] = Field(None, ge=0, description="Price must be non-negative")
    currency: str = "INR"
    size: Optional[str] = None
    skin_types: List[str] = Field(default_factory=list)
    side_effects: Optional[str] = None
    usage_instructions: Optional[str] = None

    @field_validator('skin_types')
    @classmethod
    def validate_skin_types(cls, v):
        valid_types = ['Oily', 'Dry', 'Combination', 'Sensitive', 'Normal', 'All']
        for skin_type in v:
            if skin_type not in valid_types:
                # Allow but warn - don't break for flexibility
                pass
        return v


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
    comparison: Dict[str, Any] = Field(default_factory=dict)


# --- FAQ Models with Validation ---
class FAQQuestion(BaseModel):
    """Single FAQ question-answer pair with validation."""

    question: str = Field(..., min_length=5)
    answer: str = Field(..., min_length=10)
    category: str = Field(default="General")

    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        valid = ['Informational', 'Safety', 'Usage', 'Purchase', 'Comparison', 'Ingredients', 'General']
        if v not in valid:
            return 'General'  # Default to General if invalid
        return v


class FAQOutput(BaseModel):
    """Complete FAQ page output with 15+ question validation."""

    product_name: str
    questions: List[FAQQuestion] = Field(default_factory=list)

    @field_validator('questions')
    @classmethod
    def validate_question_count(cls, v):
        if len(v) < 15:
            raise ValueError(f"Must have at least 15 questions, got {len(v)}")
        return v


class AgentContext(BaseModel):
    """Shared state object passed between agents."""

    # Typed Data Fields
    product_data: Optional[ProductData] = None
    comparison_data: Optional[ProductData] = None

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
        self.decision_log.append({
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "reason": reason,
        })


class AgentResult(BaseModel):
    """Standardized return object for all agents."""

    agent_name: str
    status: AgentStatus
    context: AgentContext
    message: str = ""

    @field_validator('message')
    @classmethod
    def validate_error_message(cls, v, info):
        # If status is ERROR, message should be present
        if info.data.get('status') == AgentStatus.ERROR and not v:
            return "Unknown error"
        return v

