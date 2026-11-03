"""
Automa Multi-Agent Content Intelligence & Publishing System.
Exposes specialized agents and pipeline orchestrator.
"""

from automa.agents.base import BaseAgent, AgentExecutionLog
from automa.agents.discovery import ResearchDiscoveryAgent
from automa.agents.verification import SourceVerificationAgent
from automa.agents.ranking import TopicRankingAgent, ScoringWeights
from automa.agents.simplification import ResearchSimplificationAgent
from automa.agents.strategist import ContentStrategistAgent
from automa.agents.copywriter import PlatformCopywritingAgent
from automa.agents.orchestrator import ContentIntelligencePipeline

__all__ = [
    "BaseAgent",
    "AgentExecutionLog",
    "ResearchDiscoveryAgent",
    "SourceVerificationAgent",
    "TopicRankingAgent",
    "ScoringWeights",
    "ResearchSimplificationAgent",
    "ContentStrategistAgent",
    "PlatformCopywritingAgent",
    "ContentIntelligencePipeline",
]
