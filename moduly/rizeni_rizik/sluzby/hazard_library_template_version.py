"""Automatické zvýšení verze vzoru při změně obsahu (R17b)."""


def bump_template_content_version(template_id: int) -> None:
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )

    hazard_library_template_service.bump_content_version(template_id)
