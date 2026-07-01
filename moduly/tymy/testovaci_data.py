"""Testovací data pro modul Týmy."""

from datetime import date

from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.tymy.sluzby.team_service import team_service


def create_demo_workers() -> dict[str, int]:
    workers = {
        "bozp": settings_service.save_worker(
            first_name="Jan",
            last_name="Novák",
            position="Specialista BOZP",
        ),
        "vedouci_vyroby": settings_service.save_worker(
            first_name="Petr",
            last_name="Svoboda",
            position="Vedoucí výroby",
        ),
        "zastupce": settings_service.save_worker(
            first_name="Marie",
            last_name="Dvořáková",
            position="Zástupce zaměstnanců",
        ),
        "technik_udrzby": settings_service.save_worker(
            first_name="Tomáš",
            last_name="Malý",
            position="Technik údržby",
        ),
        "vedouci_zamestnanec": settings_service.save_worker(
            first_name="Lucie",
            last_name="Horáková",
            position="Vedoucí zaměstnanec",
        ),
        "technik": settings_service.save_worker(
            first_name="Martin",
            last_name="Černý",
            position="Technik",
        ),
        "revizni_technik": settings_service.save_worker(
            first_name="Josef",
            last_name="Vlček",
            position="Revizní technik",
        ),
    }
    return {key: worker.id for key, worker in workers.items()}


def seed_demo_teams() -> list[int]:
    worker_ids = create_demo_workers()

    prov_team = team_service.create_team_from_dict(
        {
            "name": "Výrobní prověrková komise",
            "description": "Prověrková komise pro výrobní provoz.",
            "team_type_id": "proverkova_komise",
            "active": True,
            "valid_from": date.today().isoformat(),
            "members": [
                {
                    "role_id": "vedouci_tymu",
                    "thp_worker_id": worker_ids["bozp"],
                    "mandatory": True,
                    "display_order": 10,
                },
                {
                    "role_id": "clen",
                    "thp_worker_id": worker_ids["vedouci_vyroby"],
                    "mandatory": True,
                    "display_order": 20,
                },
                {
                    "role_id": "clen",
                    "thp_worker_id": worker_ids["zastupce"],
                    "mandatory": False,
                    "display_order": 30,
                },
                {
                    "role_id": "prizvany_odbornik",
                    "thp_worker_id": worker_ids["technik_udrzby"],
                    "mandatory": False,
                    "display_order": 40,
                },
            ],
        }
    )

    investigation_team = team_service.create_team_from_dict(
        {
            "name": "Vyšetřovací tým PÚ",
            "description": "Tým pro šetření pracovních úrazů.",
            "team_type_id": "vysetrovaci_tym",
            "active": True,
            "valid_from": date.today().isoformat(),
            "members": [
                {
                    "role_id": "vedouci_tymu",
                    "thp_worker_id": worker_ids["bozp"],
                    "mandatory": True,
                    "display_order": 10,
                },
                {
                    "role_id": "clen",
                    "thp_worker_id": worker_ids["vedouci_zamestnanec"],
                    "mandatory": True,
                    "display_order": 20,
                },
                {
                    "role_id": "clen",
                    "thp_worker_id": worker_ids["technik"],
                    "mandatory": False,
                    "display_order": 30,
                },
                {
                    "role_id": "prizvany_odbornik",
                    "thp_worker_id": worker_ids["revizni_technik"],
                    "mandatory": False,
                    "display_order": 40,
                },
            ],
        }
    )

    return [prov_team.team.id, investigation_team.team.id]
