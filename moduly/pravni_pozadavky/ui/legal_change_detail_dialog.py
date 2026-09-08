from datetime import date, datetime

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_close_box,
    wrap_in_scroll_area,
)
from moduly.pravni_pozadavky.constants import (
    CHANGE_TYPE_LABELS,
    NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
    legal_document_catalog_link_label,
)
from moduly.pravni_pozadavky.sluzby.legal_change_impacted_assertion_service import (
    legal_change_impacted_assertion_service,
)
from moduly.pravni_pozadavky.sluzby.legal_change_impacted_process_service import (
    legal_change_impacted_process_service,
)
from moduly.pravni_pozadavky.sluzby.legal_change_section_service import (
    legal_change_section_service,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.ui.legal_change_impacted_assertions_table import (
    LegalChangeImpactedAssertionsTable,
)
from moduly.pravni_pozadavky.ui.legal_change_impacted_processes_widget import (
    LegalChangeImpactedProcessesWidget,
)
from moduly.pravni_pozadavky.ui.legal_change_sections_table import LegalChangeSectionsTable


def _format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _display_note(note: str) -> str:
    normalized = (note or "").strip()
    if normalized.startswith(NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX):
        return ""
    return normalized


class LegalChangeDetailDialog(QDialog):
    """Detail zjištěné změny legislativy."""

    def __init__(self, parent=None, *, change):
        super().__init__(parent)
        self.change = change

        self.setWindowTitle("Detail zjištěné změny")
        configure_resizable_form_dialog(self, width=760, height=680, min_width=560, min_height=480)

        layout = QVBoxLayout(self)
        layout.addWidget(wrap_in_scroll_area(self._build_content()))
        buttons = create_close_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_content(self) -> QWidget:
        content = QWidget()
        root = QVBoxLayout(content)

        form_host = QWidget()
        form = QFormLayout(form_host)
        document = legal_document_service.get_by_id(self.change.legal_document_id)
        document_label = ""
        if document is not None:
            document_label = legal_document_catalog_link_label(document) or document.title

        original_version = None
        if self.change.legal_document_version_id is not None:
            original_version = legal_document_version_service.get_by_id(
                self.change.legal_document_version_id,
            )
        detected_version = None
        if self.change.new_legal_document_version_id is not None:
            detected_version = legal_document_version_service.get_by_id(
                self.change.new_legal_document_version_id,
            )

        self._add_readonly_row(form, "Právní předpis:", document_label)
        self._add_readonly_row(
            form,
            "Používané znění:",
            original_version.version_name if original_version is not None else "—",
        )
        self._add_readonly_row(
            form,
            "Nově zjištěné znění:",
            detected_version.version_name if detected_version is not None else "—",
        )
        self._add_readonly_row(
            form,
            "Typ změny:",
            CHANGE_TYPE_LABELS.get(self.change.change_type, self.change.change_type),
        )
        self._add_readonly_row(form, "Datum zveřejnění:", _format_date(self.change.published_at))
        self._add_readonly_row(
            form,
            "Stav vyhodnocení:",
            "Vyhodnoceno" if self.change.evaluated else "Nevyhodnoceno",
        )
        self._add_readonly_text_row(form, "Popis:", self.change.description)
        self._add_readonly_text_row(form, "Poznámka:", _display_note(self.change.note))
        root.addWidget(form_host)

        sections_group = QGroupBox("Změněná ustanovení")
        sections_layout = QVBoxLayout(sections_group)
        sections = legal_change_section_service.list_sections_for_change(self.change.id)
        if sections:
            table = LegalChangeSectionsTable()
            table.load_sections(sections)
            sections_layout.addWidget(table)
        else:
            empty_label = QLabel("U této změny nebyla zjištěna změna struktury ustanovení.")
            empty_label.setWordWrap(True)
            sections_layout.addWidget(empty_label)
        root.addWidget(sections_group)

        processes_group = QGroupBox("Dotčené řídicí procesy")
        processes_layout = QVBoxLayout(processes_group)
        processes = legal_change_impacted_process_service.list_processes_for_change(self.change.id)
        if processes:
            processes_widget = LegalChangeImpactedProcessesWidget()
            processes_widget.load_processes(processes)
            processes_layout.addWidget(processes_widget)
        else:
            empty_processes_label = QLabel(
                "Toto ustanovení zatím není přiřazeno k žádnému řídicímu procesu.",
            )
            empty_processes_label.setWordWrap(True)
            processes_layout.addWidget(empty_processes_label)
        root.addWidget(processes_group)

        assertions_group = QGroupBox("Dotčená auditní tvrzení")
        assertions_layout = QVBoxLayout(assertions_group)
        assertions = legal_change_impacted_assertion_service.list_assertions_for_change(
            self.change.id,
        )
        if assertions:
            assertions_table = LegalChangeImpactedAssertionsTable()
            assertions_table.load_assertions(assertions)
            assertions_layout.addWidget(assertions_table)
        else:
            empty_assertions_label = QLabel(
                "Ke změně nejsou navázána žádná auditní tvrzení.",
            )
            empty_assertions_label.setWordWrap(True)
            assertions_layout.addWidget(empty_assertions_label)
        root.addWidget(assertions_group)

        return content

    def _add_readonly_row(self, form: QFormLayout, label: str, value: str) -> None:
        field = QLabel((value or "").strip() or "—")
        field.setWordWrap(True)
        form.addRow(label, field)

    def _add_readonly_text_row(self, form: QFormLayout, label: str, value: str) -> None:
        field = QTextEdit()
        field.setReadOnly(True)
        field.setPlainText((value or "").strip())
        field.setMinimumHeight(70)
        form.addRow(label, field)
