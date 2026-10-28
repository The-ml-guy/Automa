"""
Base Publisher Interface and Data Structures for Automa.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field
from automa.db.repository import PostRecord


class PublishResult(BaseModel):
    success: bool
    external_post_id: Optional[str] = None
    is_transient_error: bool = False
    error_message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class BasePublisher(ABC):
    @abstractmethod
    def publish(self, post: PostRecord) -> PublishResult:
        """Executes publication for the given post."""
        pass

    @abstractmethod
    def verify_status(self, external_id: str, platform: str) -> str:
        """Verifies publication status from upstream platform or aggregator."""
        pass
