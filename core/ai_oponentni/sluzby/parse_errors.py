"""Výjimky parsování odpovědí AI oponentury."""


class AiPeerReviewParseError(ValueError):
    """Chyba strukturované JSON odpovědi, která vypadá jako naše schéma."""
