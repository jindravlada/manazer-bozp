from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from core.widgets.info_tooltip import set_widget_tooltip
from core.widgets.text_preview import DEFAULT_TEXT_PREVIEW_LENGTH, truncate_text_preview


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
            6: 110,  # Stav
            7: 90,   # Typ auditu
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (1, 2, 3, 5, 6, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

    elif profile == "bozp_inspections":
        widths = {
            0: 0,    # ID
            1: 90,   # Číslo
            2: 115,  # Datum prověrky
            3: 180,  # Pracoviště
            4: 180,  # Specialista BOZP
            5: 70,   # Závady
            6: 120,  # Stav
            7: 320,  # Název
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        for column in (1, 2, 3, 4, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

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
            COL_CODE: 80,
            COL_PROCESS: 180,
            COL_SUMMARY: 240,
            COL_RESPONSIBLE: 175,
            COL_STATUS: 130,
            COL_NEXT_CHECK: 115,
            COL_LAST_CHECK: 115,
            COL_PERIODICITY: 125,
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(COL_PROCESS, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_SUMMARY, QHeaderView.Fixed)
        for column in (
            COL_CODE,
            COL_RESPONSIBLE,
            COL_STATUS,
            COL_NEXT_CHECK,
            COL_LAST_CHECK,
            COL_PERIODICITY,
        ):
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

    table.verticalHeader().setVisible(False)
    if profile != "controls_year_matrix":
        table.setAlternatingRowColors(True)
