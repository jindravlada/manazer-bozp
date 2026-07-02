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

        QFrame#ReferencePhotoPlaceholder {
            background-color: #f9fafb;
            border: 1px dashed #d1d5db;
            border-radius: 10px;
        }

        QFrame#ControlPointPanel {
            border-radius: 10px;
            border: 1px solid #e5e7eb;
            background-color: #ffffff;
            margin: 2px 0;
        }

        QFrame#ControlPointPanel[severity="kriticka"] {
            background-color: #fef2f2;
            border: 1px solid #dc2626;
        }

        QFrame#ControlPointPanel[severity="vysoka"] {
            background-color: #fff7ed;
            border: 1px solid #ea580c;
        }

        QFrame#ControlPointPanel[severity="stredni"] {
            background-color: #fffbeb;
            border: 1px solid #ca8a04;
        }

        QFrame#ControlPointPanel[severity="nizka"] {
            background-color: #f0fdf4;
            border: 1px solid #16a34a;
        }

        QFrame#ControlPointPanel[selected="true"] {
            border-width: 2px;
        }

        QFrame#ControlPointPanel[selected="true"][severity="kriticka"] {
            border-color: #b91c1c;
        }

        QFrame#ControlPointPanel[selected="true"][severity="vysoka"] {
            border-color: #c2410c;
        }

        QFrame#ControlPointPanel[selected="true"][severity="stredni"] {
            border-color: #a16207;
        }

        QFrame#ControlPointPanel[selected="true"][severity="nizka"] {
            border-color: #15803d;
        }

        QLabel#ControlPointTitle {
            font-size: 15px;
            font-weight: bold;
        }

        QLabel#ControlPointSeverityBadge {
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
        }

        QLabel#ControlPointSeverityBadge[severity="kriticka"] {
            color: #991b1b;
            background-color: #fee2e2;
            border: 1px solid #fecaca;
        }

        QLabel#ControlPointSeverityBadge[severity="vysoka"] {
            color: #9a3412;
            background-color: #ffedd5;
            border: 1px solid #fed7aa;
        }

        QLabel#ControlPointSeverityBadge[severity="stredni"] {
            color: #92400e;
            background-color: #fef3c7;
            border: 1px solid #fde68a;
        }

        QLabel#ControlPointSeverityBadge[severity="nizka"] {
            color: #166534;
            background-color: #dcfce7;
            border: 1px solid #bbf7d0;
        }

        QLabel#ProgramStatusBadge {
            font-size: 13px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 6px;
        }

        QLabel#ProgramStatusBadge[programStatus="draft"] {
            background-color: #fef9c3;
            color: #854d0e;
            border: 1px solid #fde047;
        }

        QLabel#ProgramStatusBadge[programStatus="approved"] {
            background-color: #dcfce7;
            color: #166534;
            border: 1px solid #86efac;
        }

        QLabel#ProgramStatusBadge[programStatus="running"] {
            background-color: #dbeafe;
            color: #1e40af;
            border: 1px solid #93c5fd;
        }

        QLabel#ProgramStatusBadge[programStatus="closed"] {
            background-color: #f3f4f6;
            color: #374151;
            border: 1px solid #d1d5db;
        }

        QLabel#ProgramDetailTitle {
            font-size: 17px;
            font-weight: bold;
        }

        QFrame#AuditProgramManagerBanner {
            background-color: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 #ffffff,
                stop:1 #f3f4f6
            );
            border: 1px solid #e5e7eb;
            border-left: 4px solid #60a5fa;
            border-radius: 10px;
        }

        QFrame#AuditProgramManagerBannerSeparator {
            background-color: #e5e7eb;
            border: none;
            max-width: 1px;
        }

        QLabel#AuditProgramManagerBannerTitle {
            font-size: 15px;
            font-weight: bold;
        }

        QLabel#AuditProgramManagerBannerProgramName {
            font-size: 14px;
            font-weight: 600;
        }

        QLabel#AuditProgramManagerBannerSectionTitle {
            font-size: 12px;
            font-weight: 600;
            color: #374151;
        }

        QLabel#AuditProgramManagerBannerHighlight {
            font-size: 14px;
            font-weight: 600;
        }

        QProgressBar#AuditProgramManagerBannerProgress {
            background-color: #e5e7eb;
            border: none;
            border-radius: 5px;
        }

        QProgressBar#AuditProgramManagerBannerProgress::chunk {
            background-color: #60a5fa;
            border-radius: 5px;
        }

        QLabel#ControlResultPhotoThumbnail {
            background-color: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
        }
    """)
