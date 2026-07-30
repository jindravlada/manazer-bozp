"""Dialog hromadné analýzy podobností (SIMILARITY-2 / SIMILARITY-3)."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.shared.sluzby.similarity_checked_pair_service import (
    SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
    similarity_checked_pair_service,
)
from core.widgets.dialog_utils import exec_maximized
from moduly.proverky.sluzby.control_point_similarity_analysis import (
    ControlPointSimilarityPair,
    analyze_control_point_similarities,
)
from moduly.proverky.sluzby.control_point_similarity_service import (
    ControlPointSimilarityCandidate,
    parse_control_point_composite_id,
)

SCOPE_PBP = "pbp"
SCOPE_PROVERKY = "proverky_kontrolni_otazky"
SCOPE_AUDIT = "auditni_tvrzeni"
SCOPE_RISKS = "rizika"
SCOPE_MEASURES = "opatreni"
SCOPE_LEGAL = "pravni_pozadavky"

SIMILARITY_SCOPE_DEFS = (
    (SCOPE_PBP, "PBP", False),
    (SCOPE_PROVERKY, "Kontrolní otázky prověrek", True),
    (SCOPE_AUDIT, "Auditní tvrzení", False),
    (SCOPE_RISKS, "Rizika", False),
    (SCOPE_MEASURES, "Opatření", False),
    (SCOPE_LEGAL, "Právní požadavky", False),
)


class _ControlPointAnalysisWorker(QThread):
    progress = Signal(int, int, int)  # current, total, found
    finished_ok = Signal(object, bool)  # pairs, cancelled
    failed = Signal(str)

    def __init__(self, *, include_checked: bool, parent=None) -> None:
        super().__init__(parent)
        self._cancel_requested = False
        self._include_checked = include_checked

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            pairs, cancelled = analyze_control_point_similarities(
                include_checked=self._include_checked,
                progress_callback=self._on_progress,
                should_cancel=lambda: self._cancel_requested,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(pairs, cancelled)

    def _on_progress(self, current: int, total: int, found: int) -> None:
        self.progress.emit(current, total, found)


class SimilarityAnalysisDialog(QDialog):
    """Nástroj údržby: výběr oblastí → průběh → kandidáti podobnosti."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        include_checked: bool | None = None,
        auto_start: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Analýza podobností")
        self.setModal(True)
        self.resize(980, 660)

        self._worker: _ControlPointAnalysisWorker | None = None
        self._pairs: list[ControlPointSimilarityPair] = []
        self._cancelled = False

        root = QVBoxLayout(self)
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        self._setup_page = self._build_setup_page()
        self._progress_page = self._build_progress_page()
        self._results_page = self._build_results_page()
        self._stack.addWidget(self._setup_page)
        self._stack.addWidget(self._progress_page)
        self._stack.addWidget(self._results_page)

        self._stack.setCurrentWidget(self._setup_page)

        if include_checked is not None:
            self._show_checked_setup.setChecked(include_checked)
            self._show_checked_results.blockSignals(True)
            self._show_checked_results.setChecked(include_checked)
            self._show_checked_results.blockSignals(False)

        if auto_start:
            QTimer.singleShot(0, self._start_analysis)

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        intro = QLabel(
            "Hromadná kontrola kvality dat. Analýza může trvat i několik minut. "
            "Zkontrolované dvojice se ve výchozím stavu znovu nenabízejí."
        )
        intro.setWordWrap(True)
        intro.setObjectName("InfoText")
        layout.addWidget(intro)

        form = QFormLayout()
        self._scope_checks: dict[str, QCheckBox] = {}
        for key, label, implemented in SIMILARITY_SCOPE_DEFS:
            check = QCheckBox(label)
            check.setChecked(implemented)
            check.setEnabled(implemented)
            if not implemented:
                check.setToolTip("Připraveno pro budoucí rozšíření.")
            self._scope_checks[key] = check
            form.addRow(check)
        layout.addLayout(form)

        self._show_checked_setup = QCheckBox("Zobrazit již zkontrolované dvojice")
        self._show_checked_setup.setChecked(False)
        layout.addWidget(self._show_checked_setup)
        layout.addStretch()

        buttons = QDialogButtonBox()
        self._start_btn = buttons.addButton(
            "Spustit analýzu", QDialogButtonBox.ButtonRole.AcceptRole
        )
        close_btn = buttons.addButton(
            "Zavřít", QDialogButtonBox.ButtonRole.RejectRole
        )
        self._start_btn.clicked.connect(self._start_analysis)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)
        return page

    def _build_progress_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self._progress_scope_label = QLabel("Kontrolní otázky")
        self._progress_scope_label.setObjectName("SectionTitle")
        layout.addWidget(self._progress_scope_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._progress_count_label = QLabel("0 / 0")
        layout.addWidget(self._progress_count_label)

        self._progress_found_label = QLabel("Nalezeno kandidátů: 0")
        layout.addWidget(self._progress_found_label)

        layout.addStretch()

        buttons = QDialogButtonBox()
        self._cancel_btn = buttons.addButton(
            "Zrušit analýzu", QDialogButtonBox.ButtonRole.RejectRole
        )
        self._cancel_btn.clicked.connect(self._cancel_analysis)
        layout.addWidget(buttons)
        return page

    def _build_results_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self._results_summary = QLabel()
        self._results_summary.setWordWrap(True)
        self._results_summary.setObjectName("InfoText")
        layout.addWidget(self._results_summary)

        self._show_checked_results = QCheckBox("Zobrazit již zkontrolované dvojice")
        self._show_checked_results.setChecked(False)
        self._show_checked_results.toggled.connect(self._on_show_checked_toggled)
        layout.addWidget(self._show_checked_results)

        self._empty_label = QLabel("Nebyly nalezeny žádné podobné záznamy.")
        self._empty_label.setWordWrap(True)
        self._empty_label.setObjectName("InfoText")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        self._results_table = QTableWidget(0, 6)
        self._results_table.setHorizontalHeaderLabels(
            [
                "Stav",
                "Podobnost",
                "První otázka",
                "Umístění první",
                "Druhá otázka",
                "Umístění druhé",
            ]
        )
        self._results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._results_table.verticalHeader().setVisible(False)
        header = self._results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._results_table, 1)

        actions = QHBoxLayout()
        self._open_first_btn = QPushButton("Otevřít první")
        self._open_second_btn = QPushButton("Otevřít druhou")
        self._open_both_btn = QPushButton("Otevřít obě")
        self._mark_checked_btn = QPushButton("Označit jako zkontrolované")
        self._unmark_checked_btn = QPushButton("Zrušit označení")
        self._open_first_btn.clicked.connect(lambda: self._open_selected("first"))
        self._open_second_btn.clicked.connect(lambda: self._open_selected("second"))
        self._open_both_btn.clicked.connect(lambda: self._open_selected("both"))
        self._mark_checked_btn.clicked.connect(self._mark_selected_checked)
        self._unmark_checked_btn.clicked.connect(self._unmark_selected_checked)
        for btn in (
            self._open_first_btn,
            self._open_second_btn,
            self._open_both_btn,
            self._mark_checked_btn,
            self._unmark_checked_btn,
        ):
            btn.setEnabled(False)
            actions.addWidget(btn)
        actions.addStretch()
        layout.addLayout(actions)

        self._results_table.itemSelectionChanged.connect(self._update_action_buttons)

        buttons = QDialogButtonBox()
        again_btn = buttons.addButton(
            "Nová analýza", QDialogButtonBox.ButtonRole.ActionRole
        )
        close_btn = buttons.addButton(
            "Zavřít", QDialogButtonBox.ButtonRole.RejectRole
        )
        again_btn.clicked.connect(self._back_to_setup)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)
        return page

    def _start_analysis(self) -> None:
        if not self._scope_checks[SCOPE_PROVERKY].isChecked():
            QMessageBox.information(
                self,
                self.windowTitle(),
                "V tomto sprintu je implementována pouze oblast "
                "„Kontrolní otázky prověrek“.",
            )
            return

        self._pairs = []
        self._cancelled = False
        include_checked = self._show_checked_setup.isChecked()
        self._show_checked_results.blockSignals(True)
        self._show_checked_results.setChecked(include_checked)
        self._show_checked_results.blockSignals(False)

        self._progress_bar.setValue(0)
        self._progress_count_label.setText("0 / 0")
        self._progress_found_label.setText("Nalezeno kandidátů: 0")
        self._cancel_btn.setEnabled(True)
        self._stack.setCurrentWidget(self._progress_page)

        self._worker = _ControlPointAnalysisWorker(
            include_checked=include_checked,
            parent=self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _cancel_analysis(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._cancel_btn.setEnabled(False)
            self._progress_found_label.setText(
                self._progress_found_label.text() + " — ruším…"
            )
            self._worker.request_cancel()

    def _on_progress(self, current: int, total: int, found: int) -> None:
        self._progress_bar.setMaximum(max(total, 1))
        self._progress_bar.setValue(current)
        self._progress_count_label.setText(f"{current} / {total}")
        self._progress_found_label.setText(f"Nalezeno kandidátů: {found}")

    def _on_finished(self, pairs: object, cancelled: bool) -> None:
        self._pairs = list(pairs or [])
        self._cancelled = bool(cancelled)
        self._worker = None
        self._show_results()

    def _on_failed(self, message: str) -> None:
        self._worker = None
        QMessageBox.critical(
            self,
            self.windowTitle(),
            f"Analýza selhala.\n\n{message}",
        )
        self._stack.setCurrentWidget(self._setup_page)

    def _on_show_checked_toggled(self, checked: bool) -> None:
        if not self._pairs and not checked:
            self._show_results()
            return
        # Přepnutí vyžaduje znovunačtení včetně zkontrolovaných.
        if checked and not any(pair.checked for pair in self._pairs):
            self._reload_with_checked(include_checked=True)
            return
        if not checked:
            self._pairs = [pair for pair in self._pairs if not pair.checked]
        self._show_results()

    def _reload_with_checked(self, *, include_checked: bool) -> None:
        try:
            pairs, _cancelled = analyze_control_point_similarities(
                include_checked=include_checked,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._pairs = pairs
        self._show_results()

    def _show_results(self) -> None:
        status = "Analýza byla zrušena." if self._cancelled else "Analýza dokončena."
        self._results_summary.setText(
            f"{status} Nalezeno kandidátních dvojic: {len(self._pairs)}."
        )
        self._results_table.setRowCount(0)

        if not self._pairs:
            self._empty_label.setVisible(True)
            self._results_table.setVisible(False)
        else:
            self._empty_label.setVisible(False)
            self._results_table.setVisible(True)
            self._results_table.setRowCount(len(self._pairs))
            for row, pair in enumerate(self._pairs):
                status_text = "✓ Zkontrolováno" if pair.checked else ""
                similarity = f"{pair.score_percent} % — {pair.match_label}"
                self._results_table.setItem(row, 0, QTableWidgetItem(status_text))
                self._results_table.setItem(row, 1, QTableWidgetItem(similarity))
                self._results_table.setItem(row, 2, QTableWidgetItem(pair.left.text))
                self._results_table.setItem(
                    row, 3, QTableWidgetItem(pair.left.location_label)
                )
                self._results_table.setItem(row, 4, QTableWidgetItem(pair.right.text))
                self._results_table.setItem(
                    row, 5, QTableWidgetItem(pair.right.location_label)
                )
                self._results_table.item(row, 0).setData(
                    Qt.ItemDataRole.UserRole, pair
                )

        self._update_action_buttons()
        self._stack.setCurrentWidget(self._results_page)

    def _selected_pair(self) -> ControlPointSimilarityPair | None:
        rows = self._results_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self._results_table.item(rows[0].row(), 0)
        if item is None:
            return None
        pair = item.data(Qt.ItemDataRole.UserRole)
        return pair if isinstance(pair, ControlPointSimilarityPair) else None

    def _update_action_buttons(self) -> None:
        pair = self._selected_pair()
        enabled = pair is not None
        self._open_first_btn.setEnabled(enabled)
        self._open_second_btn.setEnabled(enabled)
        self._open_both_btn.setEnabled(enabled)
        self._mark_checked_btn.setEnabled(enabled and pair is not None and not pair.checked)
        self._unmark_checked_btn.setEnabled(enabled and pair is not None and pair.checked)

    def _open_selected(self, which: str) -> None:
        pair = self._selected_pair()
        if pair is None:
            return
        if which in {"first", "both"}:
            self._open_control_point(pair.left)
        if which in {"second", "both"}:
            self._open_control_point(pair.right)

    def _mark_selected_checked(self) -> None:
        pair = self._selected_pair()
        if pair is None or pair.checked:
            return
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            (
                "Tato dvojice již nebude při dalších analýzách nabízena.\n\n"
                "Pokračovat?"
            ),
            QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        similarity_checked_pair_service.mark_checked(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            pair.left.composite_id,
            pair.right.composite_id,
        )
        # Odstranit ze seznamu bez nutnosti nové analýzy.
        self._pairs = [
            item
            for item in self._pairs
            if item.normalized_ids != pair.normalized_ids
        ]
        self._show_results()

    def _unmark_selected_checked(self) -> None:
        pair = self._selected_pair()
        if pair is None or not pair.checked:
            return
        similarity_checked_pair_service.unmark_checked(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            pair.left.composite_id,
            pair.right.composite_id,
        )
        updated = replace(pair, checked=False)
        self._pairs = [
            updated if item.normalized_ids == pair.normalized_ids else item
            for item in self._pairs
        ]
        if not self._show_checked_results.isChecked():
            # Po zrušení označení zůstane dvojice ve výsledcích aktuální analýzy.
            pass
        self._show_results()

    def _open_control_point(self, candidate: ControlPointSimilarityCandidate) -> None:
        from moduly.proverky.ui.proverky_knowledge_editor_dialog import (
            ProverkyKnowledgeEditorDialog,
        )

        parsed = parse_control_point_composite_id(candidate.composite_id)
        if parsed is None:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Kontrolní otázku nelze otevřít — neplatný identifikátor.",
            )
            return
        area_id, section_id, item_id = parsed
        dialog = ProverkyKnowledgeEditorDialog(
            self,
            area_id=area_id,
            section_id=section_id,
            control_point_id=item_id,
        )
        exec_maximized(dialog)

    def _back_to_setup(self) -> None:
        self._pairs = []
        self._stack.setCurrentWidget(self._setup_page)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_cancel()
            self._worker.wait(5000)
        super().closeEvent(event)
