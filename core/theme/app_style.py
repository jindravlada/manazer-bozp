from PySide6.QtWidgets import QApplication


def apply_app_style(app: QApplication) -> None:
    """
    Jednotný vzhled aplikace.
    """
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f3f4f6;
        }

        QWidget {
            font-size: 14px;
        }

        QLabel#AppTitle {
            font-size: 22px;
            font-weight: bold;
        }

        QLabel#PageTitle {
            font-size: 22px;
            font-weight: bold;
        }

        QLabel#SectionTitle {
            font-size: 16px;
            font-weight: bold;
        }

        QLabel#InfoText {
            color: #4b5563;
        }

        QLabel#MutedText {
            color: #6b7280;
            font-size: 13px;
        }

        QPushButton {
            padding: 8px 12px;
            border-radius: 6px;
            background-color: #e5e7eb;
            border: 1px solid #d1d5db;
            text-align: left;
        }

        QPushButton:hover {
            background-color: #dbeafe;
            border: 1px solid #93c5fd;
        }

        QPushButton:disabled {
            color: #9ca3af;
            background-color: #f3f4f6;
        }

        QPushButton#PrimaryButton {
            background-color: #2563eb;
            color: white;
            border: 1px solid #1d4ed8;
            font-weight: bold;
            text-align: center;
        }

        QPushButton#PrimaryButton:hover {
            background-color: #1d4ed8;
        }

        QPushButton#QuickButton {
            background-color: #ffffff;
            border: 1px solid #d1d5db;
            font-weight: bold;
            text-align: center;
            min-height: 42px;
        }

        QPushButton#QuickButton:hover {
            background-color: #eff6ff;
            border: 1px solid #60a5fa;
        }

        QLineEdit {
            padding: 8px 10px;
            border-radius: 6px;
            border: 1px solid #d1d5db;
            background-color: #ffffff;
        }

        QFrame#Sidebar {
            background-color: #ffffff;
            border-right: 1px solid #d1d5db;
        }

        QFrame#HeaderCard,
        QFrame#ContentCard {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
        }

        QFrame#ModulePanel {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
        }

        QFrame#ControlPointRow {
            border-radius: 6px;
        }

        QFrame#ControlPointRow[selected="true"] {
            background-color: #f3f4f6;
            border-left: 3px solid #2563eb;
        }

        QLabel#ControlResultPhotoThumbnail {
            background-color: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
        }
    """)
