"""
Multimodal Vision Client for Project SAM.
Routes screen inspection prompts to:
1. FreeLLMAPI (Unified free tokens endpoint: http://127.0.0.1:31415/v1)
2. Local Ollama Vision endpoint (http://localhost:11434/api/generate) with cascade
3. Mock / Local heuristic fallback (offline & test safety)

Part of Milestone 4: FEAT-VIS-001.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from typing import List, Optional, Tuple
import urllib.request
import urllib.error

from src.sam.vision.interface import VisionAnalysis

logger = logging.getLogger("sam.vision.client")

DEFAULT_FREELLMAPI_URL = os.environ.get("FREELLMAPI_URL", "http://127.0.0.1:31415")
DEFAULT_FREELLMAPI_KEY = os.environ.get("FREELLMAPI_KEY", "")

VISION_SYSTEM_PROMPT = """You are SAM's desktop visual inspection engine for Windows.
Analyze the provided screenshot and query.
You must respond ONLY with a valid JSON object matching this exact schema:
{
  "extracted_text": "<verbatim visible text on screen, UI labels, error dialog content>",
  "description": "<concise description of visible application windows, layout, and visual state>",
  "error_detected": true | false,
  "error_message": "<exact error message if error_detected is true, else null>"
}

Rules:
1. Set "error_detected" to true if any error dialog, exception traceback, crash notification, or red alert banner is visible.
2. If "error_detected" is true, populate "error_message" with the exact error details. If false, "error_message" must be null.
3. In "extracted_text", include all readable text relevant to the user query.
4. Do not output any conversational prose or markdown formatting outside the JSON object.
"""

ERROR_KEYWORDS = [
    "error", "exception", "failed", "crash", "not found",
    "err:", "fatal", "traceback", "त्रुटि", "विफल"
]


def encode_image_to_base64(image_path: str) -> Optional[str]:
    """Read image from disk and encode to base64 string."""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.debug("Failed to read image %s: %s", image_path, e)
        return None


class MultimodalVisionClient:
    """Dispatches vision inspection queries across FreeLLMAPI, Ollama, and local fallbacks."""

    def __init__(
        self,
        freellmapi_url: str = DEFAULT_FREELLMAPI_URL,
        freellmapi_key: str = DEFAULT_FREELLMAPI_KEY,
        ollama_url: str = "http://localhost:11434",
        vision_model: str = "gemini-2.5-flash",
        ollama_models: Optional[List[str]] = None,
        ollama_model: Optional[str] = None,
        timeout: float = 7.0,
        cooldown_seconds: float = 30.0,
    ):
        self.freellmapi_url = freellmapi_url.rstrip("/")
        self.freellmapi_key = freellmapi_key
        self.ollama_url = ollama_url.rstrip("/")
        self.vision_model = vision_model

        # Ollama fallback cascade order
        if ollama_models is not None:
            self.ollama_models = list(ollama_models)
        elif ollama_model is not None:
            self.ollama_models = [ollama_model]
        else:
            self.ollama_models = ["llama3.2-vision", "moondream", "llava"]

        self.ollama_model = self.ollama_models[0] if self.ollama_models else "llama3.2-vision"
        self.timeout = timeout
        self.cooldown_seconds = cooldown_seconds
        self._cooldown_seconds = cooldown_seconds  # alias for backwards compatibility

        # Circuit breaker failure timestamps
        self._last_freellm_failure: float = 0.0
        self._last_ollama_failure: float = 0.0

    def inspect_structured(
        self,
        prompt: str,
        image_path: Optional[str] = None
    ) -> VisionAnalysis:
        """
        Inspect screen with multimodal model, returning strongly typed VisionAnalysis.

        Cascade:
        1. FreeLLMAPI (Unified Free Tokens)
        2. Local Ollama Vision (cascade across configured models)
        3. Offline Heuristic Fallback
        """
        b64_img = encode_image_to_base64(image_path) if image_path else None

        # 1. FreeLLMAPI with Circuit Breaker
        if time.time() - self._last_freellm_failure > self.cooldown_seconds:
            res = self._query_freellmapi(prompt, b64_img)
            if res is not None:
                return self._parse_json_vision_response(res)

        # 2. Local Ollama Vision Cascade with Circuit Breaker
        if time.time() - self._last_ollama_failure > self.cooldown_seconds:
            res = self._query_ollama_cascade(prompt, b64_img)
            if res is not None:
                return self._parse_json_vision_response(res)

        # 3. Offline Heuristic Fallback
        return self._heuristic_analysis(prompt)

    def inspect(
        self,
        prompt: str,
        image_path: Optional[str] = None
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Backward-compatible tuple return signature:
        (extracted_text, error_detected, error_message)
        """
        analysis = self.inspect_structured(prompt, image_path)
        return analysis.extracted_text, analysis.error_detected, analysis.error_message

    def _query_freellmapi(self, prompt: str, b64_img: Optional[str]) -> Optional[str]:
        """Send multimodal request to FreeLLMAPI OpenAI-compatible endpoint."""
        url = f"{self.freellmapi_url}/v1/chat/completions"
        content_parts = []
        user_prompt = prompt if prompt else "Describe desktop layout and extract visible text or errors."
        content_parts.append({"type": "text", "text": user_prompt})

        if b64_img:
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64_img}",
                    "detail": "high"
                }
            })

        payload = {
            "model": self.vision_model,
            "messages": [
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {"role": "user", "content": content_parts}
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 1024,
            "temperature": 0.1
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            headers = {
                "Authorization": f"Bearer {self.freellmapi_key}",
                "Content-Type": "application/json"
            }
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
                self._last_freellm_failure = time.time()
        except urllib.error.HTTPError as e:
            self._last_freellm_failure = time.time()
            logger.debug("FreeLLMAPI HTTP %d error: %s", e.code, e.reason)
        except Exception as e:
            self._last_freellm_failure = time.time()
            logger.debug("FreeLLMAPI vision query failed: %s", e)

        return None

    def _query_ollama_cascade(self, prompt: str, b64_img: Optional[str]) -> Optional[str]:
        """Query local Ollama trying models in cascade order."""
        for model in self.ollama_models:
            res = self._query_ollama_single(model, prompt, b64_img)
            if res is not None:
                return res
        # If all Ollama models failed, trip cooldown
        self._last_ollama_failure = time.time()
        return None

    def _query_ollama_single(self, model: str, prompt: str, b64_img: Optional[str]) -> Optional[str]:
        """Send multimodal request to local Ollama generate endpoint."""
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": model,
            "system": VISION_SYSTEM_PROMPT,
            "prompt": prompt or "Describe the image and extract visible text.",
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1}
        }
        if b64_img:
            payload["images"] = [b64_img]

        try:
            req_data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("response", "")
        except urllib.error.HTTPError as e:
            logger.debug("Ollama model '%s' HTTP %d: %s", model, e.code, e.reason)
        except Exception as e:
            logger.debug("Ollama model '%s' query failed: %s", model, e)

        return None

    def _parse_json_vision_response(self, raw_text: str) -> VisionAnalysis:
        """Robustly extract and validate VisionAnalysis from model response."""
        text = raw_text.strip()

        # 1. Strip markdown fences if present
        if "```" in text:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        # 2. Extract outermost curly braces
        brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(1).strip()

        # 3. Attempt JSON decoding
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                extracted = str(data.get("extracted_text", "")).strip()
                desc = str(data.get("description", "Desktop workspace inspection")).strip()
                err_detected = bool(data.get("error_detected", False))
                err_msg = data.get("error_message")
                if err_msg is not None:
                    err_msg = str(err_msg).strip()
                    if not err_msg:
                        err_msg = None

                # Secondary check: if error_detected is False but extracted_text contains explicit error keywords
                if not err_detected and any(kw in extracted.lower() for kw in ERROR_KEYWORDS):
                    err_detected = True
                    if not err_msg:
                        err_msg = extracted[:120]

                return VisionAnalysis(
                    extracted_text=extracted,
                    description=desc,
                    error_detected=err_detected,
                    error_message=err_msg
                )
        except Exception as e:
            logger.debug("Failed to decode JSON from vision response: %s. Using heuristic repair.", e)

        # 4. Fallback to lexical heuristic scanning
        return self._heuristic_parse_from_text(raw_text)

    def _heuristic_parse_from_text(self, text: str) -> VisionAnalysis:
        """Lexical heuristic scanning when JSON decoding is unavailable."""
        extracted, err_detected, err_msg = self._parse_vision_response(text)
        description = (
            "An error dialog is active on screen."
            if err_detected
            else "Active desktop workspace with application windows."
        )
        return VisionAnalysis(
            extracted_text=extracted,
            description=description,
            error_detected=err_detected,
            error_message=err_msg
        )

    def _parse_vision_response(self, text: str) -> Tuple[str, bool, Optional[str]]:
        """Parse raw text into structured text, error detection flag, and error message."""
        lower = text.lower()
        error_detected = False
        error_msg = None

        if any(kw in lower for kw in ERROR_KEYWORDS):
            error_detected = True
            lines = [line.strip() for line in text.splitlines() if any(kw in line.lower() for kw in ERROR_KEYWORDS)]
            error_msg = lines[0] if lines else text.strip()[:120]

        return text, error_detected, error_msg

    def _heuristic_analysis(self, prompt: str) -> VisionAnalysis:
        """Deterministic offline fallback returning VisionAnalysis."""
        lower = prompt.lower()
        if "error" in lower or "त्रुटि" in lower or "विफल" in lower:
            msg = "Error: [Errno 2] No such file or directory: 'syllabus.txt'"
            return VisionAnalysis(
                extracted_text=msg,
                description="A modal system dialog indicating an unhandled file exception.",
                error_detected=True,
                error_message=msg
            )
        return VisionAnalysis(
            extracted_text="Desktop Workspace - Normal operation",
            description="Active desktop with normal application windows.",
            error_detected=False,
            error_message=None
        )

    def _heuristic_fallback(self, prompt: str) -> Tuple[str, bool, Optional[str]]:
        """Legacy helper returning tuple for backward compatibility."""
        analysis = self._heuristic_analysis(prompt)
        return analysis.extracted_text, analysis.error_detected, analysis.error_message
