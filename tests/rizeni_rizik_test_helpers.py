"""Pomocné funkce pro testy modulu Řízení rizik."""

from __future__ import annotations

from moduly.nastaveni.modely.exposed_group import ExposedGroup
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service


def ensure_exposed_group(name: str) -> ExposedGroup:
    matches = exposed_group_service.find_matches(name, include_inactive=True)
    if matches:
        return matches[0]
    return exposed_group_service.create_group(name=name)
