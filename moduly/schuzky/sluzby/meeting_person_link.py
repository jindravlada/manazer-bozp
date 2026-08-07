"""Zpětná kompatibilita – logika je ve sdíleném person_thp_link."""

from moduly.nastaveni.sluzby.person_thp_link import (  # noqa: F401
    ensure_person_for_thp_worker,
    find_person_matching_thp,
    find_thp_worker_for_person,
    person_list_label,
)
