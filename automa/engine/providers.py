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

        # Topic-aware content synthesis
        if "idempotent" in prompt_lower or "webhook" in prompt_lower:
            if "platform: linkedin" in prompt_lower:
                return (
                    "In distributed systems, networks guarantee at-least-once delivery, not exactly-once.\n\n"
                    "If your webhook receiver assumes every payload arrives once, duplicate processing is guaranteed. "
                    "Upstream network retries from Stripe, GitHub, or Shopify will regularly send identical payloads within milliseconds.\n\n"
                    "Many teams reach for distributed Redis locks, but a cleaner, zero-dependency pattern is storage-level deduplication:\n\n"
                    "1. Maintain an idempotency table recording `(provider, event_id, created_at)`.\n"
                    "2. Add a database-level unique constraint on `(provider, event_id)`.\n"
                    "3. Insert atomically before processing business logic.\n\n"
                    "Concurrent duplicate deliveries will fail fast at the storage boundary with a unique constraint violation, "
                    "completely eliminating side-effects without distributed locks.\n\n"
                    "#DistributedSystems #BackendEngineering #SoftwareArchitecture"
                )
            elif "platform: x" in prompt_lower:
                return (
                    "Networks guarantee at-least-once delivery, not exactly-once.\n\n"
                    "Don't build complex distributed locks to prevent duplicate webhooks. A database unique constraint on (provider, event_id) fails duplicates fast at the storage boundary."
                )

        elif "sqlite" in prompt_lower or "wal" in prompt_lower:
            if "platform: linkedin" in prompt_lower:
                return (
                    "SQLite handles concurrent workloads far better than most developers realize.\n\n"
                    "The common complaint 'database table is locked' is almost always caused by running in default journal mode. "
                    "With three simple configuration pragmas, SQLite becomes exceptionally resilient for internal tools and edge workloads:\n\n"
                    "1. `PRAGMA journal_mode = WAL;` (Write-Ahead Logging: readers never block writers, writers never block readers)\n"
                    "2. `PRAGMA busy_timeout = 5000;` (Wait up to 5 seconds for write locks rather than failing immediately)\n"
                    "3. `PRAGMA synchronous = NORMAL;` (Reduces disk sync calls with virtually zero durability loss)\n\n"
                    "For moderate write workloads and high read throughput, embedded SQLite eliminates multi-thousand dollar cloud database bills while delivering sub-millisecond latencies.\n\n"
                    "#SQLite #DatabaseDesign #Python #PerformanceOptimization"
                )
            elif "platform: x" in prompt_lower:
                return (
                    "Most developers don't need a $200/mo cloud Postgres instance for internal tools.\n\n"
                    "SQLite in WAL mode (`PRAGMA journal_mode = WAL;`) allows concurrent readers while a writer commits. Sub-millisecond queries on a single file."
                )

        elif "jitter" in prompt_lower or "backoff" in prompt_lower:
            if "platform: linkedin" in prompt_lower:
                return (
                    "Why unjittered exponential backoff crashes recovering systems:\n\n"
                    "When an API experiences a temporary outage, hundreds of failed clients back off at the exact same intervals (1s, 2s, 4s, 8s). "
                    "The moment the service begins to recover, every client retries at the exact same millisecond. This creates a 'thundering herd' spike that immediately knocks the API back down.\n\n"
                    "The fix is 'Full Jitter':\n"
                    "Instead of sleeping for `base * 2^attempt`, sleep for `random(0, min(max_delay, base * 2^attempt))`.\n\n"
                    "Spreading the retry wave uniformly across time allows recovering backends to drain queues without recurring contention spikes.\n\n"
                    "#DistributedSystems #ReliabilityEngineering #CloudArchitecture"
                )
            elif "platform: x" in prompt_lower:
                return (
                    "Unjittered exponential backoff is a trap.\n\n"
                    "If 1,000 clients fail simultaneously, they will all retry at the exact same second and knock the recovering service back down.\n\n"
                    "Always add Full Jitter: randomize sleep between 0 and your backoff delay."
                )

        elif "lighthouse" in prompt_lower or "assistive" in prompt_lower:
            if "platform: linkedin" in prompt_lower:
                return (
                    "Most computer vision systems stop at generating bounding boxes on a screen. For visually impaired users, a bounding box on a display is useless—low latency and actionable audio are what matter.\n\n"
                    "In Project Lighthouse, we set out to build an assistive ecosystem that converts physical surroundings into conversational audio cues in real time.\n\n"
                    "Here is how the architecture is wired:\n\n"
                    "1. Cloud Training Pipeline:\n"
                    "We trained custom YOLOv8 models on AWS (SageMaker + S3) targeting real-world obstacle classes: doorways, walkway hazards, curbs, and everyday personal objects.\n\n"
                    "2. Edge Quantization:\n"
                    "Cloud API roundtrips introduce too much latency for navigation. We quantized the trained weights into ONNX / TFLite formats for native on-device inference inside Flutter.\n\n"
                    "3. Distance & Dialogue Layer:\n"
                    "Detection alone does not prevent collisions. We paired classification with monocular depth estimation to calculate relative physical distance, feeding the output directly into a local Text-to-Speech (TTS) engine.\n\n"
                    "The core engineering lesson: The bottleneck in assistive edge AI is rarely raw model accuracy—it is balancing inference frame rates with audio queue pacing so the user is not overwhelmed with auditory clutter.\n\n"
                    "Open-source codebase: https://github.com/The-ml-guy/Project_Lighthouse\n\n"
                    "#MachineLearning #EdgeAI #ComputerVision"
                )
            elif "platform: x" in prompt_lower:
                return (
                    "Turning bounding boxes into low-latency spatial audio is the real edge AI challenge.\n\n"
                    "Project Lighthouse pairs AWS-trained YOLOv8 with on-device ONNX quantization, monocular depth estimation, and Flutter TTS for accessibility.\n\n"
                    "https://github.com/The-ml-guy/Project_Lighthouse"
                )

        elif "100projects" in prompt_lower or "algorithms" in prompt_lower:
            if "platform: linkedin" in prompt_lower:
                return (
                    "High-level libraries make it easy to call .fit() and .predict() without ever understanding the underlying optimization mechanics.\n\n"
                    "To stay sharp on foundational mathematics and algorithmic trade-offs, I have been building out '100projects'—a repository of 100+ modular, self-contained Python scripts covering core machine learning techniques from the ground up:\n\n"
                    "1. Supervised foundations: Ordinary least squares, gradient descent variants, decision tree splits, and ensemble boosting.\n"
                    "2. Unsupervised mechanics: Vector quantization in K-Means, density clustering with DBSCAN, and dimensionality reduction via PCA.\n"
                    "3. Implementation focus: Minimal external dependencies, readable linear algebra, and reproducible code.\n\n"
                    "Writing algorithms without relying on black-box wrappers forces you to confront vectorization bottlenecks, numerical stability edge cases, and matrix shape mismatches head-on.\n\n"
                    "Explore the implementations:\n"
                    "https://github.com/The-ml-guy/100projects\n\n"
                    "#Python #MachineLearning #DataScience"
                )
            elif "platform: x" in prompt_lower:
                return (
                    "Calling .fit() and .predict() hides how ML algorithms actually work under the hood.\n\n"
                    "I built '100projects'—100+ modular Python scripts implementing core ML techniques from scratch (gradient descent, trees, PCA, clustering) with zero bloat.\n\n"
                    "https://github.com/The-ml-guy/100projects"
                )

        # Dynamic synthesis for any discovered topic or open-source repository
        topic_match = ""
        context_match = ""
        for line in prompt.split("\n"):
            line_s = line.strip()
            if line_s.upper().startswith("TOPIC:"):
                topic_match = line_s.split(":", 1)[1].strip()
            elif line_s.upper().startswith("VERIFIED KNOWLEDGE") or line_s.upper().startswith("CONTEXT:"):
                context_match = line_s.split(":", 1)[1].strip()

        if topic_match:
            clean_topic = topic_match.replace("GitHub Repo: ", "")
            if "platform: linkedin" in prompt_lower:
                summary = context_match[:160] if context_match else "Modular engineering design with clean separation of concerns."
                return (
                    f"Exploring modern open-source architectures: {clean_topic}.\n\n"
                    f"Building reliable software in AI and distributed systems comes down to reducing runtime friction. "
                    f"{clean_topic} provides a focused, high-leverage approach to this problem:\n\n"
                    f"1. Core Architecture: {summary}\n"
                    f"2. Performance Profile: Eliminates runtime bloat by keeping execution paths deterministic and testable.\n"
                    f"3. Practical Adoption: Integrates cleanly into existing production pipelines without heavy overhead.\n\n"
                    f"What architectural trade-offs do you prioritize when evaluating similar open-source tooling in production?\n\n"
                    f"#OpenSource #MachineLearning #SoftwareEngineering"
                )
            elif "platform: x" in prompt_lower:
                return (
                    f"Deep-dive into {clean_topic}: solving core engineering bottlenecks with clean, modular architecture.\n\n"
                    f"A great example of avoiding framework bloat by focusing on execution speed and determinism.\n\n"
                    f"#OpenSource #AI"
                )
            elif "platform: instagram" in prompt_lower:
                return (
                    f"Engineering Spotlight: {clean_topic}\n\n"
                    f"A closer look at how modern open-source projects approach high-efficiency systems architecture.\n\n"
                    f"Key takeaways:\n"
                    f"- Focused, clean execution without runtime bloat\n"
                    f"- Testable design patterns for production environments\n"
                    f"- High performance with minimal external dependencies\n\n"
                    f"#SoftwareEngineering #TechInnovation #OpenSource"
                )

        # Default Cron topic
        if "platform: linkedin" in prompt_lower:
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
        else:
            return (
                "Cron is a scheduler, not an orchestrator.\n\n"
                "If your batch task takes longer than the interval, cron will spawn a duplicate worker and corrupt your data.\n\n"
                "Use an atomic state machine with advisory locking instead. Simple, local, and resilient."
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
