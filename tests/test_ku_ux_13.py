"""KU-UX-13 – souhrnné úkoly pro ohlašovací povinnosti pracovního úrazu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="ku-ux-13-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import ENTITY_ACCIDENT
    from core.shared.task_source_display import task_source_short_label
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        OBLIGATION_EZOP,
        OBLIGATION_OIP_OBU_ZASLANI,
        OBLIGATION_OO_OHLASENI,
        OBLIGATION_OO_PREDANI,
        OBLIGATION_VYHOTOVENI_ZAZNAMU,
        OBLIGATION_ZAMESTNANEC_PREDANI,
        OBLIGATION_ZP_ZASLANI,
        SECTION_OHLASENI,
        SECTION_ZAZNAM,
        add_workdays,
        obligation_default_deadline,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_task_service import (
        OHLASENI_TASK_TITLE_PREFIX,
        ZAZNAM_TASK_TITLE_PREFIX,
        accident_reporting_task_service,
        is_accident_reporting_task_title,
        ohlaseni_task_title,
        zaznam_task_title,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.ukoly.sluzby.task_service import task_service


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"


class KuUx13ReportingTasksTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.kniha_urazu.modely.accident import Accident
        from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

    def _open_tasks(self, accident_id: int, *, prefix: str):
        return [
            task
            for task in task_service.get_all_tasks()
            if task.source_module == ENTITY_ACCIDENT
            and task.source_record_id == accident_id
            and not task.completed
            and not task.canceled
            and (task.title or "").startswith(prefix)
        ]

    def test_create_up_to_3_creates_only_ohlaseni_summary_task(self) -> None:
        accident_date = date(2026, 7, 27)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            accident = accident_service.create_accident(
                jmeno_prijmeni="Ohlášení 13",
                accident_date=accident_date,
                druh_urazu=KIND_UP_TO_3,
                dpn_od=accident_date,
            )

        ohlaseni = self._open_tasks(accident.id, prefix=OHLASENI_TASK_TITLE_PREFIX)
        zaznam = self._open_tasks(accident.id, prefix=ZAZNAM_TASK_TITLE_PREFIX)
        self.assertEqual(len(ohlaseni), 1)
        self.assertEqual(len(zaznam), 0)
        self.assertEqual(ohlaseni[0].title, ohlaseni_task_title(accident.number))
        self.assertEqual(
            ohlaseni[0].due_date,
            obligation_default_deadline(accident_date, section=SECTION_OHLASENI),
        )
        self.assertEqual(task_source_short_label(ohlaseni[0]), "Úraz")
        self.assertIn("Odborová organizace", ohlaseni[0].description)

    def test_create_over_3_creates_ohlaseni_and_zaznam_summary_tasks(self) -> None:
        accident_date = date(2026, 7, 27)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            accident = accident_service.create_accident(
                jmeno_prijmeni="Záznam 13",
                accident_date=accident_date,
                druh_urazu=KIND_OVER_3,
                dpn_od=accident_date,
                dpn_do=accident_date + timedelta(days=10),
            )

        ohlaseni = self._open_tasks(accident.id, prefix=OHLASENI_TASK_TITLE_PREFIX)
        zaznam = self._open_tasks(accident.id, prefix=ZAZNAM_TASK_TITLE_PREFIX)
        self.assertEqual(len(ohlaseni), 1)
        self.assertEqual(len(zaznam), 1)
        self.assertEqual(zaznam[0].title, zaznam_task_title(accident.number))
        self.assertEqual(
            zaznam[0].due_date,
            obligation_default_deadline(accident_date, section=SECTION_ZAZNAM),
        )
        self.assertEqual(
            zaznam[0].due_date,
            add_workdays(accident_date, 15),
        )
        for label_part in (
            "Vyhotovení Záznamu",
            "OIP / OBÚ",
            "EZOP",
            "Postižený zaměstnanec",
            "Odborová organizace",
        ):
            self.assertIn(label_part, zaznam[0].description)

    def test_no_duplicate_summary_tasks_on_resync(self) -> None:
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            accident = accident_service.create_accident(
                jmeno_prijmeni="Bez duplicit",
                accident_date=date.today(),
                druh_urazu=KIND_OVER_3,
                dpn_od=date.today(),
                dpn_do=date.today() + timedelta(days=9),
            )
            accident_reporting_task_service.sync_for_accident(accident)
            accident_reporting_task_service.sync_for_accident(accident)

        self.assertEqual(
            len(self._open_tasks(accident.id, prefix=OHLASENI_TASK_TITLE_PREFIX)),
            1,
        )
        self.assertEqual(
            len(self._open_tasks(accident.id, prefix=ZAZNAM_TASK_TITLE_PREFIX)),
            1,
        )

    def test_ohlaseni_completes_only_when_all_done(self) -> None:
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            accident = accident_service.create_accident(
                jmeno_prijmeni="Dokončení ohlášení",
                accident_date=date.today(),
                druh_urazu=KIND_UP_TO_3,
                dpn_od=date.today(),
            )
            self.assertEqual(
                len(self._open_tasks(accident.id, prefix=OHLASENI_TASK_TITLE_PREFIX)),
                1,
            )

            accident_reporting_task_service.sync_for_accident(
                accident,
                saved_data={
                    "admin_ohlaseni": [
                        {"key": OBLIGATION_OO_OHLASENI, "nazev": "OO", "datum": ""}
                    ],
                    "admin_zaslani": [],
                },
            )
            self.assertEqual(
                len(self._open_tasks(accident.id, prefix=OHLASENI_TASK_TITLE_PREFIX)),
                1,
            )

            accident_reporting_task_service.sync_for_accident(
                accident,
                saved_data={
                    "admin_ohlaseni": [
                        {
                            "key": OBLIGATION_OO_OHLASENI,
                            "nazev": "OO",
                            "datum": date.today().isoformat(),
                        }
                    ],
                    "admin_zaslani": [],
                },
            )
            self.assertEqual(
                len(self._open_tasks(accident.id, prefix=OHLASENI_TASK_TITLE_PREFIX)),
                0,
            )

    def test_zaznam_stays_open_until_all_record_items_done(self) -> None:
        accident_date = date.today()
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            accident = accident_service.create_accident(
                jmeno_prijmeni="Částečný záznam",
                accident_date=accident_date,
                druh_urazu=KIND_OVER_3,
                dpn_od=accident_date,
                dpn_do=accident_date + timedelta(days=10),
            )
            partial = {
                "admin_ohlaseni": [
                    {
                        "key": OBLIGATION_OO_OHLASENI,
                        "datum": accident_date.isoformat(),
                    }
                ],
                "admin_zaslani": [
                    {"key": OBLIGATION_VYHOTOVENI_ZAZNAMU, "datum": accident_date.isoformat()},
                    {"key": OBLIGATION_OIP_OBU_ZASLANI, "datum": accident_date.isoformat()},
                    {"key": OBLIGATION_ZP_ZASLANI, "datum": accident_date.isoformat()},
                    {"key": OBLIGATION_EZOP, "datum": accident_date.isoformat()},
                    {"key": OBLIGATION_ZAMESTNANEC_PREDANI, "datum": ""},
                    {"key": OBLIGATION_OO_PREDANI, "datum": accident_date.isoformat()},
                ],
            }
            accident_reporting_task_service.sync_for_accident(accident, saved_data=partial)
            self.assertEqual(
                len(self._open_tasks(accident.id, prefix=ZAZNAM_TASK_TITLE_PREFIX)),
                1,
            )

            partial["admin_zaslani"][-2]["datum"] = accident_date.isoformat()
            accident_reporting_task_service.sync_for_accident(accident, saved_data=partial)
            self.assertEqual(
                len(self._open_tasks(accident.id, prefix=ZAZNAM_TASK_TITLE_PREFIX)),
                0,
            )
            self.assertEqual(
                len(self._open_tasks(accident.id, prefix=OHLASENI_TASK_TITLE_PREFIX)),
                0,
            )

    def test_removing_record_obligations_completes_zaznam_task(self) -> None:
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            accident = accident_service.create_accident(
                jmeno_prijmeni="Změna druhu",
                accident_date=date.today(),
                druh_urazu=KIND_OVER_3,
                dpn_od=date.today(),
                dpn_do=date.today() + timedelta(days=8),
            )
            self.assertEqual(
                len(self._open_tasks(accident.id, prefix=ZAZNAM_TASK_TITLE_PREFIX)),
                1,
            )
            accident_service.update_accident(
                accident.id,
                druh_urazu=KIND_UP_TO_3,
                dpn_od=date.today(),
                dpn_do=date.today() + timedelta(days=1),
            )
            self.assertEqual(
                len(self._open_tasks(accident.id, prefix=ZAZNAM_TASK_TITLE_PREFIX)),
                0,
            )
            self.assertEqual(
                len(self._open_tasks(accident.id, prefix=OHLASENI_TASK_TITLE_PREFIX)),
                1,
            )

    def test_reporting_title_helpers(self) -> None:
        self.assertTrue(is_accident_reporting_task_title(ohlaseni_task_title("6/2026")))
        self.assertTrue(is_accident_reporting_task_title(zaznam_task_title("6/2026")))
        self.assertFalse(is_accident_reporting_task_title("Ověřit druh pracovního úrazu č. 6/2026"))


if __name__ == "__main__":
    unittest.main()
