"""
SAM Common Foundation Module: Shared Types, Network Probe, and Configuration Engine.
"""

from src.sam.common.types import (
    RiskLevel,
    ActionStatus,
    DecisionType,
    PersonalityMode,
    ToolCall,
    BrainDecision,
    ConversationTurn,
    ActiveContext,
    ExecutionResult,
    NetworkStatus,
)
from src.sam.common.network import (
    probe_socket,
    is_online,
    check_online_async,
    set_forced_connectivity,
    get_forced_connectivity,
    NetworkMonitor,
)
from src.sam.common.config import (
    SamConfig,
    OllamaConfig,
    NetworkConfig,
    PathConfig,
    SafetyConfig,
    VoiceConfig,
    PersonalityConfig,
    get_config,
    set_config,
    reset_config,
)

__all__ = [
    "RiskLevel",
    "ActionStatus",
    "DecisionType",
    "PersonalityMode",
    "ToolCall",
    "BrainDecision",
    "ConversationTurn",
    "ActiveContext",
    "ExecutionResult",
    "NetworkStatus",
    "probe_socket",
    "is_online",
    "check_online_async",
    "set_forced_connectivity",
    "get_forced_connectivity",
    "NetworkMonitor",
    "SamConfig",
    "OllamaConfig",
    "NetworkConfig",
    "PathConfig",
    "SafetyConfig",
    "VoiceConfig",
    "PersonalityConfig",
    "get_config",
    "set_config",
    "reset_config",
]
