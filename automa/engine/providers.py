"""
AI Reasoning Providers for Automa (Phase 3 & 10).
Supports Google GenAI (Gemini) and deterministic Mock/Dry-Run generator.
"""

from __future__ import annotations
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional
from automa.config import get_settings

logger = logging.getLogger("automa.engine.providers")


class BaseAIProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generates text from a given prompt and system instruction."""
        pass


class GeminiProvider(BaseAIProvider):
    """Integrates with Google Gemini models via google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Failed to initialize google-genai client: %s", e)

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        if not self._client:
            raise RuntimeError(
                "GeminiProvider client is not initialized. Please set GEMINI_API_KEY in .env "
                "or enable DRY_RUN mode."
            )

        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                max_output_tokens=2048,
            )
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            logger.error("Gemini API call failed: %s", e)
            raise e


class MockProvider(BaseAIProvider):
    """
    Deterministic provider for dry-run simulation, offline testing,
    and zero-cost local execution. Synthesizes high-substance posts directly
    from verified knowledge base templates.
    """

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        prompt_lower = prompt.lower()

        # Differentiate output by platform requested in prompt
        if "platform: linkedin" in prompt_lower or "for linkedin" in prompt_lower:
            return (
                "Cron jobs are schedulers, not orchestrators. Here is why un-gated cron jobs fail in production:\n\n"
                "When a high-frequency background worker experiences a traffic spike or slow external API response, "
                "the task often exceeds its execution window. A standard cron runner will blindly spawn a second instance "
                "at the next tick. The result? Concurrent database writes, row lock contention, and duplicate processing.\n\n"
                "A resilient alternative requires three deterministic guardrails:\n"
                "1. An advisory file or database lock so overlapping executions exit immediately.\n"
                "2. An atomic state machine (`QUEUED` -> `PROCESSING` -> `COMPLETED` / `FAILED`) in SQLite or Postgres.\n"
                "3. A heartbeat timestamp to cleanly recover orphaned jobs after unexpected worker restarts.\n\n"
                "Before reaching for complex distributed orchestration frameworks, a 50-line state machine with WAL-mode "
                "SQLite solves 95% of concurrency failure modes.\n\n"
                "#SoftwareEngineering #DistributedSystems #BackendArchitecture"
            )

        elif "platform: x" in prompt_lower or "for x" in prompt_lower:
            return (
                "Cron is a scheduler, not an orchestrator.\n\n"
                "If your batch task takes longer than the interval, cron will spawn a duplicate worker and corrupt your data.\n\n"
                "Use an atomic state machine with advisory locking instead. Simple, local, and resilient."
            )

        elif "platform: instagram" in prompt_lower or "for instagram" in prompt_lower:
            return (
                "Why Cron Jobs Break Under High Load (And What To Build Instead):\n\n"
                "Swipe through the visual blueprint to see the exact state transition diagram:\n"
                "Slide 1: The Cron Overlap Trap (Concurrent worker collision)\n"
                "Slide 2: Atomic State Machine (QUEUED -> PROCESSING -> COMPLETED)\n"
                "Slide 3: Heartbeat Timeout & Recovery\n\n"
                "Building resilient background jobs doesn't require Kubernetes. A hardened SQLite database with WAL mode provides sub-millisecond local locks.\n\n"
                "#SystemDesign #BackendEngineering #DevOps #Architecture"
            )

        # General revision fallback
        return (
            "Engineering Architecture Lesson: Idempotent Consumer Design\n\n"
            "In distributed systems, networks guarantee at-least-once delivery, not exactly-once. "
            "Every consumer must maintain an idempotency table recording `(provider, event_id)` "
            "with a unique database constraint. Concurrent duplicate webhooks fail fast at the storage "
            "boundary before triggering side-effects.\n\n"
            "#SystemDesign #CloudArchitecture"
        )


def get_ai_provider() -> BaseAIProvider:
    """Returns GeminiProvider if API key is present and DRY_RUN is false; otherwise MockProvider."""
    settings = get_settings()
    if not settings.dry_run and settings.gemini_api_key:
        logger.info("Using live GeminiProvider (%s)", settings.gemini_model)
        return GeminiProvider(api_key=settings.gemini_api_key, model_name=settings.gemini_model)
    else:
        logger.info("Using deterministic MockProvider (Safe Dry-Run / Test Mode)")
        return MockProvider()
