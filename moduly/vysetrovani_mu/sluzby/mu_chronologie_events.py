from datetime import date

from moduly.vysetrovani_mu.constants import SOURCE_TYPE_ACCIDENT


def build_system_chronologie_events(
    *,
    started_at: date | None = None,
    source_type: str = "",
    source_id: int | None = None,
    oznameni_datum: date | None = None,
    oznameni_cas: str = "",
) -> list[dict]:
    events: list[dict] = []

    if started_at is not None:
        events.append(
            {
                "id": "system:investigation_started",
                "datum": started_at.isoformat(),
                "cas": "",
                "typ": "Šetření",
                "popis": "Šetření mimořádné události zahájeno.",
                "source": "system",
            }
        )

    if source_type == SOURCE_TYPE_ACCIDENT and isinstance(source_id, int) and source_id > 0:
        accident_event = _accident_chronologie_event(source_id)
        if accident_event is not None:
            events.append(accident_event)

    if oznameni_datum is not None:
        events.append(
            {
                "id": "system:oznameni",
                "datum": oznameni_datum.isoformat(),
                "cas": (oznameni_cas or "").strip(),
                "typ": "Oznámení",
                "popis": "Událost oznámena.",
                "source": "system",
            }
        )

    return events


def _accident_chronologie_event(source_id: int) -> dict | None:
    from moduly.vysetrovani_mu.sluzby.mu_source_context import _normalize_time_text
    from moduly.kniha_urazu.sluzby.accident_service import accident_service

    accident = accident_service.get_by_id(source_id)
    if accident is None or accident.accident_date is None:
        return None

    return {
        "id": "system:accident_event",
        "datum": accident.accident_date.isoformat(),
        "cas": _normalize_time_text(accident.accident_time),
        "typ": "Událost",
        "popis": "Vznik události podle zdrojového záznamu.",
        "source": "system",
    }
