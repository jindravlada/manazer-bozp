from PySide6.QtWidgets import QHeaderView, QTableWidget


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
            8: 80,
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

    elif profile == "tasks":
        widths = {
            0: 0,    # ID
            1: 24,   # Priorita - barevný proužek
            2: 620,  # Opatření
            3: 105,  # Termín
            4: 240,  # Odpovídá
            5: 230,  # Pracoviště
            6: 100,  # Zdroj
        }
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.setColumnHidden(0, True)
        header.setSectionResizeMode(2, QHeaderView.Stretch)

    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
