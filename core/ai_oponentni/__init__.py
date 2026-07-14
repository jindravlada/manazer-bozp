"""Obecný modul odborného oponentního posouzení s externí AI."""

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_INTRO_TEXT,
    AI_PEER_REVIEW_TAB_TITLE,
    DEFAULT_AI_PEER_REVIEW_PROMPT,
)
from core.ai_oponentni.sluzby.ai_peer_review_service import (
    AiPeerReviewError,
    ai_peer_review_service,
)

__all__ = [
    "AI_PEER_REVIEW_INTRO_TEXT",
    "AI_PEER_REVIEW_TAB_TITLE",
    "DEFAULT_AI_PEER_REVIEW_PROMPT",
    "AiPeerReviewError",
    "ai_peer_review_service",
]
