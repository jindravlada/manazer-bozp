from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.shared.sluzby.performance_evaluation_methodology_service import (
    PerformanceEvaluationExplanation,
    PerformanceEvaluationSimulationInput,
    performance_evaluation_methodology_service,
)
from core.widgets.dialog_utils import configure_resizable_form_dialog, create_close_box


class PerformanceEvaluationExplanationDialog(QDialog):
    """Obecný dialog pro vysvětlení stanovení hodnocení výkonnosti systému."""

    def __init__(
        self,
        parent=None,
        *,
        explanation: PerformanceEvaluationExplanation,
    ):
        super().__init__(parent)
        self.setWindowTitle("Jak bylo stanoveno hodnocení?")
        configure_resizable_form_dialog(self, width=760, height=820, min_width=560, min_height=560)

        self._service = performance_evaluation_methodology_service
        self._updating_simulation = False

        root = QVBoxLayout(self)

        self.rating_label = QLabel()
        self.rating_label.setWordWrap(True)
        self.rating_label.setObjectName("SectionHeading")
        root.addWidget(self.rating_label)

        scroll_host = QWidget()
        scroll_layout = QVBoxLayout(scroll_host)

        indicators_group = QGroupBox("Použité ukazatele")
        self.indicators_layout = QVBoxLayout(indicators_group)
        scroll_layout.addWidget(indicators_group)

        rules_group = QGroupBox("Rozhodovací pravidla")
        self.rules_layout = QVBoxLayout(rules_group)
        scroll_layout.addWidget(rules_group)

        justification_group = QGroupBox("Zdůvodnění")
        justification_layout = QVBoxLayout(justification_group)
        self.justification_label = QLabel()
        self.justification_label.setWordWrap(True)
        justification_layout.addWidget(self.justification_label)
        scroll_layout.addWidget(justification_group)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(scroll_host)
        root.addWidget(scroll, 1)
        self._scroll_host = scroll_host

        simulation_group = QGroupBox("Simulace")
        simulation_form_host = QWidget()
        simulation_form = QFormLayout(simulation_form_host)
        self.sim_activities = self._create_spinbox(0, 999)
        self.sim_control_points = self._create_spinbox(0, 99999)
        self.sim_noncompliance = self._create_spinbox(0, 99999)
        self.sim_overdue = self._create_spinbox(0, 999)
        self.sim_critical = self._create_spinbox(0, 999)
        self.sim_high = self._create_spinbox(0, 999)
        self.sim_repeated = self._create_spinbox(0, 999)
        simulation_form.addRow("Počet kontrolních aktivit:", self.sim_activities)
        simulation_form.addRow("Počet kontrolních bodů:", self.sim_control_points)
        simulation_form.addRow("Počet neshod:", self.sim_noncompliance)
        simulation_form.addRow("Počet otevřených opatření po termínu:", self.sim_overdue)
        simulation_form.addRow("Počet kritických závad:", self.sim_critical)
        simulation_form.addRow("Počet vysokých závad:", self.sim_high)
        simulation_form.addRow("Počet opakovaných problémů:", self.sim_repeated)
        simulation_layout = QVBoxLayout(simulation_group)
        simulation_layout.addWidget(simulation_form_host)
        self.simulation_reason_label = QLabel()
        self.simulation_reason_label.setWordWrap(True)
        simulation_layout.addWidget(self.simulation_reason_label)
        root.addWidget(simulation_group)

        for spinbox in (
            self.sim_activities,
            self.sim_control_points,
            self.sim_noncompliance,
            self.sim_overdue,
            self.sim_critical,
            self.sim_high,
            self.sim_repeated,
        ):
            spinbox.valueChanged.connect(self._on_simulation_changed)

        buttons = create_close_box(self)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._render(explanation)

    @staticmethod
    def _create_spinbox(minimum: int, maximum: int) -> QSpinBox:
        spinbox = QSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setMinimumWidth(120)
        return spinbox

    def _render(self, explanation: PerformanceEvaluationExplanation) -> None:
        self._updating_simulation = True
        try:
            self.rating_label.setText(
                f"{explanation.rating.emoji} {explanation.rating.headline}\n"
                f"Spolehlivost hodnocení: {explanation.reliability.label}"
            )
            self._render_indicators(explanation)
            self._render_rules(explanation)
            self.justification_label.setText(explanation.justification)
            self._set_simulation_values(explanation.simulation)
            self.simulation_reason_label.setText(explanation.justification)
            self._scroll_host.adjustSize()
        finally:
            self._updating_simulation = False

    def _render_indicators(self, explanation: PerformanceEvaluationExplanation) -> None:
        self._clear_layout(self.indicators_layout)
        for indicator in explanation.indicators:
            block = QWidget()
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(0, 0, 0, 0)

            title = QLabel(indicator.label)
            title.setObjectName("SectionHeading")
            block_layout.addWidget(title)

            value = QLabel(indicator.value_text)
            value.setStyleSheet("font-size: 14pt;")
            block_layout.addWidget(value)

            influence = QLabel(
                "✔ ovlivnilo hodnocení"
                if indicator.influenced
                else "— neovlivnilo hodnocení"
            )
            block_layout.addWidget(influence)

            hint = QLabel(indicator.explanation)
            hint.setWordWrap(True)
            hint.setStyleSheet("color: palette(mid);")
            block_layout.addWidget(hint)

            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
            block_layout.addWidget(separator)

            self.indicators_layout.addWidget(block)

    def _render_rules(self, explanation: PerformanceEvaluationExplanation) -> None:
        self._clear_layout(self.rules_layout)
        for rule in explanation.rules:
            prefix = "✔" if rule.applied else "○"
            label = QLabel(f"{prefix} {rule.label}\n{rule.effect_text}")
            label.setWordWrap(True)
            if not rule.applied:
                label.setStyleSheet("color: palette(mid);")
            self.rules_layout.addWidget(label)

    def _set_simulation_values(self, simulation: PerformanceEvaluationSimulationInput) -> None:
        self.sim_activities.setValue(simulation.activities_count)
        self.sim_control_points.setValue(simulation.control_points_count)
        self.sim_noncompliance.setValue(simulation.noncompliance_count)
        self.sim_overdue.setValue(simulation.overdue_measures_count)
        self.sim_critical.setValue(simulation.critical_findings_count)
        self.sim_high.setValue(simulation.high_severity_count)
        self.sim_repeated.setValue(simulation.repeated_problems_count)

    def _collect_simulation(self) -> PerformanceEvaluationSimulationInput:
        return PerformanceEvaluationSimulationInput(
            activities_count=self.sim_activities.value(),
            control_points_count=self.sim_control_points.value(),
            noncompliance_count=self.sim_noncompliance.value(),
            overdue_measures_count=self.sim_overdue.value(),
            critical_findings_count=self.sim_critical.value(),
            high_severity_count=self.sim_high.value(),
            repeated_problems_count=self.sim_repeated.value(),
        )

    def _on_simulation_changed(self) -> None:
        if self._updating_simulation:
            return
        explanation = self._service.simulate(self._collect_simulation())
        self._render(explanation)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
