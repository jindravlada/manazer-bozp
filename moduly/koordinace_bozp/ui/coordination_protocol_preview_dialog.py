from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    add_work_dialog_footer,
    configure_resizable_form_dialog,
    create_close_box,
)
from moduly.koordinace_bozp.constants import (
    AGREEMENT_SECTION_TITLE,
    COMMON_RULES_SECTION_TITLE,
    PROTOCOL_WARNING_EMPLOYER_WITHOUT_ACTIVITY,
    PROTOCOL_WARNING_MISSING_COORDINATOR,
    PROTOCOL_WARNING_MISSING_MEASURES,
    PROTOCOL_WARNING_MISSING_WORKPLACE,
    PROTOCOL_WARNING_SEVERITY_CRITICAL,
    PROTOCOL_WARNING_SEVERITY_INFO,
    PROTOCOL_WARNING_SEVERITY_WARNING,
    TAB_CONTACTS,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
    CoordinationProtocolBuilderError,
    ProtocolBuildResult,
    build_coordination_agreement_parts,
    coordination_protocol_builder,
    flatten_protocol_measure_bullets,
)
from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
    protocol_version_mark,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
    CoordinationProtocolOdtRendererError,
    coordination_protocol_odt_renderer,
)


def _format_date(value: str | None) -> str:
    if not value:
        return "—"
    parts = value.split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return value


class CoordinationProtocolPreviewDialog(QDialog):
    """Read-only náhled koordinačního protokolu (COORD-011a)."""

    def __init__(self, parent=None, *, coordination_id: int):
        super().__init__(parent)
        self.coordination_id = coordination_id
        self._build_result: ProtocolBuildResult | None = None
        self.setWindowTitle("Náhled koordinačního protokolu")
        configure_resizable_form_dialog(
            self,
            width=820,
            height=700,
            min_width=560,
            min_height=420,
        )

        layout = QVBoxLayout(self)
        self.status_label = QLabel()
        font = QFont(self.status_label.font())
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.status_label.setFont(font)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(self.body)
        layout.addWidget(scroll, 1)

        self.export_btn = QPushButton("Export ODT")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_odt)
        buttons = create_close_box(self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        add_work_dialog_footer(
            layout,
            work_widgets=[self.export_btn],
            buttons=buttons,
        )

        self._load()

    def _load(self) -> None:
        try:
            result = coordination_protocol_builder.build(self.coordination_id)
        except CoordinationProtocolBuilderError as error:
            self._build_result = None
            self.export_btn.setEnabled(False)
            self.status_label.setText(str(error))
            return
        self._build_result = result
        self.export_btn.setEnabled(True)
        self._render(result)

    def export_odt(self) -> None:
        """Exportuje ODT z již sestavených dat náhledu (bez nového sestavení)."""
        if self._build_result is None:
            QMessageBox.warning(
                self,
                "Export ODT",
                "Protokol není připraven k exportu.",
            )
            return
        basics = (self._build_result.protocol_data or {}).get("basics") or {}
        number = basics.get("coordination_number") or "protokol"
        suggested = f"KoordinacniProtokol-{number}.odt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ODT",
            suggested,
            "ODT (*.odt)",
        )
        if not path:
            return
        try:
            exported = coordination_protocol_odt_renderer.render_from_result(
                path,
                self._build_result,
            )
        except CoordinationProtocolOdtRendererError as error:
            QMessageBox.warning(self, "Export ODT", str(error))
            return
        QMessageBox.information(
            self,
            "Export ODT",
            f"Soubor byl uložen:\n{exported}",
        )

    def _render(self, result: ProtocolBuildResult) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        warning_count = result.summary.warnings_total
        basics = (result.protocol_data or {}).get("basics") or {}
        version_mark = protocol_version_mark(basics.get("status"))
        if warning_count == 0:
            status_text = "Připraveno bez upozornění"
            self.status_label.setStyleSheet("color: #2e7d32;")
        else:
            status_text = f"Protokol obsahuje {warning_count} upozornění"
            self.status_label.setStyleSheet("color: #ef6c00;")
        if version_mark:
            status_text = f"{version_mark} — {status_text}"
        self.status_label.setText(status_text)

        data = result.protocol_data
        warning_codes = {item.code for item in result.warnings}

        if version_mark:
            mark_label = QLabel(version_mark)
            mark_font = QFont(mark_label.font())
            mark_font.setBold(True)
            mark_label.setFont(mark_font)
            mark_label.setStyleSheet("color: #c62828;")
            self.body_layout.addWidget(mark_label)

        self._add_warnings_section(result.warnings)

        self._add_section(
            "Základní údaje",
            self._basics_lines(data.get("basics") or {}),
            force=True,
        )

        employers = data.get("employers") or []
        participants = data.get("participants_by_employer") or []
        self._add_section(
            "Zaměstnavatelé a účastníci",
            self._employers_participants_lines(employers, participants),
            force=bool(employers or participants),
        )

        coordinator = data.get("coordinator")
        self._add_section(
            "Koordinátor BOZP",
            self._coordinator_lines(coordinator),
            force=bool(coordinator)
            or PROTOCOL_WARNING_MISSING_COORDINATOR in warning_codes,
        )

        workplaces = data.get("workplaces") or []
        self._add_section(
            "Místa výkonu práce",
            self._workplaces_lines(workplaces),
            force=bool(workplaces)
            or PROTOCOL_WARNING_MISSING_WORKPLACE in warning_codes,
        )

        activities = data.get("activities_by_employer") or []
        has_activities = any(group.get("activities") for group in activities)
        self._add_section(
            "Činnosti na pracovišti",
            self._activities_lines(activities),
            force=has_activities
            or PROTOCOL_WARNING_EMPLOYER_WITHOUT_ACTIVITY in warning_codes,
        )

        measures = data.get("measures_by_category") or []
        agreement_parts = build_coordination_agreement_parts(data)
        if agreement_parts:
            agreement_lines: list[str] = []
            for part in agreement_parts:
                if agreement_lines:
                    agreement_lines.append("")
                agreement_lines.append(part["title"])
                agreement_lines.extend(part["lines"])
            self._add_section(
                AGREEMENT_SECTION_TITLE,
                agreement_lines,
                force=True,
                allow_empty_placeholder=False,
            )

        measure_lines = flatten_protocol_measure_bullets(measures)
        if measure_lines or PROTOCOL_WARNING_MISSING_MEASURES in warning_codes:
            self._add_section(
                COMMON_RULES_SECTION_TITLE,
                measure_lines
                if measure_lines
                else ["Nejsou evidována žádná aktivní společná pravidla BOZP."],
                force=True,
                allow_empty_placeholder=False,
            )

        contacts = data.get("contacts") or []
        contact_groups = data.get("contacts_by_type") or []
        procedures = data.get("emergency_procedures") or {}
        self._add_section(
            TAB_CONTACTS,
            self._contacts_grouped_lines(contact_groups, contacts),
            force=bool(contacts) or bool(contact_groups),
        )
        if any((value or "").strip() for value in procedures.values()):
            self._add_section(
                "Postupy při mimořádných událostech",
                self._procedures_lines(procedures),
                force=True,
            )

        risks = data.get("risk_handovers") or []
        self._add_section(
            "Předání rizik",
            self._risks_lines(risks),
            force=bool(risks),
        )

        attachments = data.get("attachments_by_group") or []
        pbp = data.get("pbp_snapshot")
        self._add_section(
            "Přílohy",
            self._attachments_lines(attachments, pbp),
            force=bool(attachments) or bool(pbp),
        )

        self._add_section(
            "Souhrn",
            self._summary_lines(result.summary.to_dict()),
            force=True,
        )
        self.body_layout.addStretch(1)

    def _add_warnings_section(self, warnings) -> None:
        if not warnings:
            return
        lines = []
        for item in warnings:
            prefix = {
                PROTOCOL_WARNING_SEVERITY_CRITICAL: "[kritické]",
                PROTOCOL_WARNING_SEVERITY_WARNING: "[varování]",
                PROTOCOL_WARNING_SEVERITY_INFO: "[info]",
            }.get(item.severity, "")
            lines.append(f"{prefix} {item.message}".strip())
        self._add_section("Upozornění", lines, force=True)

    def _add_section(
        self,
        title: str,
        lines: list[str],
        *,
        force: bool,
        allow_empty_placeholder: bool = True,
    ) -> None:
        if not force:
            return
        if not lines:
            if not allow_empty_placeholder:
                return
            lines = ["—"]
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        label = QLabel("\n".join(lines))
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        group_layout.addWidget(label)
        self.body_layout.addWidget(group)

    @staticmethod
    def _basics_lines(basics: dict) -> list[str]:
        return [
            f"Číslo: {basics.get('coordination_number') or '—'}",
            f"Datum schůzky: {_format_date(basics.get('meeting_date'))}",
            f"Místo: {basics.get('place') or '—'}",
            f"Název akce: {basics.get('subject') or '—'}",
            f"Stav: {basics.get('status_label') or basics.get('status') or '—'}",
            (
                f"Platnost: {_format_date(basics.get('valid_from'))}"
                f" – {_format_date(basics.get('valid_to'))}"
            ),
            f"Poznámka: {basics.get('note') or '—'}",
        ]

    @staticmethod
    def _employers_participants_lines(employers, participants_groups) -> list[str]:
        lines = []
        for employer in employers:
            role = "hlavní" if employer.get("is_main") else "zúčastněný"
            lines.append(f"• {employer.get('display_name')} ({role})")
        if participants_groups:
            lines.append("")
            lines.append("Účastníci podle zaměstnavatele:")
            for group in participants_groups:
                employer = group.get("employer") or {}
                lines.append(f"  {employer.get('display_name')}:")
                participants = group.get("participants") or []
                if not participants:
                    lines.append("    — žádní aktivní účastníci")
                    continue
                for participant in participants:
                    detail = participant.get("full_name") or "—"
                    if participant.get("role"):
                        detail = f"{detail} – {participant['role']}"
                    lines.append(f"    • {detail}")
        return lines

    @staticmethod
    def _coordinator_lines(coordinator) -> list[str]:
        if not coordinator:
            return ["Koordinátor není určen."]
        lines = []
        name = (coordinator.get("full_name") or "").strip()
        lines.append(f"Jméno: {name or '—'}")
        employer = (coordinator.get("employer_name") or "").strip()
        if employer:
            lines.append(f"Organizace: {employer}")
        role = (coordinator.get("role") or "").strip()
        if role:
            lines.append(f"Funkce: {role}")
        if coordinator.get("phone"):
            lines.append(f"Telefon: {coordinator['phone']}")
        if coordinator.get("email"):
            lines.append(f"E-mail: {coordinator['email']}")
        note = (coordinator.get("note") or "").strip()
        if note:
            lines.append("")
            lines.append("Další informace")
            lines.append(note)
        return lines

    @staticmethod
    def _workplaces_lines(workplaces) -> list[str]:
        if not workplaces:
            return ["Není evidováno žádné aktivní místo výkonu práce."]
        return [f"• {item.get('label') or '—'}" for item in workplaces]

    @staticmethod
    def _activities_lines(groups) -> list[str]:
        lines = []
        for group in groups:
            employer = group.get("employer") or {}
            activities = group.get("activities") or []
            lines.append(f"{employer.get('display_name')}:")
            if not activities:
                lines.append("  — bez aktivní činnosti")
                continue
            for activity in activities:
                place = activity.get("workplace_label") or ""
                suffix = f" ({place})" if place else ""
                lines.append(f"  • {activity.get('activity_name') or '—'}{suffix}")
        return lines or ["—"]

    @staticmethod
    def _measures_lines(groups) -> list[str]:
        lines = flatten_protocol_measure_bullets(groups)
        if not lines:
            return ["Nejsou evidována žádná aktivní organizační opatření."]
        return lines

    @staticmethod
    def _contacts_grouped_lines(contact_groups, contacts) -> list[str]:
        groups = list(contact_groups or [])
        if not groups and contacts:
            groups = [{"contact_type_label": "", "contacts": list(contacts)}]
        lines: list[str] = []
        for group in groups:
            type_label = (group.get("contact_type_label") or "").strip()
            items = group.get("contacts") or []
            if not items:
                continue
            if type_label:
                lines.append(type_label)
            for contact in items:
                detail = contact.get("custom_name") or "—"
                role = contact.get("role") or ""
                if role:
                    detail = f"{detail} – {role}"
                phone = contact.get("phone") or ""
                email = contact.get("email") or ""
                extras = ", ".join(item for item in (phone, email) if item)
                if extras:
                    detail = f"{detail} – {extras}"
                lines.append(f"• {detail}")
        return lines or ["—"]

    @staticmethod
    def _procedures_lines(procedures) -> list[str]:
        return [
            f"Mimořádná událost: {procedures.get('emergency_reporting') or '—'}",
            f"Pracovní úraz: {procedures.get('accident_reporting') or '—'}",
            f"Požár: {procedures.get('fire_reporting') or '—'}",
            f"Evakuace: {procedures.get('evacuation_instructions') or '—'}",
        ]

    @staticmethod
    def _risks_lines(rows) -> list[str]:
        if not rows:
            return ["—"]
        lines = []
        for row in rows:
            employer = row.get("employer") or {}
            lines.append(
                f"• {employer.get('display_name')}: "
                f"{row.get('handover_status_label') or row.get('handover_status')}"
            )
        return lines

    @staticmethod
    def _attachments_lines(groups, pbp) -> list[str]:
        lines = []
        if pbp and not groups:
            lines.append(
                f"Příloha PBP: revize {pbp.get('revision_number')} "
                f"({pbp.get('rules_count') or 0} pravidel)"
            )
        for group in groups:
            lines.append(f"{group.get('attachment_type_label')}:")
            for attachment in group.get("attachments") or []:
                name = attachment.get("original_filename") or attachment.get(
                    "description"
                ) or "—"
                lines.append(f"  • {name}")
        return lines or ["—"]

    @staticmethod
    def _summary_lines(summary: dict) -> list[str]:
        return [
            f"Aktivní zaměstnavatelé: {summary.get('active_employers', 0)}",
            f"Aktivní účastníci: {summary.get('active_participants', 0)}",
            f"Aktivní místa: {summary.get('active_workplaces', 0)}",
            f"Aktivní činnosti: {summary.get('active_activities', 0)}",
            f"Aktivní organizační opatření: {summary.get('active_measures', 0)}",
            f"Aktivní kontakty: {summary.get('active_contacts', 0)}",
            f"Pravidla v posledním PBP snapshotu: {summary.get('pbp_rules_count', 0)}",
            f"Aktivní přílohy: {summary.get('active_attachments', 0)}",
            (
                "Varování – info / warning / critical: "
                f"{summary.get('warnings_info', 0)} / "
                f"{summary.get('warnings_warning', 0)} / "
                f"{summary.get('warnings_critical', 0)}"
            ),
        ]
