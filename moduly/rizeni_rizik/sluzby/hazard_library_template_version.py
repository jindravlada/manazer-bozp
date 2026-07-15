"""Zvýšení revize odborného obsahu zdroje rizika (R17b, R18g.0, R18g.1).

Revize se zvyšuje pouze explicitně:
- jednou po ukončení editační relace v editoru zdroje,
- jednou po dokončení hromadné operace (import, převzetí návrhů AI, …).
"""


def bump_template_content_version(
    template_id: int,
    *,
    change_reason: str | None = None,
) -> None:
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_REVISION_REASON_MANUAL
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )

    reason = change_reason or HAZARD_LIBRARY_REVISION_REASON_MANUAL
    hazard_library_template_service.bump_content_version(
        template_id,
        change_reason=reason,
    )
