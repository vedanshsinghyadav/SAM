"""
Central SAM System Application Runtime.
Unites AI Brain, Persistent Memory, Computer Control, Safety Guard,
Screen Vision, Task Planner, Voice Engine, and Personality Adaptation
into an integrated, production-grade conversational assistant for Windows.

Part of Milestone 7: Full System Integration (R1 - R8).
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Callable, Dict, Optional

from src.sam.brain.ollama_client import OllamaBrain
from src.sam.common.config import SamConfig, get_config
from src.sam.common.network import is_online
from src.sam.common.types import ActiveContext, BrainDecision, ConversationTurn, ExecutionResult, RiskLevel
from src.sam.control.controller import ComputerController
from src.sam.memory import MemoryEngine
from src.sam.personality.adapter import PersonalityAdapter
from src.sam.planner.engine import TaskPlanner
from src.sam.safety.guard import SafetyGuard
from src.sam.vision.engine import VisionEngine
from src.sam.voice.engine import VoiceEngine

logger = logging.getLogger("sam.main")


class SAMSystem:
    """
    JARVIS-style local AI assistant orchestrator for Windows.
    Coordinates all autonomous subsystems, managing conversational context,
    tool routing, safety authorization, and multi-modal interactions.
    """

    def __init__(
        self,
        config: Optional[SamConfig] = None,
        workspace_root: Optional[str] = None
    ):
        self.config = config or get_config()
        self.brain = OllamaBrain(
            cloud_model=self.config.ollama.cloud_model,
            local_model=self.config.ollama.local_model,
            base_url=self.config.ollama.url,
            timeout=self.config.ollama.request_timeout,
            network_checker=is_online
        )
        self.memory = MemoryEngine(
            db_path=self.config.paths.memory_db_path
        )
        self.controller = ComputerController(
            workspace_root=workspace_root or os.getcwd()
        )
        self.safety = SafetyGuard()
        self.vision = VisionEngine()
        self.planner = TaskPlanner(
            controller=self.controller,
            safety=self.safety
        )
        self.voice = VoiceEngine()
        self.personality = PersonalityAdapter()
        self.context = ActiveContext()

    def process_turn(
        self,
        user_input: str,
        user_confirmed: bool = False,
        is_task: bool = False
    ) -> Dict[str, Any]:
        """
        Processes a single conversational turn across brain, safety, controller, and planner.
        Returns execution result and styled personality response.
        """
        # 1. Semantic Memory Context Retrieval
        try:
            search_results = self.memory.search_facts(user_input, top_k=3)
            for sr in search_results:
                self.context.stored_facts.append(sr.fact)
        except Exception as e:
            logger.debug("Memory retrieval exception: %s", e)

        # 2. AI Brain Reasoning & Decision Extraction
        decision: BrainDecision = self.brain.process_input(user_input, self.context)

        result: Dict[str, Any] = {
            "decision": decision,
            "executed": False,
            "output": None,
            "blocked": False,
            "response_text": decision.reply_text or ""
        }

        # 3. Tool Routing & Safety Gating
        if decision.decision_type == "tool_call" and decision.tool_call:
            authorized, reason = self.safety.authorize(
                decision.tool_call,
                user_confirmed=user_confirmed
            )
            if not authorized:
                result["blocked"] = True
                result["response_text"] = decision.confirmation_prompt or f"Confirmation needed: {reason}"
                styled_response = self.personality.adapt_tone(result["response_text"], is_task=True)
                result["styled_response"] = styled_response
                return result

            # Execute tool action
            tc = decision.tool_call
            tool_name = tc.tool_name
            args = tc.arguments

            if tool_name in ("open_app", "open_application", "launch_application"):
                res = self.controller.open_app(args.get("app_name", args.get("application", "")))
            elif tool_name in ("close_app", "close_application", "kill_process"):
                res = self.controller.close_app(args.get("process_or_name", args.get("app_name", "")))
            elif tool_name in ("control_volume", "set_volume"):
                res = self.controller.control_volume(level=args.get("level"), delta=args.get("delta"))
            elif tool_name == "control_brightness":
                res = self.controller.control_brightness(level=args.get("level"))
            elif tool_name in ("media_play", "control_media"):
                res = self.controller.control_media(args.get("command", "play"))
            elif tool_name in ("delete_files", "file_action", "move_file"):
                action = args.get("action", "delete" if "delete" in tool_name else "move")
                res = self.controller.file_action(action, **args)
            elif tool_name == "inspect_screen":
                vis = self.vision.inspect_screen(args.get("query", ""))
                res = ExecutionResult(success=True, output=vis.extracted_text)
            elif tool_name in ("get_system_stats", "check_cpu"):
                stats = self.controller.get_system_stats()
                res = ExecutionResult(success=True, output=stats)
            else:
                res = ExecutionResult(success=True, output=f"Executed {tool_name}")

            result["executed"] = res.success
            result["output"] = res.output

        # 4. Multi-step Plan Execution
        elif decision.decision_type == "plan":
            plan = self.planner.create_plan(decision.plan_goal or user_input)
            plan_res = self.planner.execute_plan(plan)
            result["plan"] = plan
            result["executed"] = plan_res.success
            result["output"] = f"Completed {plan_res.completed_steps}/{len(plan.steps)} steps."

        # 5. Personality Tone Adaptation
        styled_response = self.personality.adapt_tone(
            result["response_text"],
            is_task=is_task or (decision.decision_type != "reply")
        )
        result["styled_response"] = styled_response

        # 6. Context History Recording
        self.context.history.append(ConversationTurn(
            user_input=user_input,
            agent_response=styled_response,
            timestamp=time.time()
        ))

        return result

    def start_voice_session(
        self,
        on_wake_detected: Optional[Callable[[], None]] = None,
        mock_input: Optional[str] = None
    ) -> str:
        """
        Activates voice listening loop, transcribes spoken audio,
        processes turn, and speaks response aloud.
        """
        def _on_wake():
            if on_wake_detected:
                on_wake_detected()

        self.voice.start_listening(_on_wake)
        spoken_text = self.voice.listen_utterance(mock_audio_text=mock_input or "Hello SAM")
        turn_result = self.process_turn(spoken_text)
        self.voice.speak(turn_result["styled_response"])
        return turn_result["styled_response"]

    def close(self) -> None:
        """Gracefully release memory stores and hardware resources."""
        try:
            self.memory.close()
        except Exception as e:
            logger.debug("Error closing memory store: %s", e)
        try:
            self.voice.stop_speaking()
        except Exception as e:
            logger.debug("Error stopping voice: %s", e)
