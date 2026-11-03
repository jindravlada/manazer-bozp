"""Označí audit ve testovací databázi jako už připravený.

Ukládání závěru, silných stránek a doporučení je po schválené změně
dostupné až u připraveného auditu. Testy dialogu ověřují samotný zápis,
nikoli průvodce přípravou.
"""

from __future__ import annotations

from datetime import date, datetime

from core.database.session import transaction
from moduly.audity.constants import AUDIT_METHODOLOGY_GENERATION_V2
from moduly.audity.modely.audit import Audit
from moduly.audity.sluzby.audit_service import audit_service


def mark_audit_prepared(audit_id: int):
    with transaction() as session:
        row = session.get(Audit, int(audit_id))
        if row is None:
            raise AssertionError(f"Audit {audit_id} v testovací databázi chybí.")
        row.methodology_generation = AUDIT_METHODOLOGY_GENERATION_V2
        if row.questions_frozen_at is None:
            row.questions_frozen_at = datetime.now()
        if row.started_at is None:
            row.started_at = row.audit_date or date.today()
    reloaded = audit_service.get_by_id(int(audit_id))
    if reloaded is None:
        raise AssertionError(f"Audit {audit_id} po označení přípravy chybí.")
    return reloaded
