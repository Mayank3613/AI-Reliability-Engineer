"""
Gemini Client — Layer 4.
Shared wrapper around Google Generative AI SDK for all AIRE agents.
Handles model initialization, safety settings, retry logic, and token tracking.
"""

import os
import time
import logging
import json
from typing import Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

logger = logging.getLogger(__name__)

# ── Safety settings (Layer 9 — applied via this client) ──────────────────────
AIRE_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}

AIRE_GENERATION_CONFIG = genai.types.GenerationConfig(
    temperature=0.2,       # Low temp for reliability analysis — consistent outputs
    top_p=0.95,
    top_k=40,
    max_output_tokens=4096,
)

AGENT_GENERATION_CONFIG = genai.types.GenerationConfig(
    temperature=0.1,       # Very low for structured JSON outputs
    max_output_tokens=8192,
    response_mime_type="application/json",  # Force JSON output for agent responses
)


class GeminiClient:
    """
    Thread-safe Gemini client for AIRE agents.
    Includes retry logic, token tracking, and safety enforcement.
    """

    def __init__(
        self,
        model_name: str = "gemini-1.5-pro",
        system_instruction: str = "",
        force_json: bool = False,
        max_retries: int = 3,
        api_key: str | None = None,
    ):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY not set")

        genai.configure(api_key=api_key)

        gen_config = AGENT_GENERATION_CONFIG if force_json else AIRE_GENERATION_CONFIG

        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction,
            safety_settings=AIRE_SAFETY_SETTINGS,
            generation_config=gen_config,
        )
        self.model_name = model_name
        self.max_retries = max_retries
        self._total_tokens = 0
        self._total_calls = 0
        self._error_count = 0
        logger.info("GeminiClient initialized: model=%s json=%s", model_name, force_json)

    def generate(self, prompt: str, context: str = "") -> str:
        """
        Generate text from a prompt with retry logic.
        Returns the text response string.
        """
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                start = time.monotonic()
                response = self.model.generate_content(full_prompt)
                latency_ms = (time.monotonic() - start) * 1000

                tokens = response.usage_metadata
                used = (tokens.prompt_token_count or 0) + (tokens.candidates_token_count or 0)
                self._total_tokens += used
                self._total_calls += 1

                logger.debug(
                    "Gemini call: tokens=%d latency=%.0fms attempt=%d",
                    used, latency_ms, attempt,
                )
                return response.text

            except ResourceExhausted as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning("Rate limited (attempt %d/%d) — waiting %ds", attempt, self.max_retries, wait)
                time.sleep(wait)

            except ServiceUnavailable as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning("Service unavailable (attempt %d/%d) — waiting %ds", attempt, self.max_retries, wait)
                time.sleep(wait)

            except Exception as e:
                self._error_count += 1
                logger.error("Gemini generate error: %s", e)
                raise

        self._error_count += 1
        raise RuntimeError(f"Gemini call failed after {self.max_retries} attempts: {last_error}")

    def generate_json(self, prompt: str, schema_hint: str = "", context: str = "") -> dict:
        """
        Generate and parse a JSON response.
        Uses schema_hint to guide the model's output structure.
        """
        json_prompt = prompt
        if schema_hint:
            json_prompt = f"{prompt}\n\nRespond ONLY with valid JSON matching this schema:\n{schema_hint}"

        raw = self.generate(json_prompt, context)

        # Strip markdown fences if model wraps in ```json
        clean = raw.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
        if clean.endswith("```"):
            clean = clean[: clean.rfind("```")]
        clean = clean.strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s\nRaw response:\n%s", e, raw[:500])
            raise ValueError(f"Model returned invalid JSON: {e}") from e

    def chat(self, messages: list[dict]) -> str:
        """
        Multi-turn chat interface.
        messages = [{"role": "user"|"model", "parts": [str]}]
        """
        history = [
            genai.types.ContentDict(role=m["role"], parts=[m["parts"]])
            for m in messages[:-1]
        ]
        chat_session = self.model.start_chat(history=history)
        response = chat_session.send_message(messages[-1]["parts"])
        self._total_calls += 1
        return response.text

    @property
    def stats(self) -> dict:
        return {
            "model": self.model_name,
            "total_tokens": self._total_tokens,
            "total_calls": self._total_calls,
            "error_count": self._error_count,
            "error_rate": round(self._error_count / max(1, self._total_calls), 4),
        }