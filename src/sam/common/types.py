"""
SAM Common Types and Data Contracts.
Defines enums, Pydantic schemas, and data structures shared across all SAM modules.
Strictly conforms to PROJECT.md lines 115-157 and M1 blueprints.
"""

from __future__ import annotations
from enum import Enum
import time
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class RiskLevel(str, Enum):
    """
    Tri-tier risk classification for all assistant actions.
    - LOW: Read-only queries, opening apps, screenshots, volume. Immediate execution.
    - MEDIUM: Moving files, closing programs. Spoken announcement before execution.
    - HIGH: Deleting files, killing processes, terminal scripts. Hard confirmation barrier.
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @classmethod
    def from_str(cls, val: str) -> "RiskLevel":
        """Parse string to RiskLevel case-insensitively."""
        normalized = val.strip().upper()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Invalid RiskLevel: '{val}'. Expected LOW, MEDIUM, or HIGH.")

    def is_at_least(self, other: "RiskLevel") -> bool:
        """Return True if self has equal or higher risk than other."""
        severity_order = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3}
        return severity_order[self] >= severity_order[other]


class ActionStatus(str, Enum):
    """Lifecycle status for planned and executed actions."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class DecisionType(str, Enum):
    """Categorization of decision emitted by the AI Brain."""
    REPLY = "reply"
    TOOL_CALL = "tool_call"
    PLAN = "plan"


class PersonalityMode(str, Enum):
    """Operational mode of the JARVIS personality engine."""
    CASUAL = "casual"
    TASK = "task"


# ============================================================================
# Base Model with Dual Pydantic v1/v2 Compatibility
# ============================================================================

class CompatibleBaseModel(BaseModel):
    """Base model providing dual Pydantic v1 and v2 convenience methods."""
    model_config = {"extra": "ignore"}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize model to dictionary across Pydantic v1/v2."""
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return self.dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Any:
        """Deserialize model from dictionary across Pydantic v1/v2."""
        if hasattr(cls, "model_validate"):
            return cls.model_validate(data)
        return cls.parse_obj(data)

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:
        """Ensure model_dump is callable even on Pydantic v1."""
        if hasattr(super(), "model_dump"):
            return super().model_dump(*args, **kwargs)
        return self.dict(*args, **kwargs)

    @classmethod
    def model_validate(cls, obj: Any, *args, **kwargs) -> Any:
        """Ensure model_validate is callable even on Pydantic v1."""
        if hasattr(super(), "model_validate"):
            return super().model_validate(obj, *args, **kwargs)
        return cls.parse_obj(obj, *args, **kwargs)


# ============================================================================
# Core Data Models
# ============================================================================

class ToolCall(CompatibleBaseModel):
    """Represents an invocation of an operating system or system tool."""
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    risk_level: Optional[RiskLevel] = None
    call_id: Optional[str] = None


class BrainDecision(CompatibleBaseModel):
    """
    Structured reasoning output produced by the AI Brain.
    Represents either a direct conversation reply, a single tool call,
    or the initiation of a multi-step execution plan.
    """
    decision_type: str  # "reply" | "tool_call" | "plan"
    reply_text: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    plan_goal: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    reasoning: Optional[str] = None
    model_used: Optional[str] = None
    is_offline_fallback: bool = False

    @property
    def is_reply(self) -> bool:
        return self.decision_type == DecisionType.REPLY.value or (
            self.reply_text is not None and not self.tool_call and not self.plan_goal
        )

    @property
    def is_tool_call(self) -> bool:
        return self.decision_type == DecisionType.TOOL_CALL.value or self.tool_call is not None

    @property
    def is_plan(self) -> bool:
        return self.decision_type == DecisionType.PLAN.value or self.plan_goal is not None


class ConversationTurn(CompatibleBaseModel):
    """A single interactive dialogue exchange between user and assistant."""
    user_input: str
    agent_response: str
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActiveContext(CompatibleBaseModel):
    """
    Tracks state across turns: active app, website, task, subject entity,
    and history of recent conversation turns.
    """
    active_app: Optional[str] = None
    current_url: Optional[str] = None
    active_task: Optional[str] = None
    active_subject: Optional[str] = None
    history: List[ConversationTurn] = Field(default_factory=list)
    last_interaction_time: float = Field(default_factory=time.time)

    def add_turn(
        self,
        user_input: str,
        agent_response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationTurn:
        """Append turn to conversation history and update timestamp."""
        turn = ConversationTurn(
            user_input=user_input,
            agent_response=agent_response,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        self.history.append(turn)
        self.last_interaction_time = turn.timestamp
        return turn

    def get_last_turn(self) -> Optional[ConversationTurn]:
        """Return the most recent conversation turn or None."""
        return self.history[-1] if self.history else None

    def clear_context(self) -> None:
        """Reset contextual state and dialogue history."""
        self.active_app = None
        self.current_url = None
        self.active_task = None
        self.active_subject = None
        self.history.clear()
        self.last_interaction_time = time.time()

    def update_active_app(self, app_name: Optional[str], url: Optional[str] = None) -> None:
        """Update focused application and optional URL."""
        self.active_app = app_name
        if url is not None:
            self.current_url = url
        self.last_interaction_time = time.time()

    def format_history_for_prompt(self, max_turns: int = 5) -> str:
        """Format recent dialogue history into compact string for LLM prompting."""
        recent = self.history[-max_turns:] if max_turns > 0 else self.history
        if not recent:
            return "No previous dialogue."
        lines = []
        for t in recent:
            lines.append(f"User: {t.user_input}")
            lines.append(f"SAM: {t.agent_response}")
        return "\n".join(lines)


class ExecutionResult(CompatibleBaseModel):
    """Outcome payload returned after tool or sub-task execution."""
    success: bool
    output: Any = None
    error_message: Optional[str] = None
    verification_passed: bool = True
    execution_time_ms: float = 0.0


class NetworkStatus(CompatibleBaseModel):
    """Snapshot of network connectivity state."""
    is_online: bool
    latency_ms: Optional[float] = None
    checked_at: float = Field(default_factory=time.time)
    target_host: str = "8.8.8.8"
    target_port: int = 53
