"""Repository Státního dozoru."""

from moduly.statni_dozor.repository.state_supervision_repository import (
    StateSupervisionRepository,
)
from moduly.statni_dozor.repository.state_supervision_required_document_repository import (
    StateSupervisionRequiredDocumentRepository,
)

__all__ = [
    "StateSupervisionRepository",
    "StateSupervisionRequiredDocumentRepository",
]
