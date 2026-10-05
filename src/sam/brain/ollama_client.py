"""
Hybrid Cloud/Local Ollama Client Reasoning Engine for Project SAM.
Implements IBrain protocol with automatic offline failover, resilient mock execution,
and robust JSON decision extraction.
Part of Milestone 1: FEAT-BRAIN-004.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable, Dict, Optional
import httpx
from pydantic import ValidationError

from src.sam.brain.interface import IBrain
from src.sam.brain.intent import MultilingualIntentParser
from src.sam.brain.context import ContextTracker
from src.sam.common.types import ActiveContext, BrainDecision, RiskLevel, ToolCall

logger = logging.getLogger("sam.brain.ollama")


class OllamaBrain(IBrain):
    """Hybrid cloud/local Ollama reasoning engine conforming to IBrain."""

    SYSTEM_PROMPT = """You are SAM, a JARVIS-style local AI assistant for Windows.
You accept instructions in English, Hindi, and Hinglish.

You must respond ONLY with a single JSON object conforming to this schema:
{
  "decision_type": "reply" | "tool_call" | "plan",
  "reply_text": "<natural voice/text response>",
  "tool_call": {
    "tool_name": "<tool_name>",
    "arguments": { ... },
    "risk_level": "LOW" | "MEDIUM" | "HIGH"
  } | null,
  "plan_goal": "<goal string if plan>" | null,
  "requires_confirmation": boolean,
  "confirmation_prompt": "<string if requires_confirmation is true>" | null
}

IMPORTANT:
- Open apps (Chrome, Spotify), web searches, volume controls are LOW risk.
- Move files, close apps are MEDIUM risk.
- Delete files, execute unknown scripts are HIGH risk (requires_confirmation=true).
- Multi-step requests are decision_type="plan".
- Do not output any markdown code blocks or explanations outside the JSON.
"""

    def __init__(
        self,
        cloud_model: str = "gemma4:cloud",
        local_model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0,
        mock_mode: bool = False,
        network_checker: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.cloud_model = cloud_model
        self.local_model = local_model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.mock_mode = mock_mode or (os.environ.get("SAM_MOCK_BRAIN", "0") == "1")
        self._network_checker = network_checker
        self.intent_parser = MultilingualIntentParser()
        self._active_model = self.cloud_model

    def is_online(self) -> bool:
        """Determine connectivity status via injected checker or TCP probe."""
        if self._network_checker is not None:
            return self._network_checker()
        try:
            from src.sam.common.network import is_online
            return is_online()
        except ImportError:
            import socket
            try:
                with socket.create_connection(("8.8.8.8", 53), timeout=0.5):
                    return True
            except OSError:
                return False

    def get_current_model(self) -> str:
        """Return the currently selected model identifier."""
        if not self.is_online():
            return self.local_model
        return self._active_model

    def process_input(self, user_text: str, context: ActiveContext) -> BrainDecision:
        """Process user query and return structured decision."""
        online = self.is_online()
        offline_fallback_occurred = not online

        if not online:
            self._active_model = self.local_model
            logger.info("Operating offline. Selected local model: %s", self.local_model)
        else:
            self._active_model = self.cloud_model

        # 1. Mock mode path
        if self.mock_mode:
            decision = self._mock_process(user_text, context)
            if offline_fallback_occurred:
                decision.is_offline_fallback = True
                notice = f"[Notice: Offline mode active. Offline mode activated. Running local {self.local_model}] "
                decision.reply_text = notice + (decision.reply_text or "")
            return decision

        # 2. Attempt LLM generation
        try:
            raw_response = self._call_ollama(user_text, context, self._active_model)
            decision = self._parse_json_decision(raw_response)
        except Exception as primary_err:
            logger.warning("Primary generation failed on model %s: %s", self._active_model, primary_err)

            # If primary was cloud, attempt auto-failover to local
            if self._active_model == self.cloud_model:
                try:
                    logger.info("Attempting automatic failover to local model %s", self.local_model)
                    self._active_model = self.local_model
                    offline_fallback_occurred = True
                    raw_response = self._call_ollama(user_text, context, self.local_model)
                    decision = self._parse_json_decision(raw_response)
                except Exception as local_err:
                    logger.warning("Local model generation also failed: %s. Using resilient fallback.", local_err)
                    decision = self._mock_process(user_text, context)
            else:
                # Local also failed (daemon offline)
                decision = self._mock_process(user_text, context)

        # 3. Acceptance Criteria: Prepend notification if offline failover occurred
        if offline_fallback_occurred:
            decision.is_offline_fallback = True
            notice = f"[Notice: Offline mode active. Offline mode activated. Running local {self.local_model}] "
            if decision.reply_text:
                decision.reply_text = notice + decision.reply_text
            else:
                decision.reply_text = notice

        decision.model_used = self._active_model
        return decision

    def _call_ollama(self, user_text: str, context: ActiveContext, model_name: str) -> str:
        """Execute HTTP request against Ollama REST endpoint."""
        prompt = self._build_prompt(user_text, context)
        payload = {
            "model": model_name,
            "prompt": prompt,
            "system": self.SYSTEM_PROMPT,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.2},
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")

    def _build_prompt(self, user_text: str, context: ActiveContext) -> str:
        """Compose context-aware prompt payload."""
        lines = [
            f"Active App: {context.active_app or 'None'}",
            f"Current URL: {context.current_url or 'None'}",
            f"Active Task: {context.active_task or 'None'}",
            f"Active Subject: {context.active_subject or 'None'}",
            "Recent Turns:",
        ]
        for turn in context.history[-3:]:
            lines.append(f"User: {turn.user_input}")
            lines.append(f"SAM: {turn.agent_response}")
        lines.append(f"\nUser Command: {user_text}")
        return "\n".join(lines)

    def _parse_json_decision(self, raw_text: str) -> BrainDecision:
        """Extract and validate BrainDecision from LLM completion string."""
        text = raw_text.strip()
        # Strip markdown fences if present
        if "```" in text:
            fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if fence_match:
                text = fence_match.group(1).strip()

        # Find outermost braces
        brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(1).strip()

        try:
            data = json.loads(text)
            return BrainDecision.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning("Failed to validate JSON from LLM: %s. Using heuristic repair.", e)
            return self._mock_process(raw_text, ActiveContext())

    def _resolve_context_chaining(self, user_text: str, context: Optional[ActiveContext]) -> Optional[BrainDecision]:
        """Hook ContextTracker chaining and pronoun resolution into the brain pipeline."""
        if not context:
            return None

        tracker = ContextTracker(initial_context=context)
        res = tracker.resolve_chaining(user_text)
        if not res.resolved:
            return None

        if res.inferred_action == "close_app":
            app = res.inferred_app or res.parameters.get("app_name") or "active application"
            return BrainDecision(
                decision_type="tool_call",
                reply_text=f"Closing {app}, sir.",
                tool_call=ToolCall(
                    tool_name="close_app",
                    arguments={"app_name": app},
                    risk_level=RiskLevel.MEDIUM,
                ),
                requires_confirmation=False,
            )
        elif res.inferred_action == "file_action":
            target = res.inferred_subject or res.parameters.get("target_file")
            return BrainDecision(
                decision_type="tool_call",
                reply_text=f"Processing file action for {target}.",
                tool_call=ToolCall(
                    tool_name="file_action",
                    arguments=res.parameters,
                    risk_level=RiskLevel.MEDIUM,
                ),
                requires_confirmation=False,
            )
        elif res.inferred_action == "navigate_url":
            url = res.inferred_url or res.parameters.get("url")
            # Do not intercept desktop apps if shortcut was triggered
            if res.inferred_subject in ("spotify", "chrome", "notepad", "calculator"):
                return None
            return BrainDecision(
                decision_type="tool_call",
                reply_text=f"Navigating to {url}.",
                tool_call=ToolCall(
                    tool_name="open_url",
                    arguments={"url": url},
                    risk_level=RiskLevel.LOW,
                ),
                requires_confirmation=False,
            )
        return None

    def _mock_process(self, user_text: str, context: ActiveContext) -> BrainDecision:
        """Resilient fallback and unit test simulation engine."""
        # 1. Resolve context chaining & pronoun anaphora before delegating to intent parser
        chained = self._resolve_context_chaining(user_text, context)
        if chained is not None:
            return chained

        # 2. Heuristic lexical & contextual parsing
        parsed = self.intent_parser.parse(user_text, context)
        if parsed is not None:
            return parsed

        # Default conversational reply if no heuristic matched
        return BrainDecision(
            decision_type="reply",
            reply_text=f"Understood: '{user_text}'. How else may I assist you, sir?",
            requires_confirmation=False,
        )
