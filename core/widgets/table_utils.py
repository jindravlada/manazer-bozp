from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
)

from core.widgets.info_tooltip import set_widget_tooltip
from core.widgets.text_preview import DEFAULT_TEXT_PREVIEW_LENGTH, truncate_text_preview


def apply_cell_tooltip(item: QTableWidgetItem | None, text: str | None) -> None:
    """Elidovaný text v buňce + celý obsah v tooltipu."""
    if item is None:
        return
    full_text = text or ""
    if full_text.strip():
        set_widget_tooltip(item, full_text)
    else:
        item.setToolTip("")


def _table_cell_padding(table: QTableWidget) -> int:
    style = table.style()
    return max(
        12,
        2 * style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, None, table)
        + 2 * style.pixelMetric(QStyle.PixelMetric.PM_LayoutHorizontalSpacing, None, table)
        + 8,
    )


def _table_cell_content_width(table: QTableWidget, column: int) -> int:
    """Šířka dostupná pro text buňky (sloupec minus okraje stylu)."""
    return max(0, table.columnWidth(column) - _table_cell_padding(table))


def _column_width_to_fit_text(table: QTableWidget, text: str) -> int:
    """Minimální šířka sloupce, aby se ``text`` vešel bez elipsy."""
    text_width = table.fontMetrics().horizontalAdvance(text)
    return text_width + _table_cell_padding(table) + 16


def table_cell_text_is_elided(table: QTableWidget, row: int, column: int) -> bool:
    """True, pokud by se text buňky při ElideRight zkrátil."""
    item = table.item(row, column)
    if item is None:
        return False
    text = item.text() or ""
    if not text:
        return False
    available = _table_cell_content_width(table, column)
    metrics = table.fontMetrics()
    elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, available)
    return elided != text


def refresh_elided_cell_tooltips(
    table: QTableWidget,
    columns: tuple[int, ...] | list[int],
) -> None:
    """Nastaví tooltip s celým textem jen u sloupců, kde je text zkrácen."""
    for row in range(table.rowCount()):
        for column in columns:
            item = table.item(row, column)
            if item is None:
                continue
            full_text = item.text() or ""
            if full_text.strip() and table_cell_text_is_elided(table, row, column):
                set_widget_tooltip(item, full_text)
            else:
                item.setToolTip("")


def create_preview_table_item(
    text: str,
    *,
    max_length: int = DEFAULT_TEXT_PREVIEW_LENGTH,
) -> QTableWidgetItem:
    full_text = text or ""
    item = QTableWidgetItem(truncate_text_preview(full_text, max_length=max_length))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if full_text.strip():
        set_widget_tooltip(item, full_text)
    return item


def configure_table_columns(table: QTableWidget, profile: str) -> None:
    header = table.horizontalHeader()
    header.setStretchLastSection(False)

    if profile == "thp_workers":
        widths = {
            0: 0,
            1: 80,
            2: 170,
            3: 150,
            4: 120,
            5: 240,
            6: 130,
            7: 260,
            8: 55,
            9: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

    elif profile == "workplaces":
        widths = {
            0: 0,
            1: 360,
            2: 420,
            3: 420,
            4: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

    elif profile == "persons":
        widths = {
            0: 0,
            1: 220,
            2: 180,
            3: 180,
            4: 180,
            5: 120,
            6: 55,
            7: 90,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (1, 2, 3, 4, 5, 6, 7):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "tasks":
        from moduly.ukoly.task_display import (
            COL_DESCRIPTION,
            COL_DUE_DATE,
            COL_INDICATOR,
            COL_RESPONSIBLE,
            COL_SOURCE,
            COL_SOURCE_RECORD,
            COL_TYPE,
            COL_WORKPLACE,
        )

        widths = {
            COL_INDICATOR: 24,
            COL_DESCRIPTION: 360,
            COL_DUE_DATE: 90,
            COL_RESPONSIBLE: 180,
            COL_WORKPLACE: 160,
            COL_SOURCE: 110,
            COL_SOURCE_RECORD: 120,
            COL_TYPE: 90,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(COL_INDICATOR, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_DESCRIPTION, QHeaderView.Stretch)
        for column in (COL_DUE_DATE, COL_RESPONSIBLE, COL_WORKPLACE, COL_SOURCE, COL_SOURCE_RECORD, COL_TYPE):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "meetings":
        from moduly.schuzky.constants import (
            COL_LOCATION,
            COL_ORGANIZER,
            COL_PRIORITY,
            COL_STARTS_AT,
            COL_STATUS,
            COL_TITLE,
            COL_TYPE,
        )

        widths = {
            COL_STARTS_AT: 140,
            COL_TYPE: 130,
            COL_PRIORITY: 100,
            COL_TITLE: 260,
            COL_LOCATION: 160,
            COL_ORGANIZER: 180,
            COL_STATUS: 120,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        for column in (
            COL_STARTS_AT,
            COL_TYPE,
            COL_PRIORITY,
            COL_LOCATION,
            COL_ORGANIZER,
            COL_STATUS,
        ):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "meeting_templates":
        widths = {
            1: 260,
            2: 140,
            3: 100,
            4: 110,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "agenda":
        from moduly.agenda.constants import (
            COL_DUE,
            COL_PERSON,
            COL_SOURCE,
            COL_STATUS,
            COL_TITLE,
            COL_TYPE,
        )

        widths = {
            COL_TITLE: 280,
            COL_DUE: 140,
            COL_PERSON: 200,
            COL_STATUS: 140,
            COL_SOURCE: 120,
            COL_TYPE: 90,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        for column in (COL_DUE, COL_PERSON, COL_STATUS, COL_SOURCE, COL_TYPE):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "periodic_activities":
        from moduly.periodicke_cinnosti.constants import (
            COL_ACTIVE,
            COL_ID,
            COL_NEXT_DUE,
            COL_NOTIFY,
            COL_PERIOD,
            COL_PLACE,
            COL_RESPONSIBLE,
            COL_TITLE,
        )

        widths = {
            COL_ID: 0,
            COL_TITLE: 260,
            COL_PLACE: 180,
            COL_RESPONSIBLE: 160,
            COL_NEXT_DUE: 120,
            COL_PERIOD: 110,
            COL_NOTIFY: 140,
            COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(COL_ID, True)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        for column in (COL_PLACE, COL_RESPONSIBLE, COL_NEXT_DUE, COL_PERIOD, COL_NOTIFY, COL_ACTIVE):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "yearly_plan":
        from moduly.rocni_plan.constants import (
            COL_ID,
            COL_LINK,
            COL_NOTE,
            COL_SOURCE,
            COL_STATUS,
            COL_TITLE,
        )

        widths = {
            COL_ID: 0,
            COL_SOURCE: 150,
            COL_TITLE: 280,
            COL_STATUS: 150,
            COL_LINK: 120,
            COL_NOTE: 220,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(COL_ID, True)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        for column in (COL_SOURCE, COL_STATUS, COL_LINK, COL_NOTE):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "ozo_contracts":
        from moduly.smlouvy_ozo.constants import (
            COL_EMPLOYER,
            COL_ICO,
            COL_ID,
            COL_NUMBER,
            COL_STATUS,
            COL_VALID_FROM,
            COL_VALID_TO,
        )

        widths = {
            COL_ID: 0,
            COL_EMPLOYER: 260,
            COL_ICO: 100,
            COL_NUMBER: 130,
            COL_VALID_FROM: 110,
            COL_VALID_TO: 110,
            COL_STATUS: 120,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(COL_ID, True)
        header.setSectionResizeMode(COL_EMPLOYER, QHeaderView.Stretch)
        for column in (
            COL_ICO,
            COL_NUMBER,
            COL_VALID_FROM,
            COL_VALID_TO,
            COL_STATUS,
        ):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "mu_investigations":
        widths = {
            0: 0,    # ID
            1: 110,  # Číslo
            2: 105,  # Stav
            3: 180,  # Charakter události
            4: 220,  # Zdroj
            5: 105,  # Zahájeno
            6: 180,  # Vedoucí šetření
            7: 320,  # Název / stručný popis
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (1, 2, 3, 4, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

    elif profile == "controls":
        widths = {
            0: 0,    # ID
            1: 105,  # Datum
            2: 320,  # Kontrolní list
            3: 180,  # THP pracovník
            4: 180,  # Pracoviště
            5: 70,   # Závada
            6: 120,  # SD
            7: 220,  # Poznámka
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (1, 2, 3, 4, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

    elif profile == "internal_audits":
        widths = {
            0: 0,    # ID
            1: 90,   # Číslo
            2: 85,   # Plán
            3: 105,  # Datum auditu
            4: 180,  # Pracoviště
            5: 320,  # Název
            6: 110,  # Stav
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (1, 2, 3, 4, 6):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Stretch)

    elif profile == "audity":
        widths = {
            0: 0,    # ID
            1: 90,   # Číslo auditu
            2: 55,   # Rok
            3: 110,  # Plánovaný měsíc
            4: 220,  # Auditovaný provoz — výchozí, roztáhne se
            5: 105,  # Datum auditu
            6: 65,   # Celkem
            7: 55,   # Závady
            8: 85,   # Nedostatky
            9: 95,   # Porušení
            10: 70,  # Neshody
            11: 95,  # Pozorování
            12: 85,  # Zjištění
            13: 50,  # PKZ
            14: 90,  # Ostatní
            15: 110, # Stav
            16: 90,  # Typ auditu
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)

    elif profile == "bozp_inspections":
        widths = {
            0: 0,    # ID
            1: 90,   # Číslo
            2: 115,  # Datum prověrky
            3: 180,  # Pracoviště
            4: 65,   # Celkem
            5: 55,   # Závady
            6: 85,   # Nedostatky
            7: 95,   # Porušení
            8: 70,   # Neshody
            9: 95,   # Pozorování
            10: 85,  # Zjištění
            11: 50,  # PKZ
            12: 90,  # Ostatní
            13: 120, # Stav
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        for column in (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)

    elif profile == "bozp_coordinations":
        from moduly.koordinace_bozp.constants import (
            COL_MEETING_DATE,
            COL_NUMBER,
            COL_PBP,
            COL_PLACE,
            COL_STATUS,
            COL_SUBJECT,
            COL_VALIDITY,
        )

        # UX-COORD-4d: Název akce Stretch, krátké sloupce Interactive.
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            COL_NUMBER: 110,
            COL_MEETING_DATE: 110,
            COL_PLACE: 160,
            COL_SUBJECT: 320,
            COL_STATUS: 120,
            COL_VALIDITY: 110,
            COL_PBP: 130,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (
            COL_NUMBER,
            COL_MEETING_DATE,
            COL_PLACE,
            COL_STATUS,
            COL_VALIDITY,
            COL_PBP,
        ):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_SUBJECT, QHeaderView.Stretch)

    elif profile == "coordination_employers":
        from moduly.koordinace_bozp.constants import (
            EMP_COL_ABBREVIATION,
            EMP_COL_ACTIVE,
            EMP_COL_ICO,
            EMP_COL_IS_MAIN,
            EMP_COL_NAME,
            EMP_COL_RISK_STATUS,
        )

        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            EMP_COL_ABBREVIATION: 90,
            EMP_COL_NAME: 260,
            EMP_COL_ICO: 100,
            EMP_COL_IS_MAIN: 120,
            EMP_COL_RISK_STATUS: 150,
            EMP_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (
            EMP_COL_ABBREVIATION,
            EMP_COL_ICO,
            EMP_COL_IS_MAIN,
            EMP_COL_RISK_STATUS,
            EMP_COL_ACTIVE,
        ):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setSectionResizeMode(EMP_COL_NAME, QHeaderView.Stretch)

    elif profile == "coordination_participants":
        from moduly.koordinace_bozp.constants import (
            PART_COL_ACTIVE,
            PART_COL_EMAIL,
            PART_COL_EMPLOYER,
            PART_COL_FULL_NAME,
            PART_COL_PHONE,
            PART_COL_ROLE,
        )

        # UX-COORD-12a: Zaměstnavatel / Telefon / Aktivní krátké; jméno, role, e-mail Stretch.
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            PART_COL_EMPLOYER: 120,
            PART_COL_FULL_NAME: 200,
            PART_COL_ROLE: 180,
            PART_COL_PHONE: 120,
            PART_COL_EMAIL: 180,
            PART_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (PART_COL_EMPLOYER, PART_COL_PHONE, PART_COL_ACTIVE):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setSectionResizeMode(PART_COL_FULL_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(PART_COL_ROLE, QHeaderView.Stretch)
        header.setSectionResizeMode(PART_COL_EMAIL, QHeaderView.Stretch)

    elif profile == "coordination_workplaces":
        from moduly.koordinace_bozp.constants import (
            WP_COL_ACTIVE,
            WP_COL_NOTE,
            WP_COL_OPERATION,
            WP_COL_PART,
            WP_COL_WORKPLACE,
        )

        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            WP_COL_OPERATION: 160,
            WP_COL_WORKPLACE: 200,
            WP_COL_PART: 180,
            WP_COL_NOTE: 220,
            WP_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(WP_COL_OPERATION, QHeaderView.Interactive)
        header.setSectionResizeMode(WP_COL_ACTIVE, QHeaderView.Interactive)
        header.setSectionResizeMode(WP_COL_WORKPLACE, QHeaderView.Stretch)
        header.setSectionResizeMode(WP_COL_PART, QHeaderView.Stretch)
        header.setSectionResizeMode(WP_COL_NOTE, QHeaderView.Stretch)

    elif profile == "coordination_employer_activities":
        from moduly.koordinace_bozp.constants import (
            ACT_COL_ACTIVE,
            ACT_COL_EMPLOYER,
            ACT_COL_FROM,
            ACT_COL_NAME,
            ACT_COL_PLACE,
            ACT_COL_TO,
        )

        # UX-COORD-10: Zaměstnavatel / Od / Do / Aktivní krátké, Činnost + Místo Stretch.
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            ACT_COL_EMPLOYER: 160,
            ACT_COL_NAME: 240,
            ACT_COL_PLACE: 220,
            ACT_COL_FROM: 110,
            ACT_COL_TO: 110,
            ACT_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (
            ACT_COL_EMPLOYER,
            ACT_COL_FROM,
            ACT_COL_TO,
            ACT_COL_ACTIVE,
        ):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setSectionResizeMode(ACT_COL_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(ACT_COL_PLACE, QHeaderView.Stretch)

    elif profile == "coordination_measures":
        from moduly.koordinace_bozp.constants import (
            MSR_COL_ACTIVE,
            MSR_COL_CATEGORY,
            MSR_COL_DESCRIPTION,
            MSR_COL_TITLE,
        )

        # UX-COORD-4b/4d: Text opatření Stretch, krátké sloupce Interactive.
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            MSR_COL_CATEGORY: 140,
            MSR_COL_TITLE: 220,
            MSR_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (MSR_COL_CATEGORY, MSR_COL_TITLE, MSR_COL_ACTIVE):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setSectionResizeMode(MSR_COL_DESCRIPTION, QHeaderView.Stretch)

    elif profile == "coordination_contacts":
        from moduly.koordinace_bozp.constants import (
            CTC_COL_ACTIVE,
            CTC_COL_EMAIL,
            CTC_COL_EMPLOYER,
            CTC_COL_NAME,
            CTC_COL_PHONE,
            CTC_COL_ROLE,
            CTC_COL_TYPE,
        )

        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            CTC_COL_TYPE: 140,
            CTC_COL_EMPLOYER: 100,
            CTC_COL_NAME: 180,
            CTC_COL_ROLE: 160,
            CTC_COL_PHONE: 120,
            CTC_COL_EMAIL: 180,
            CTC_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (
            CTC_COL_TYPE,
            CTC_COL_EMPLOYER,
            CTC_COL_PHONE,
            CTC_COL_EMAIL,
            CTC_COL_ACTIVE,
        ):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setSectionResizeMode(CTC_COL_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(CTC_COL_ROLE, QHeaderView.Stretch)

    elif profile == "coordination_attachments":
        from moduly.koordinace_bozp.constants import (
            ATT_COL_ACTIVE,
            ATT_COL_DESCRIPTION,
            ATT_COL_FILENAME,
            ATT_COL_TYPE,
        )

        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            ATT_COL_FILENAME: 240,
            ATT_COL_TYPE: 140,
            ATT_COL_DESCRIPTION: 220,
            ATT_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (ATT_COL_TYPE, ATT_COL_ACTIVE):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setSectionResizeMode(ATT_COL_FILENAME, QHeaderView.Stretch)
        header.setSectionResizeMode(ATT_COL_DESCRIPTION, QHeaderView.Stretch)

    elif profile == "coordination_pbp_history":
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {0: 70, 1: 130, 2: 160, 3: 110, 4: 200}
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        for column in (0, 1, 3):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)

    elif profile == "hazard_events":
        from moduly.rizeni_rizik.constants import (
            EVENT_COL_ACTIVE,
            EVENT_COL_INVENTORY_ITEM,
            EVENT_COL_NAME,
        )

        widths = {
            EVENT_COL_NAME: 220,
            EVENT_COL_INVENTORY_ITEM: 200,
            EVENT_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(EVENT_COL_NAME, QHeaderView.Stretch)
        for column in (EVENT_COL_INVENTORY_ITEM, EVENT_COL_ACTIVE):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "hazard_inventory_item_events":
        from moduly.rizeni_rizik.constants import (
            ITEM_EVENT_COL_ACTIVE,
            ITEM_EVENT_COL_NAME,
        )

        widths = {
            ITEM_EVENT_COL_NAME: 320,
            ITEM_EVENT_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(ITEM_EVENT_COL_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(ITEM_EVENT_COL_ACTIVE, QHeaderView.Fixed)

    elif profile == "hazard_risk_assessments":
        from moduly.rizeni_rizik.constants import (
            RISK_ASSESSMENT_COL_ACTIVE,
            RISK_ASSESSMENT_COL_COMPLETED_AT,
            RISK_ASSESSMENT_COL_EVENT,
            RISK_ASSESSMENT_COL_EXPOSED_GROUP,
            RISK_ASSESSMENT_COL_INVENTORY_ITEM,
            RISK_ASSESSMENT_COL_SEVERITY,
            RISK_ASSESSMENT_COL_STATUS,
        )

        # UX-RISK-2: Aktivní pevně ~70 px. Ušetřenou šířku (dříve celý Stretch
        # na Aktivní) sdílejí rovnoměrně Ohrožené skupiny a Nežádoucí událost.
        # Ostatní sloupce, ElideRight a tooltipy beze změny.
        widths = {
            RISK_ASSESSMENT_COL_EXPOSED_GROUP: 260,
            RISK_ASSESSMENT_COL_EVENT: 340,
            RISK_ASSESSMENT_COL_INVENTORY_ITEM: 220,
            RISK_ASSESSMENT_COL_SEVERITY: 110,
            RISK_ASSESSMENT_COL_STATUS: 130,
            RISK_ASSESSMENT_COL_COMPLETED_AT: 120,
            RISK_ASSESSMENT_COL_ACTIVE: 70,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        for column in (
            RISK_ASSESSMENT_COL_INVENTORY_ITEM,
            RISK_ASSESSMENT_COL_SEVERITY,
            RISK_ASSESSMENT_COL_STATUS,
            RISK_ASSESSMENT_COL_COMPLETED_AT,
            RISK_ASSESSMENT_COL_ACTIVE,
        ):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        header.setSectionResizeMode(RISK_ASSESSMENT_COL_EXPOSED_GROUP, QHeaderView.Stretch)
        header.setSectionResizeMode(RISK_ASSESSMENT_COL_EVENT, QHeaderView.Stretch)

    elif profile == "hazard_existing_measures":
        from moduly.rizeni_rizik.constants import (
            EXISTING_MEASURE_COL_ACTIVE,
            EXISTING_MEASURE_COL_DESCRIPTION,
            EXISTING_MEASURE_COL_NOTE,
        )

        widths = {
            EXISTING_MEASURE_COL_DESCRIPTION: 260,
            EXISTING_MEASURE_COL_NOTE: 220,
            EXISTING_MEASURE_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(EXISTING_MEASURE_COL_DESCRIPTION, QHeaderView.Stretch)
        for column in (EXISTING_MEASURE_COL_NOTE, EXISTING_MEASURE_COL_ACTIVE):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "hazard_required_measures":
        from moduly.rizeni_rizik.constants import (
            REQUIRED_MEASURE_COL_ACTIVE,
            REQUIRED_MEASURE_COL_DESCRIPTION,
            REQUIRED_MEASURE_COL_TITLE,
        )

        widths = {
            REQUIRED_MEASURE_COL_TITLE: 260,
            REQUIRED_MEASURE_COL_DESCRIPTION: 220,
            REQUIRED_MEASURE_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(REQUIRED_MEASURE_COL_TITLE, QHeaderView.Stretch)
        for column in (REQUIRED_MEASURE_COL_DESCRIPTION, REQUIRED_MEASURE_COL_ACTIVE):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "hazard_identification_photos":
        from moduly.rizeni_rizik.constants import (
            PHOTO_COL_ACTIVE,
            PHOTO_COL_CAPTION,
            PHOTO_COL_SIZE,
            PHOTO_COL_TAKEN_AT,
            PHOTO_COL_THUMBNAIL,
        )

        widths = {
            PHOTO_COL_THUMBNAIL: 110,
            PHOTO_COL_CAPTION: 220,
            PHOTO_COL_TAKEN_AT: 120,
            PHOTO_COL_SIZE: 90,
            PHOTO_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(PHOTO_COL_CAPTION, QHeaderView.Stretch)
        for column in (
            PHOTO_COL_THUMBNAIL,
            PHOTO_COL_TAKEN_AT,
            PHOTO_COL_SIZE,
            PHOTO_COL_ACTIVE,
        ):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "ai_peer_reviews":
        from core.ai_oponentni.constants import (
            AI_PEER_REVIEW_COL_ACCEPTED,
            AI_PEER_REVIEW_COL_EXPORT_DATE,
            AI_PEER_REVIEW_COL_FILENAME,
            AI_PEER_REVIEW_COL_ID,
            AI_PEER_REVIEW_COL_LOADED,
            AI_PEER_REVIEW_COL_MODEL,
            AI_PEER_REVIEW_COL_PENDING,
            AI_PEER_REVIEW_COL_REJECTED,
            AI_PEER_REVIEW_COL_RESPONSE_DATE,
            AI_PEER_REVIEW_COL_UNASSIGNED,
        )

        widths = {
            AI_PEER_REVIEW_COL_EXPORT_DATE: 132,
            AI_PEER_REVIEW_COL_RESPONSE_DATE: 156,
            AI_PEER_REVIEW_COL_MODEL: 128,
            AI_PEER_REVIEW_COL_LOADED: 88,
            AI_PEER_REVIEW_COL_PENDING: 96,
            AI_PEER_REVIEW_COL_ACCEPTED: 88,
            AI_PEER_REVIEW_COL_REJECTED: 88,
            AI_PEER_REVIEW_COL_UNASSIGNED: 92,
            AI_PEER_REVIEW_COL_FILENAME: 280,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(AI_PEER_REVIEW_COL_ID, True)
        header.setSectionResizeMode(AI_PEER_REVIEW_COL_ID, QHeaderView.Fixed)
        header.setSectionResizeMode(AI_PEER_REVIEW_COL_FILENAME, QHeaderView.Stretch)
        for column in widths:
            if column != AI_PEER_REVIEW_COL_FILENAME:
                header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "ai_peer_review_proposals":
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        for column in (0, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)

    elif profile == "hazard_inventory_items":
        from moduly.rizeni_rizik.constants import (
            INVENTORY_COL_ACTIVE,
            INVENTORY_COL_DESCRIPTION,
            INVENTORY_COL_NAME,
        )

        widths = {
            INVENTORY_COL_NAME: 220,
            INVENTORY_COL_DESCRIPTION: 360,
            INVENTORY_COL_ACTIVE: 80,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(INVENTORY_COL_DESCRIPTION, QHeaderView.Stretch)
        for column in (INVENTORY_COL_NAME, INVENTORY_COL_ACTIVE):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "hazard_identifications":
        from moduly.rizeni_rizik.constants import (
            COL_IDENTIFICATION,
            COL_OPERATION,
            COL_RESPONSIBLE_PERSON,
            COL_STARTED_AT,
            COL_STATUS,
            COL_WORKPLACE,
            COL_WORKPLACE_PART,
        )

        # UX-RISK-4: Provoz/Pracoviště stejně široké; Část pracoviště Stretch;
        # Odpovědná osoba širší; Datum a Stav úzké. Interactive = ruční změna.
        widths = {
            COL_OPERATION: 200,
            COL_WORKPLACE: 200,
            COL_WORKPLACE_PART: 280,
            COL_STARTED_AT: 100,
            COL_RESPONSIBLE_PERSON: 200,
            COL_STATUS: 100,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        table.setColumnHidden(COL_IDENTIFICATION, True)
        for column in (
            COL_OPERATION,
            COL_WORKPLACE,
            COL_STARTED_AT,
            COL_RESPONSIBLE_PERSON,
            COL_STATUS,
        ):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_WORKPLACE_PART, QHeaderView.Stretch)

    elif profile == "risk_measure_review_items":
        from moduly.rizeni_rizik.constants import (
            RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT,
            RISK_MEASURE_REVIEW_ITEM_COL_MEASURE,
            RISK_MEASURE_REVIEW_ITEM_COL_NON_COMPLIANT,
            RISK_MEASURE_REVIEW_ITEM_COL_NOTE,
            RISK_MEASURE_REVIEW_ITEM_COL_PHOTO,
        )

        widths = {
            RISK_MEASURE_REVIEW_ITEM_COL_MEASURE: 260,
            RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT: 80,
            RISK_MEASURE_REVIEW_ITEM_COL_NON_COMPLIANT: 90,
            RISK_MEASURE_REVIEW_ITEM_COL_PHOTO: 70,
            RISK_MEASURE_REVIEW_ITEM_COL_NOTE: 220,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(RISK_MEASURE_REVIEW_ITEM_COL_MEASURE, QHeaderView.Stretch)
        header.setSectionResizeMode(RISK_MEASURE_REVIEW_ITEM_COL_NOTE, QHeaderView.Stretch)
        for column in (
            RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT,
            RISK_MEASURE_REVIEW_ITEM_COL_NON_COMPLIANT,
            RISK_MEASURE_REVIEW_ITEM_COL_PHOTO,
        ):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "risk_measure_reviews":
        from moduly.rizeni_rizik.constants import (
            RISK_MEASURE_REVIEW_COL_DATE,
            RISK_MEASURE_REVIEW_COL_NUMBER,
            RISK_MEASURE_REVIEW_COL_OPERATION,
            RISK_MEASURE_REVIEW_COL_REVIEWER,
            RISK_MEASURE_REVIEW_COL_STATUS,
            RISK_MEASURE_REVIEW_COL_WORKPLACE,
            RISK_MEASURE_REVIEW_COL_WORKPLACE_PART,
        )

        # UX-RISK-4: Provoz/Pracoviště stejně široké; Část pracoviště Stretch;
        # Kontrolující širší; Číslo, Datum a Stav úzké. Interactive = ruční změna.
        widths = {
            RISK_MEASURE_REVIEW_COL_NUMBER: 100,
            RISK_MEASURE_REVIEW_COL_DATE: 100,
            RISK_MEASURE_REVIEW_COL_OPERATION: 200,
            RISK_MEASURE_REVIEW_COL_WORKPLACE: 200,
            RISK_MEASURE_REVIEW_COL_WORKPLACE_PART: 280,
            RISK_MEASURE_REVIEW_COL_REVIEWER: 200,
            RISK_MEASURE_REVIEW_COL_STATUS: 110,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (
            RISK_MEASURE_REVIEW_COL_NUMBER,
            RISK_MEASURE_REVIEW_COL_DATE,
            RISK_MEASURE_REVIEW_COL_OPERATION,
            RISK_MEASURE_REVIEW_COL_WORKPLACE,
            RISK_MEASURE_REVIEW_COL_REVIEWER,
            RISK_MEASURE_REVIEW_COL_STATUS,
        ):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setSectionResizeMode(RISK_MEASURE_REVIEW_COL_WORKPLACE_PART, QHeaderView.Stretch)

    elif profile == "hazard_library_templates":
        from moduly.rizeni_rizik.constants_library import (
            HAZARD_LIBRARY_CATEGORY_COLUMN_FIT_TEXT,
            HAZARD_LIBRARY_COL_ACTIVE,
            HAZARD_LIBRARY_COL_CATEGORY,
            HAZARD_LIBRARY_COL_NAME,
            HAZARD_LIBRARY_COL_VERSION,
        )

        # UX-RISK-6: Kategorie dost široká na běžný nejdelší název; Název Stretch.
        widths = {
            HAZARD_LIBRARY_COL_NAME: 220,
            HAZARD_LIBRARY_COL_CATEGORY: _column_width_to_fit_text(
                table,
                HAZARD_LIBRARY_CATEGORY_COLUMN_FIT_TEXT,
            ),
            HAZARD_LIBRARY_COL_VERSION: 70,
            HAZARD_LIBRARY_COL_ACTIVE: 70,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(HAZARD_LIBRARY_COL_NAME, QHeaderView.Stretch)
        for column in (
            HAZARD_LIBRARY_COL_CATEGORY,
            HAZARD_LIBRARY_COL_VERSION,
            HAZARD_LIBRARY_COL_ACTIVE,
        ):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "hazard_library_template_events":
        from moduly.rizeni_rizik.constants_library import (
            HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE,
            HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME,
        )

        table.setColumnWidth(HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE, 70)
        table.setColumnHidden(0, True)
        table.setWordWrap(True)
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME,
            QHeaderView.Stretch,
        )
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE,
            QHeaderView.Fixed,
        )

    elif profile == "hazard_library_template_legal_links":
        from moduly.rizeni_rizik.constants_library import (
            HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ACTIVE,
            HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_NOTE,
            HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_REQUIREMENT,
        )

        table.setColumnWidth(HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ACTIVE, 70)
        table.setColumnHidden(0, True)
        table.setWordWrap(True)
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_REQUIREMENT,
            QHeaderView.Stretch,
        )
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_NOTE,
            QHeaderView.Stretch,
        )
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ACTIVE,
            QHeaderView.Fixed,
        )

    elif profile == "hazard_library_template_assessments":
        from moduly.rizeni_rizik.constants_library import (
            HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ACTIVE,
            HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_GROUP,
            HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_SEVERITY,
        )

        table.setColumnWidth(HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_SEVERITY, 110)
        table.setColumnWidth(HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ACTIVE, 70)
        table.setColumnHidden(0, True)
        table.setWordWrap(True)
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_GROUP,
            QHeaderView.Stretch,
        )
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_SEVERITY,
            QHeaderView.Fixed,
        )
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ACTIVE,
            QHeaderView.Fixed,
        )

    elif profile == "hazard_library_template_existing_measures":
        from moduly.rizeni_rizik.constants_library import (
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE,
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_DESCRIPTION,
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_NOTE,
        )

        table.setColumnWidth(HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE, 70)
        table.setColumnHidden(0, True)
        table.setWordWrap(True)
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_DESCRIPTION,
            QHeaderView.Stretch,
        )
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_NOTE,
            QHeaderView.Stretch,
        )
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE,
            QHeaderView.Fixed,
        )

    elif profile == "hazard_library_template_required_measures":
        from moduly.rizeni_rizik.constants_library import (
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE,
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_DESCRIPTION,
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_NOTE,
        )

        table.setColumnWidth(HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE, 70)
        table.setColumnHidden(0, True)
        table.setWordWrap(True)
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_DESCRIPTION,
            QHeaderView.Stretch,
        )
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_NOTE,
            QHeaderView.Stretch,
        )
        header.setSectionResizeMode(
            HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE,
            QHeaderView.Fixed,
        )

    elif profile == "exposed_groups":
        widths = {0: 260, 1: 280, 2: 80}
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (0, 2):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "legal_requirements":
        from moduly.pravni_pozadavky.ui.legal_requirement_table import (
            COL_CODE,
            COL_LAST_CHECK,
            COL_NEXT_CHECK,
            COL_PERIODICITY,
            COL_PROCESS,
            COL_RESPONSIBLE,
            COL_STATUS,
            COL_SUMMARY,
        )

        widths = {
            COL_CODE: 72,
            COL_PROCESS: 200,
            COL_RESPONSIBLE: 200,
            COL_STATUS: 120,
            COL_NEXT_CHECK: 110,
            COL_LAST_CHECK: 110,
            COL_PERIODICITY: 120,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(COL_SUMMARY, QHeaderView.Stretch)
        for column in widths:
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    elif profile == "controls_year_matrix":
        table.setColumnWidth(0, 230)
        table.setColumnWidth(1, 55)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        for column in range(2, 14):
            header.setSectionResizeMode(column, QHeaderView.Stretch)
            table.setColumnWidth(column, 62)
        table.setAlternatingRowColors(False)

    elif profile == "external_audits_overview":
        # Kompaktní sloupce podle obsahu; organizace + provozy vyplní zbývající šířku.
        for column in range(table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Externí organizace
        header.setSectionResizeMode(5, QHeaderView.Stretch)  # Provozy
        header.setMinimumSectionSize(56)
        header.setStretchLastSection(False)

    elif profile == "external_audit_program":
        for column in range(table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        for column in (3, 4, 5, 6, 7):  # Provoz, role, poznámka
            header.setSectionResizeMode(column, QHeaderView.Stretch)
        header.setMinimumSectionSize(56)
        header.setStretchLastSection(False)

    elif profile == "external_audit_findings":
        for column in range(table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Text zjištění
        header.setMinimumSectionSize(56)
        header.setStretchLastSection(False)

    elif profile == "external_audit_findings_strength":
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setMinimumSectionSize(56)
        header.setStretchLastSection(True)

    elif profile == "state_supervision_overview":
        from moduly.statni_dozor.constants import (
            COL_AUTHORITY,
            COL_ENDED,
            COL_RESULT,
            COL_STARTED,
            COL_STATUS,
            COL_WORKPLACE,
        )

        widths = {
            COL_STATUS: 52,
            COL_AUTHORITY: 220,
            COL_WORKPLACE: 180,
            COL_STARTED: 110,
            COL_ENDED: 110,
            COL_RESULT: 240,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_STARTED, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_ENDED, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_AUTHORITY, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_WORKPLACE, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_RESULT, QHeaderView.Stretch)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)

    elif profile == "state_supervision_required_documents":
        from moduly.statni_dozor.constants import (
            COL_DOCUMENT_DUE,
            COL_DOCUMENT_NOTE,
            COL_DOCUMENT_PREPARED,
            COL_DOCUMENT_RESPONSIBLE,
            COL_DOCUMENT_SUBMITTED,
            COL_DOCUMENT_TITLE,
        )

        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            COL_DOCUMENT_TITLE: 240,
            COL_DOCUMENT_RESPONSIBLE: 160,
            COL_DOCUMENT_DUE: 130,
            COL_DOCUMENT_PREPARED: 130,
            COL_DOCUMENT_SUBMITTED: 130,
            COL_DOCUMENT_NOTE: 200,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(COL_DOCUMENT_DUE, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_DOCUMENT_PREPARED, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_DOCUMENT_SUBMITTED, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_DOCUMENT_RESPONSIBLE, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_DOCUMENT_TITLE, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_DOCUMENT_NOTE, QHeaderView.Stretch)

    elif profile == "state_supervision_participants":
        from moduly.statni_dozor.constants import (
            COL_PARTICIPANT_ATTENDANCE,
            COL_PARTICIPANT_CONTACT,
            COL_PARTICIPANT_NAME,
            COL_PARTICIPANT_NOTE,
            COL_PARTICIPANT_ORGANIZATION,
            COL_PARTICIPANT_PLANNED,
            COL_PARTICIPANT_ROLE,
        )

        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            COL_PARTICIPANT_ROLE: 160,
            COL_PARTICIPANT_NAME: 180,
            COL_PARTICIPANT_ORGANIZATION: 140,
            COL_PARTICIPANT_PLANNED: 110,
            COL_PARTICIPANT_ATTENDANCE: 140,
            COL_PARTICIPANT_CONTACT: 140,
            COL_PARTICIPANT_NOTE: 180,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(COL_PARTICIPANT_PLANNED, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_PARTICIPANT_ATTENDANCE, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_PARTICIPANT_ROLE, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_PARTICIPANT_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_PARTICIPANT_ORGANIZATION, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_PARTICIPANT_CONTACT, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_PARTICIPANT_NOTE, QHeaderView.Stretch)

    elif profile == "state_supervision_attachments":
        from moduly.statni_dozor.constants import (
            COL_ATTACHMENT_NAME,
            COL_ATTACHMENT_SIZE,
            COL_ATTACHMENT_STATUS,
            COL_ATTACHMENT_TYPE,
        )

        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            COL_ATTACHMENT_NAME: 260,
            COL_ATTACHMENT_TYPE: 70,
            COL_ATTACHMENT_SIZE: 90,
            COL_ATTACHMENT_STATUS: 120,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(COL_ATTACHMENT_TYPE, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_ATTACHMENT_SIZE, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_ATTACHMENT_STATUS, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_ATTACHMENT_NAME, QHeaderView.Stretch)

    elif profile == "state_supervision_timeline_items":
        from moduly.statni_dozor.constants import (
            COL_TIMELINE_NOTES,
            COL_TIMELINE_OCCURRED,
            COL_TIMELINE_PLACE,
            COL_TIMELINE_TITLE,
        )

        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            COL_TIMELINE_OCCURRED: 145,
            COL_TIMELINE_TITLE: 265,
            COL_TIMELINE_PLACE: 210,
            COL_TIMELINE_NOTES: 200,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(COL_TIMELINE_OCCURRED, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_TIMELINE_TITLE, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_TIMELINE_PLACE, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_TIMELINE_NOTES, QHeaderView.Stretch)

    elif profile == "state_supervision_findings":
        from moduly.statni_dozor.constants import (
            COL_FINDING_DESCRIPTION,
            COL_FINDING_DUE,
            COL_FINDING_PERSON,
            COL_FINDING_PLACE,
            COL_FINDING_STATUS,
            COL_FINDING_TASK,
            COL_FINDING_TYPE,
        )

        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        widths = {
            COL_FINDING_TYPE: 205,
            COL_FINDING_DESCRIPTION: 190,
            COL_FINDING_PLACE: 165,
            COL_FINDING_STATUS: 105,
            COL_FINDING_PERSON: 180,
            COL_FINDING_DUE: 105,
            COL_FINDING_TASK: 160,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(COL_FINDING_TYPE, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_FINDING_DESCRIPTION, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_FINDING_PLACE, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_FINDING_STATUS, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_FINDING_PERSON, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_FINDING_DUE, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_FINDING_TASK, QHeaderView.Stretch)

    table.verticalHeader().setVisible(False)
    if profile not in ("controls_year_matrix", "yearly_plan"):
        table.setAlternatingRowColors(True)
    if profile == "yearly_plan":
        # Celoroční pohled: zebra po měsících přes Base/AlternateBase, ne globálně.
        table.setAlternatingRowColors(False)


def configure_tree_columns(tree: QTreeWidget, profile: str) -> None:
    """Rozložení sloupců stromu. Nemění existující QTableWidget profily."""
    header = tree.header()
    header.setStretchLastSection(False)
    tree.setWordWrap(False)
    tree.setTextElideMode(Qt.TextElideMode.ElideRight)
    tree.setUniformRowHeights(True)
    tree.setAlternatingRowColors(True)
    tree.setAnimated(False)
    if profile == "control_authority_catalog":
        widths = {
            0: 280,
            1: 170,
            2: 260,
            3: 200,
            4: 90,
            5: 70,
        }
        for column, width in widths.items():
            tree.setColumnWidth(column, width)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        return
    if profile == "control_authority_web_preview":
        widths = {
            0: 240,
            1: 280,
            2: 260,
            3: 220,
        }
        for column, width in widths.items():
            tree.setColumnWidth(column, width)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        return
    header.setStretchLastSection(True)
