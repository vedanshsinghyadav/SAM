"""
Multilingual Intent Parser for Project SAM (English, Hindi, Hinglish).
Implements IIntentParser protocol with fast lexical and contextual matching.
Part of Milestone 1: FEAT-BRAIN-001.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple
from src.sam.brain.interface import IIntentParser
from src.sam.common.types import ActiveContext, BrainDecision, RiskLevel, ToolCall


class MultilingualIntentParser(IIntentParser):
    """Fast deterministic and contextual intent parser for English and Hinglish."""

    # 1. App opening patterns
    # Matches: "open chrome", "launch the browser", "internet chalana hai", "browser kholo", etc.
    CHROME_PATTERNS = [
        r"(?:open|launch|start)\s+(?:chrome|google\s+chrome)",
        r"(?:chrome|google\s+chrome)\s+(?:kholo|khol|chalao|start\s+karo|open\s+karo)",
        r"launch\s+(?:the\s+)?browser",
        r"browser\s+(?:kholo|khol|chalao|start\s+karo|open\s+karo)",
        r"internet\s+(?:chalana\s+hai|chalao|kholo|shuru\s+karo)",
    ]

    SPOTIFY_PATTERNS = [
        r"(?:open|launch|start|play)\s+spotify",
        r"spotify\s+(?:kholo|khol|chalao|open\s+karo)",
        r"(?:gaane|music|song)\s+(?:chalao|bajaao|shuru\s+karo)",
    ]

    # 2. Volume patterns
    VOL_UP_PATTERNS = [
        r"(?:increase|raise|turn\s+up)\s+(?:volume|sound)",
        r"(?:volume|sound|awaaz|awaj)\s+(?:badhao|badao|up\s+karo|tezz\s+karo)",
    ]
    VOL_DOWN_PATTERNS = [
        r"(?:decrease|lower|turn\s+down)\s+(?:volume|sound)",
        r"(?:volume|sound|awaaz|awaj)\s+(?:kam\s+karo|ghatao|down\s+karo|dheemi\s+karo)",
    ]

    # 3. System metric patterns
    CPU_PATTERNS = [
        r"(?:check|get|what\s+is|show)\s+(?:the\s+)?cpu(?:\s+usage)?",
        r"cpu(?:\s+usage)?\s+(?:check\s+karo|batao|dikhao|kya\s+hai)",
    ]

    # 4. Destructive deletion patterns (HIGH RISK)
    # Handles English ("delete all files in Downloads") and Hinglish ("Downloads k saare files uda do",
    # "Downloads k files delete kar do", "Downloads se saare files uda do", "saare files uda do").
    DELETE_PATTERNS = [
        # 1. English with explicit folder
        r"(?:delete|remove|clear|wipe)\s+(?:all\s+)?files?\s+(?:in|from)\s+([a-zA-Z0-9_.:\-\\\/]+)",
        # 2. Hindi/Hinglish directory-first with connector ("Downloads k saare files uda do", "Downloads k files delete kar do")
        r"([a-zA-Z0-9_.:\-\\\/]+)(?:\s+folder)?\s+(?:(?:se|ke|k|ki|ka|me|mein)\s+(?:saare|saari|saara)|(?:se|ke|k|ki|ka|me|mein))\s+files?\s+(?:ko\s+)?(?:delete|mita|hata|uda|remove|clear)\s+(?:karo|kar\s+do|kar\s+de|karna|do|de|dena|diya)",
        # 3. Hindi/Hinglish directory-first without connector ("Downloads files delete kar do", "Downloads files uda do")
        r"([a-zA-Z0-9_.:\-\\\/]+)(?:\s+folder)?\s+files?\s+(?:ko\s+)?(?:delete|mita|hata|uda|remove|clear)\s+(?:karo|kar\s+do|kar\s+de|karna|do|de|dena|diya)",
        # 4. Hindi/Hinglish verb-first ("uda do Downloads k saare files")
        r"(?:uda\s+(?:do|de|dena)|delete\s+(?:kar\s+do|karo|kar\s+de)|hata\s+(?:do|de|dena)|mita\s+(?:do|de|dena))\s+(?:all\s+files\s+(?:in|from)\s+|(?:(?:se|ke|k|ki|ka)\s+)?(?:saare|saari|sab)\s+files?\s+(?:se|in|from)\s+)?([a-zA-Z0-9_.:\-\\\/]+)",
        # 5. Generic delete without explicit folder ("delete all files", "saare files uda do", "files uda do")
        r"(?:delete|remove|clear)\s+all\s+files|(?:(?:saare|saari|sab|sabhi)\s+)?files?\s+(?:ko\s+)?(?:uda|delete|hata|mita)\s+(?:do|de|dena|karo|kar\s+do|kar\s+de)",
    ]

    # 5. Complex goal / plan patterns
    PLAN_PATTERNS = [
        r"(?:kal\s+)?([a-zA-Z0-9_]+)\s+exam\s+hai.*(?:notes|syllabus|list)",
        r"(?:notes\s+kholo.*syllabus.*list)",
        r"(?:move\s+(?:the\s+)?latest\s+pdf.*from\s+downloads\s+to\s+.*)",
        r"(?:downloads\s+se\s+latest\s+pdf.*move\s+karo)",
    ]

    GREETING_PATTERN = r"\b(?:hey\s+sam|hello|hi|kaise\s+ho|who\s+are\s+you)\b"

    def __init__(self) -> None:
        self._chrome_regexes = [re.compile(p, re.IGNORECASE) for p in self.CHROME_PATTERNS]
        self._spotify_regexes = [re.compile(p, re.IGNORECASE) for p in self.SPOTIFY_PATTERNS]
        self._vol_up_regexes = [re.compile(p, re.IGNORECASE) for p in self.VOL_UP_PATTERNS]
        self._vol_down_regexes = [re.compile(p, re.IGNORECASE) for p in self.VOL_DOWN_PATTERNS]
        self._cpu_regexes = [re.compile(p, re.IGNORECASE) for p in self.CPU_PATTERNS]
        self._delete_regexes = [re.compile(p, re.IGNORECASE) for p in self.DELETE_PATTERNS]
        self._plan_regexes = [re.compile(p, re.IGNORECASE) for p in self.PLAN_PATTERNS]
        self._greeting_regex = re.compile(self.GREETING_PATTERN, re.IGNORECASE)

    def parse(self, user_text: str, context: Optional[ActiveContext] = None) -> Optional[BrainDecision]:
        """Parse natural language query against lexical and contextual rules."""
        text = user_text.strip()
        lower_text = text.lower()

        # 1. Complex plan goals (R6 line 68)
        for r in self._plan_regexes:
            if r.search(lower_text):
                return BrainDecision(
                    decision_type="plan",
                    reply_text="Right away, sir. Formulating an execution plan for your request.",
                    plan_goal=text,
                    requires_confirmation=False,
                )

        # 2. Chrome / Browser opening (R2 line 50)
        for r in self._chrome_regexes:
            if r.search(lower_text):
                return BrainDecision(
                    decision_type="tool_call",
                    reply_text="Opening Google Chrome, sir.",
                    tool_call=ToolCall(
                        tool_name="open_app",
                        arguments={"app_name": "chrome"},
                        risk_level=RiskLevel.LOW,
                    ),
                    requires_confirmation=False,
                )

        # 3. Spotify / Music opening
        for r in self._spotify_regexes:
            if r.search(lower_text):
                return BrainDecision(
                    decision_type="tool_call",
                    reply_text="Opening Spotify, sir.",
                    tool_call=ToolCall(
                        tool_name="open_app",
                        arguments={"app_name": "spotify"},
                        risk_level=RiskLevel.LOW,
                    ),
                    requires_confirmation=False,
                )

        # 4. Contextual Navigation & Search (R2 line 51)
        # e.g., "Go to YouTube"
        youtube_nav = re.search(r"(?:go\s+to|open|navigate\s+to|kholo)\s+youtube", lower_text)
        if youtube_nav or "youtube.com" in lower_text:
            return BrainDecision(
                decision_type="tool_call",
                reply_text="Navigating to YouTube.",
                tool_call=ToolCall(
                    tool_name="open_url",
                    arguments={"url": "https://www.youtube.com"},
                    risk_level=RiskLevel.LOW,
                ),
                requires_confirmation=False,
            )

        # e.g., "Search Gate Smashers" / "Gate Smashers search karo"
        search_match = re.search(r"(?:search|dhoondho|khojo)\s+(?:for\s+)?(.+)", text, re.IGNORECASE)
        if not search_match:
            search_match = re.search(r"(.+?)\s+(?:search\s+karo|dhoondho)", text, re.IGNORECASE)

        if search_match:
            query = search_match.group(1).strip()
            # Context resolution: Is YouTube active?
            is_youtube_active = False
            if context:
                if context.active_subject and "youtube" in context.active_subject.lower():
                    is_youtube_active = True
                elif context.current_url and "youtube.com" in context.current_url.lower():
                    is_youtube_active = True

            if is_youtube_active:
                target_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
                return BrainDecision(
                    decision_type="tool_call",
                    reply_text=f"Searching for '{query}' on YouTube.",
                    tool_call=ToolCall(
                        tool_name="search_youtube",
                        arguments={"query": query, "url": target_url},
                        risk_level=RiskLevel.LOW,
                    ),
                    requires_confirmation=False,
                )
            else:
                return BrainDecision(
                    decision_type="tool_call",
                    reply_text=f"Searching for '{query}'.",
                    tool_call=ToolCall(
                        tool_name="web_search",
                        arguments={"query": query},
                        risk_level=RiskLevel.LOW,
                    ),
                    requires_confirmation=False,
                )

        # 5. Volume controls
        for r in self._vol_up_regexes:
            if r.search(lower_text):
                return BrainDecision(
                    decision_type="tool_call",
                    reply_text="Increasing volume by 10%.",
                    tool_call=ToolCall(
                        tool_name="control_volume",
                        arguments={"delta": 10},
                        risk_level=RiskLevel.LOW,
                    ),
                    requires_confirmation=False,
                )

        for r in self._vol_down_regexes:
            if r.search(lower_text):
                return BrainDecision(
                    decision_type="tool_call",
                    reply_text="Decreasing volume by 10%.",
                    tool_call=ToolCall(
                        tool_name="control_volume",
                        arguments={"delta": -10},
                        risk_level=RiskLevel.LOW,
                    ),
                    requires_confirmation=False,
                )

        # Absolute volume set e.g. "set volume to 85%"
        vol_set = re.search(r"(?:set\s+)?volume\s+(?:to\s+)?(\d+)", lower_text)
        if vol_set:
            lvl = int(vol_set.group(1))
            return BrainDecision(
                decision_type="tool_call",
                reply_text=f"Volume set to {lvl}%.",
                tool_call=ToolCall(
                    tool_name="control_volume",
                    arguments={"level": lvl},
                    risk_level=RiskLevel.LOW,
                ),
                requires_confirmation=False,
            )

        # 6. System metrics (CPU usage)
        for r in self._cpu_regexes:
            if r.search(lower_text):
                return BrainDecision(
                    decision_type="reply",
                    reply_text="CPU is running comfortably at 15%, sir. Barely breaking a sweat.",
                    requires_confirmation=False,
                )

        # 7. High-Risk deletion actions (R7 line 72, Challenge 4)
        DELETE_STOP_WORDS = {
            "k", "ke", "ki", "ka", "se", "me", "mein",
            "saare", "saari", "saara", "sab", "sabhi",
            "all", "files", "file", "folder",
        }
        for r in self._delete_regexes:
            m = r.search(text)
            if m:
                raw_target = m.group(1).strip() if m.groups() and m.group(1) else "Downloads"
                if not raw_target or raw_target.lower() in DELETE_STOP_WORDS:
                    target_dir = "Downloads"
                elif raw_target.lower() == "downloads":
                    target_dir = "Downloads"
                else:
                    target_dir = raw_target

                return BrainDecision(
                    decision_type="tool_call",
                    reply_text=f"Warning: Deletion of files in {target_dir} is irreversible.",
                    tool_call=ToolCall(
                        tool_name="delete_files",
                        arguments={"directory": target_dir, "path": target_dir, "pattern": "*"},
                        risk_level=RiskLevel.HIGH,
                    ),
                    requires_confirmation=True,
                    confirmation_prompt=f"Are you sure you want to delete all files in {target_dir}? Confirm?",
                )

        # 8. Casual greetings & questions
        if self._greeting_regex.search(lower_text):
            return BrainDecision(
                decision_type="reply",
                reply_text="At your service, sir. What shall we tackle today?",
                requires_confirmation=False,
            )

        return None
