"""
Multi-turn ActiveContext Tracker and Context Chaining Engine for SAM.
Part of Milestone 1: FEAT-BRAIN-002.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from src.sam.common.types import ActiveContext, CompatibleBaseModel, ConversationTurn


class ChainingResolution(CompatibleBaseModel):
    resolved: bool = False
    inferred_app: Optional[str] = None
    inferred_url: Optional[str] = None
    inferred_subject: Optional[str] = None
    inferred_action: Optional[str] = None
    search_query: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ContextTracker:
    """
    Manages active session context across multi-turn interactions.
    Provides context chaining, pronoun resolution, and sliding window pruning.
    """

    KNOWN_BROWSERS: Set[str] = {"chrome", "google chrome", "msedge", "edge", "firefox", "brave"}

    URL_SHORTCUTS: Dict[str, str] = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "reddit": "https://www.reddit.com",
        "wikipedia": "https://www.wikipedia.org",
    }

    def __init__(self, initial_context: Optional[ActiveContext] = None, max_history_turns: int = 20) -> None:
        self.context: ActiveContext = initial_context or ActiveContext()
        self.max_history_turns: int = max_history_turns
        self.last_interaction_timestamp: float = time.time()

    def add_turn(self, user_input: str, agent_response: str, timestamp: Optional[float] = None) -> None:
        """Add a conversation turn and apply sliding window limit."""
        ts = timestamp if timestamp is not None else time.time()
        turn = ConversationTurn(
            user_input=user_input.strip(),
            agent_response=agent_response.strip(),
            timestamp=ts
        )
        self.context.history.append(turn)
        if len(self.context.history) > self.max_history_turns:
            self.context.history = self.context.history[-self.max_history_turns:]
        self.last_interaction_timestamp = ts

    def set_active_app(self, app_name: Optional[str]) -> None:
        """Set the active application, normalizing common names."""
        old_app = self.context.active_app

        if app_name is None:
            self.context.active_app = None
            self.context.current_url = None
            return

        normalized = app_name.strip().lower()
        if normalized in ("google chrome", "chrome"):
            normalized = "chrome"
        elif normalized in ("msedge", "edge", "microsoft edge"):
            normalized = "edge"
        else:
            normalized = normalized

        self.context.active_app = normalized

        # Reset active URL if switching to a different application or non-browser
        if old_app != normalized or normalized not in self.KNOWN_BROWSERS:
            self.context.current_url = None

    def set_current_url(self, url: Optional[str]) -> None:
        """Set the active browser URL. Auto-sets active_app to chrome if unset."""
        self.context.current_url = url
        if url and (not self.context.active_app or self.context.active_app not in self.KNOWN_BROWSERS):
            self.context.active_app = "chrome"

    def set_active_task(self, task: Optional[str]) -> None:
        """Set or clear active multi-step task identifier."""
        self.context.active_task = task

    def set_active_subject(self, subject: Optional[str]) -> None:
        """Set active entity/subject (e.g., search target, selected file)."""
        self.context.active_subject = subject

    def clear_context(self, keep_history: bool = True) -> None:
        """Reset contextual slots while optionally retaining conversation turns."""
        self.context.active_app = None
        self.context.current_url = None
        self.context.active_task = None
        self.context.active_subject = None
        if not keep_history:
            self.context.history.clear()

    def resolve_chaining(self, user_input: str) -> ChainingResolution:
        """
        Resolves context chaining for multi-step instructions without repeated state.
        Handles:
          - 'Go to YouTube' -> navigates active_app (Chrome) to youtube.com
          - 'Search Gate Smashers' -> executes YouTube search if current_url is YouTube
          - 'Close it' -> closes active app
          - 'Move it to COA' -> moves active subject
        """
        text = user_input.strip()
        lower_text = text.lower()
        resolution = ChainingResolution()

        # 1. Navigation Chaining ("Go to X", "Open X", "Navigate to X")
        nav_match = re.search(r"^(?:go to|navigate to|open)\s+([a-zA-Z0-9\.\-]+)$", lower_text)
        if nav_match:
            target = nav_match.group(1).lower()
            if target in self.URL_SHORTCUTS or "." in target:
                url = self.URL_SHORTCUTS.get(target, f"https://{target}")
                resolution.resolved = True
                resolution.inferred_action = "navigate_url"
                resolution.inferred_app = self.context.active_app or "chrome"
                resolution.inferred_url = url
                resolution.inferred_subject = target
                resolution.parameters = {"app": resolution.inferred_app, "url": url}
                return resolution

        # 2. In-App / In-Site Search Chaining ("Search X", "Find X")
        search_match = re.search(r"^(?:search(?:\s+for)?|find)\s+(.+)$", text, re.IGNORECASE)
        if search_match:
            query = search_match.group(1).strip()
            # If current app is browser and current_url is YouTube:
            if self.context.active_app in self.KNOWN_BROWSERS and self.context.current_url:
                if "youtube.com" in self.context.current_url:
                    resolution.resolved = True
                    resolution.inferred_action = "search_youtube"
                    resolution.inferred_app = self.context.active_app
                    resolution.inferred_url = self.context.current_url
                    resolution.inferred_subject = query
                    resolution.search_query = query
                    resolution.parameters = {
                        "app": self.context.active_app,
                        "site": "youtube.com",
                        "query": query,
                        "search_url": f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
                    }
                    return resolution
                else:
                    # General web search in active browser
                    resolution.resolved = True
                    resolution.inferred_action = "search_web"
                    resolution.inferred_app = self.context.active_app
                    resolution.inferred_subject = query
                    resolution.search_query = query
                    resolution.parameters = {
                        "app": self.context.active_app,
                        "query": query,
                        "search_url": f"https://www.google.com/search?q={query.replace(' ', '+')}"
                    }
                    return resolution

        # 3. Pronoun Resolution ("close it", "move it to ...")
        pronoun_match = re.search(r"\b(it|that|this)\b", lower_text)
        if pronoun_match:
            if any(k in lower_text for k in ("close", "terminate", "kill", "exit", "minimize")):
                if self.context.active_app:
                    resolution.resolved = True
                    resolution.inferred_action = "close_app"
                    resolution.inferred_app = self.context.active_app
                    resolution.parameters = {"app_name": self.context.active_app}
                    return resolution
            elif any(k in lower_text for k in ("move", "copy", "delete", "rename")):
                if self.context.active_subject:
                    resolution.resolved = True
                    resolution.inferred_action = "file_action"
                    resolution.inferred_subject = self.context.active_subject
                    resolution.parameters = {"target_file": self.context.active_subject}
                    return resolution

        return resolution

    def update_from_decision(
        self,
        decision_type: str,
        tool_name: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None
    ) -> None:
        """Updates internal state following brain/planner decision execution."""
        if not tool_name or not args:
            return

        tool = tool_name.lower()
        if tool == "open_app":
            app = args.get("app_name")
            if app:
                self.set_active_app(app)
        elif tool == "close_app":
            closed = args.get("app_name") or args.get("process_or_name")
            if closed and self.context.active_app and closed.lower() in self.context.active_app.lower():
                self.context.active_app = None
                self.context.current_url = None
        elif tool in ("navigate_browser", "open_url", "browser_navigate"):
            url = args.get("url")
            if url:
                self.set_current_url(url)
        elif tool in ("search_youtube", "youtube_search", "search_web"):
            query = args.get("query")
            if query:
                self.set_active_subject(query)
                self.set_active_task("search")
        elif tool == "move_file":
            self.set_active_task(None)

    def format_for_prompt(self) -> str:
        """Serializes current context into a formatted block for LLM prompt injection."""
        lines = [
            "### Current Session Active Context:",
            f"- Active Application: {self.context.active_app or 'None'}",
            f"- Current URL: {self.context.current_url or 'None'}",
            f"- Active Task: {self.context.active_task or 'None'}",
            f"- Active Subject: {self.context.active_subject or 'None'}",
        ]
        if self.context.history:
            lines.append("- Recent Turns:")
            for turn in self.context.history[-5:]:
                lines.append(f"  * User: {turn.user_input}")
                lines.append(f"    SAM: {turn.agent_response}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dictionary."""
        return self.context.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any], max_history_turns: int = 20) -> ContextTracker:
        """Deserialize context from dictionary."""
        active_ctx = ActiveContext.from_dict(data)
        return cls(initial_context=active_ctx, max_history_turns=max_history_turns)
