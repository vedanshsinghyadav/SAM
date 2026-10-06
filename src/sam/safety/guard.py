"""
Safety and Permission Guard Subsystem.
Implements Tri-Tier Risk Classification (LOW, MEDIUM, HIGH) and confirmation barriers.
"""

from __future__ import annotations
import re
from typing import Dict, List, Set, Tuple
from src.sam.common.types import ToolCall, RiskLevel
from src.sam.safety.interface import ISafetyGuard

LOW_RISK_TOOLS: Set[str] = {
    # App and media
    "open_app", "launch_app", "start_app",
    "control_volume", "volume_control",
    "control_brightness", "brightness_control",
    "media_play", "control_media", "media_control",
    # System and notification queries
    "get_system_stats", "system_stats", "read_notifications", "get_notifications",
    # Read-only file queries
    "find_files", "find_file", "find_latest", "list_files", "search_files",
    "read_file", "open_file",
    # Screen & vision inspection
    "inspect_screen", "capture_screen", "verify_ui_state",
    # Web & search
    "web_search", "browser_navigate", "youtube_search",
    # Empty boundary
    "",
}

MEDIUM_RISK_TOOLS: Set[str] = {
    "close_app", "terminate_process", "kill_process",
    "move_file", "move",
    "rename_file", "rename",
    "create_file", "create_dir", "make_dir", "copy_file", "copy",
    "install_software", "install_package",
    "manage_window",
    "run_terminal",
    "set_system_setting",
}

HIGH_RISK_TOOLS: Set[str] = {
    "delete_files", "delete_file", "delete_dir", "delete_directory", "delete_folder",
    "format_disk", "format_drive", "format_partition",
    "send_message", "send_email", "send_slack", "post_message",
    "execute_sensitive_cmd", "sensitive_command", "run_admin_cmd",
    "wipe_system_cache", "wipe_disk", "destroy_volume", "purge_database",
}

HIGH_RISK_KEYWORDS: Tuple[str, ...] = (
    "delete", "destroy", "wipe", "erase", "format", "purge",
    "nuke", "drop", "uninstall", "remove_all",
)

MEDIUM_RISK_KEYWORDS: Tuple[str, ...] = (
    "move", "rename", "kill", "terminate", "close", "install",
    "modify", "update", "write", "overwrite",
)

DANGEROUS_COMMAND_PATTERNS: List[str] = [
    r"\b(rm|rmdir|del|erase|unlink)\b",
    r"\bRemove-Item\b",
    r"shutil\.rmtree",
    r"\bformat\s+[a-zA-Z]:",
    r"\b(diskpart|fdisk|mkfs)\b",
    r"vssadmin\s+delete\s+shadows",
    r"\bSet-ExecutionPolicy\b",
    r"\breg\s+(add|delete)\b",
    r"\bnet\s+user\b",
    r"\b(iex|Invoke-Expression)\b",
    r"curl\b.*\|\s*(bash|sh|powershell|cmd)",
    r"powershell\b.*-(e|enc|encodedcommand)\b",
    r"\b(shutdown|Restart-Computer|stop-computer)\b",
    r"\b(DROP\s+DATABASE|DROP\s+TABLE|TRUNCATE\s+TABLE)\b",
]

SENSITIVE_PATHS_REGEX = re.compile(
    r"(^[a-zA-Z]:\\Windows(\\|\b))|"
    r"(^[a-zA-Z]:\\(Program Files|Program Files \(x86\))(\\|\b))|"
    r"(\bSystem32\b)|(\bSysWOW64\b)|(\bbootmgr\b)|(\bNTLDR\b)|"
    r"(^/etc/)|(^/sys/)|(^/boot/)|(^/usr/bin/)",
    re.IGNORECASE,
)

AFFIRMATIVE_TOKENS: Set[str] = {
    "confirm", "confirmed", "confirming",
    "yes", "y", "yeah", "yep", "sure", "ok", "okay",
    "proceed", "affirmative", "agreed", "do it",
    # Hinglish
    "haan", "ha", "kar do", "kardo", "haan kar do", "bilkul",
}

NEGATIVE_TOKENS: Set[str] = {
    "no", "n", "nope", "cancel", "cancelled",
    "stop", "abort", "never", "don't", "dont",
    # Hinglish
    "nahi", "nah", "mat karo", "roko",
}


class SafetyGuard(ISafetyGuard):
    """
    Enforces Tri-Tier Risk Classification and Confirmation Barriers.
    - LOW: Immediate execution (no announcement, no confirmation)
    - MEDIUM: Pre-execution announcement logged and communicated
    - HIGH: Mandatory blocking confirmation barrier (requires explicit user confirmation)
    """

    def __init__(self):
        self.announcements: List[str] = []

    def classify_risk(self, tool_call: ToolCall) -> RiskLevel:
        """Categorize a tool call into LOW, MEDIUM, or HIGH risk level."""
        name = (tool_call.tool_name or "").strip().lower()
        args: Dict = tool_call.arguments or {}

        # 1. Empty tool name boundary
        if not name:
            inherent = RiskLevel.LOW
        # 2. Explicit HIGH Risk tool name match
        elif name in HIGH_RISK_TOOLS:
            inherent = RiskLevel.HIGH
        # 3. HIGH Risk keyword match in tool name
        elif any(kw in name for kw in HIGH_RISK_KEYWORDS):
            inherent = RiskLevel.HIGH
        # 4. Deep inspection for terminal runners (run_terminal)
        elif name in ["run_terminal", "terminal", "powershell", "cmd", "bash", "shell"]:
            command = str(args.get("command") or args.get("cmd") or "")
            if any(re.search(pat, command, re.IGNORECASE) for pat in DANGEROUS_COMMAND_PATTERNS):
                inherent = RiskLevel.HIGH
            else:
                inherent = RiskLevel.MEDIUM
        # 5. Deep inspection for sensitive filesystem targets
        elif any(
            str(args.get(path_key) or "") and SENSITIVE_PATHS_REGEX.search(str(args.get(path_key) or ""))
            for path_key in ["path", "src", "dst", "directory", "target"]
        ):
            inherent = RiskLevel.HIGH
        # 6. Explicit MEDIUM Risk tool name match
        elif name in MEDIUM_RISK_TOOLS:
            inherent = RiskLevel.MEDIUM
        # 7. MEDIUM Risk keyword match in tool name
        elif any(kw in name for kw in MEDIUM_RISK_KEYWORDS):
            inherent = RiskLevel.MEDIUM
        # 8. Explicit LOW Risk tool name match or safe fallback
        else:
            inherent = RiskLevel.LOW

        # Defense-in-depth: Caller cannot downgrade inherently dangerous tools
        if tool_call.risk_level is not None:
            if tool_call.risk_level.is_at_least(inherent):
                return tool_call.risk_level
        return inherent

    def authorize(self, tool_call: ToolCall, user_confirmed: bool = False) -> Tuple[bool, str]:
        """Authorize tool execution based on classified risk and user confirmation."""
        effective_risk = self.classify_risk(tool_call)

        # LOW RISK: Immediate execution, no announcements
        if effective_risk == RiskLevel.LOW:
            return True, "Authorized: Low risk immediate dispatch"

        # MEDIUM RISK: Log announcement and allow execution
        if effective_risk == RiskLevel.MEDIUM:
            msg = f"Announcing medium risk action: executing {tool_call.tool_name}"
            self.announcements.append(msg)
            return True, msg

        # HIGH RISK: Strict boolean True check, never leak to announcements
        if effective_risk == RiskLevel.HIGH:
            if user_confirmed is True:
                return True, "Authorized: User confirmed high risk action"
            return False, f"Blocked: Action '{tool_call.tool_name}' requires explicit confirmation."

        return False, "Blocked: Unknown risk classification"

    def generate_confirmation_prompt(self, tool_call: ToolCall) -> str:
        """Formulate explicit prompt detailing target entities before action."""
        name = (tool_call.tool_name or "").strip().lower()
        args: Dict = tool_call.arguments or {}

        if "delete" in name:
            target = args.get("path") or args.get("target") or "specified files"
            return f"Are you sure you want to delete all files in {target}? Please confirm."

        if "format" in name:
            drive = args.get("drive") or "target drive"
            return f"DANGER: Are you sure you want to format disk {drive}? This will permanently erase all data. Please confirm."

        if "send_message" in name or "send_email" in name:
            recipient = args.get("recipient") or args.get("to") or "recipient"
            return f"Are you sure you want to send message to '{recipient}'? Please confirm."

        if "terminal" in name or "sensitive" in name:
            cmd = args.get("command") or args.get("cmd") or "command"
            return f"Are you sure you want to execute command '{cmd}'? Please confirm."

        return f"Action '{tool_call.tool_name}' is high-risk and requires confirmation. Please confirm."

    def is_affirmative_confirmation(self, user_response: str) -> bool:
        """Determine if natural language user input constitutes affirmative confirmation."""
        if not user_response or not isinstance(user_response, str):
            return False

        cleaned = re.sub(r"[^\w\s]", "", user_response.strip().lower())
        tokens = set(cleaned.split())

        # Check for negative tokens first (negation takes precedence)
        for neg in NEGATIVE_TOKENS:
            if " " in neg:
                if neg in cleaned:
                    return False
            else:
                if neg in tokens:
                    return False

        # Check for affirmative match
        for aff in AFFIRMATIVE_TOKENS:
            if " " in aff:
                if aff in cleaned:
                    return True
            else:
                if aff in tokens:
                    return True

        return False
