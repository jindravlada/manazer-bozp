"""Zvýšení verze odborného obsahu zdroje rizika (R17b, R18g.0).

Verze se zvyšuje pouze explicitně:
- jednou po ukončení editační relace v editoru zdroje,
- jednou po dokončení hromadné operace (import, převzetí návrhů AI, …).
"""


def bump_template_content_version(template_id: int) -> None:
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )

    hazard_library_template_service.bump_content_version(template_id)
