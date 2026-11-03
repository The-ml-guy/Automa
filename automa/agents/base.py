"""
Base Agent Architecture for Automa (Multi-Agent Content Intelligence Platform).
Defines contracts, telemetry, logging, and error handling for all specialized agents.
"""

from __future__ import annotations
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("automa.agents")


class AgentExecutionLog(BaseModel):
    agent_name: str
    status: str  # "SUCCESS", "FAILED", "SKIPPED"
    duration_ms: float
    items_processed: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstract Base Class for specialized intelligent agents in Automa.
    Every agent has explicit input/output types, operational boundaries,
    and structured telemetry.
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"automa.agents.{name.lower()}")

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Core execution logic to be implemented by each specialized agent."""
        pass

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes the agent with automatic performance measurement,
        telemetry logging, and exception containment.
        """
        ctx = context or {}
        start_time = time.perf_counter()
        self.logger.info("Starting execution of Agent [%s]: %s", self.name, self.description)

        try:
            result = self.run(ctx)
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.info("Agent [%s] completed successfully in %.2fms", self.name, duration_ms)
            result["_telemetry"] = AgentExecutionLog(
                agent_name=self.name,
                status="SUCCESS",
                duration_ms=round(duration_ms, 2),
                items_processed=result.get("items_processed", 0),
                details=result.get("summary", {}),
            ).model_dump()
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error("Agent [%s] encountered failure: %s", self.name, e, exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "_telemetry": AgentExecutionLog(
                    agent_name=self.name,
                    status="FAILED",
                    duration_ms=round(duration_ms, 2),
                    error=str(e),
                ).model_dump(),
            }
