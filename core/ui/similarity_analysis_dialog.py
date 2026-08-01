"""Dialog hromadné analýzy podobností (SIMILARITY-2 / SIMILARITY-10)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
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
from core.shared.sluzby.similarity_domain import (
    SCOPE_AUDIT,
    SCOPE_LEGAL,
    SCOPE_MEASURES,
    SCOPE_PBP,
    SCOPE_PROVERKY,
    SCOPE_RISKS,
    SIMILARITY_DOMAINS,
    SIMILARITY_SCOPE_DEFS,
    domain_label,
    estimate_comparison_count,
    estimate_duration_label,
    requires_large_analysis_confirmation,
)
from core.shared.sluzby.similarity_domain_analysis import (
    SimilarityAnalysisPair,
    analyze_domain_similarities,
)
from core.shared.sluzby.similarity_item_collectors import (
    collect_similarity_items,
)
from core.ui.similarity_checked_pairs_dialog import SimilarityCheckedPairsDialog
from core.widgets.dialog_utils import exec_maximized, prepare_work_dialog_maximized
from core.widgets.table_utils import refresh_elided_cell_tooltips
from moduly.proverky.sluzby.control_point_similarity_analysis import (
    ControlPointSimilarityPair,
)
from moduly.proverky.sluzby.control_point_similarity_service import (
    parse_control_point_composite_id,
)

# Sloupce výsledkové tabulky:
# výběr uživatele | podobnost | stav z DB | texty…
_COL_SELECT = 0
_COL_SIMILARITY = 1
_COL_STATUS = 2
_COL_LEFT_TEXT = 3
_COL_LEFT_LOCATION = 4
_COL_RIGHT_TEXT = 5
_COL_RIGHT_LOCATION = 6

# Textové sloupce s ElideRight + tooltipem
_RESULT_TEXT_COLUMNS = (
    _COL_LEFT_TEXT,
    _COL_LEFT_LOCATION,
    _COL_RIGHT_TEXT,
    _COL_RIGHT_LOCATION,
)


class _DomainAnalysisWorker(QThread):
    progress = Signal(int, int, int)  # current, total, found
    finished_ok = Signal(object, bool)  # pairs, cancelled
    failed = Signal(str)

    def __init__(self, scope_a: str, scope_b: str, parent=None) -> None:
        super().__init__(parent)
        self._cancel_requested = False
        self._scope_a = scope_a
        self._scope_b = scope_b

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            pairs, cancelled = analyze_domain_similarities(
                self._scope_a,
                self._scope_b,
                include_checked=False,
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
        auto_start: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Analýza podobností")
        self.setModal(True)
        self.resize(980, 660)

        self._worker: _DomainAnalysisWorker | None = None
        self._pairs: list[SimilarityAnalysisPair | ControlPointSimilarityPair] = []
        self._cancelled = False
        self._closing = False
        self._count_a = 0
        self._count_b = 0
        self._comparison_estimate = 0

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
        self._refresh_scope_estimates()

        if auto_start:
            QTimer.singleShot(0, self._start_analysis)

    def exec(self) -> int:  # noqa: A003
        prepare_work_dialog_maximized(self)
        return super().exec()

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        intro = QLabel(
            "Hromadná kontrola kvality dat. Vyberte nejvýše dvě oblasti. "
            "Stejná oblast hledá duplicity uvnitř; dvě různé oblasti hledají "
            "podobnosti mezi sebou. Zkontrolované dvojice se při analýze "
            "znovu nenabízejí."
        )
        intro.setWordWrap(True)
        intro.setObjectName("InfoText")
        layout.addWidget(intro)

        form = QFormLayout()
        self._scope_a_combo = QComboBox()
        self._scope_b_combo = QComboBox()
        for domain in SIMILARITY_DOMAINS:
            self._scope_a_combo.addItem(domain.label, domain.key)
            self._scope_b_combo.addItem(domain.label, domain.key)
        proverky_index = next(
            (
                i
                for i in range(self._scope_a_combo.count())
                if self._scope_a_combo.itemData(i) == SCOPE_PROVERKY
            ),
            0,
        )
        self._scope_a_combo.setCurrentIndex(proverky_index)
        self._scope_b_combo.setCurrentIndex(proverky_index)
        self._scope_a_combo.currentIndexChanged.connect(self._refresh_scope_estimates)
        self._scope_b_combo.currentIndexChanged.connect(self._refresh_scope_estimates)
        form.addRow("Oblast A", self._scope_a_combo)
        form.addRow("Oblast B", self._scope_b_combo)
        layout.addLayout(form)

        self._estimate_label = QLabel()
        self._estimate_label.setWordWrap(True)
        self._estimate_label.setObjectName("InfoText")
        layout.addWidget(self._estimate_label)
        layout.addStretch()

        buttons = QDialogButtonBox()
        self._start_btn = buttons.addButton(
            "Spustit analýzu", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._manage_checked_setup_btn = buttons.addButton(
            "Správa zkontrolovaných dvojic...",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        close_btn = buttons.addButton(
            "Zavřít", QDialogButtonBox.ButtonRole.RejectRole
        )
        self._start_btn.clicked.connect(self._start_analysis)
        self._manage_checked_setup_btn.clicked.connect(self._open_checked_pairs_manager)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)
        return page

    def _selected_scope_a(self) -> str:
        return str(self._scope_a_combo.currentData() or SCOPE_PROVERKY)

    def _selected_scope_b(self) -> str:
        return str(self._scope_b_combo.currentData() or SCOPE_PROVERKY)

    def _refresh_scope_estimates(self) -> None:
        scope_a = self._selected_scope_a()
        scope_b = self._selected_scope_b()
        try:
            items_a = collect_similarity_items(scope_a, include_inactive=True)
            self._count_a = len(items_a)
            if scope_a == scope_b:
                self._count_b = self._count_a
            else:
                self._count_b = len(
                    collect_similarity_items(scope_b, include_inactive=True)
                )
        except Exception as exc:  # noqa: BLE001
            self._count_a = 0
            self._count_b = 0
            self._comparison_estimate = 0
            self._estimate_label.setText(
                f"Počet položek se nepodařilo načíst.\n{exc}"
            )
            return

        self._comparison_estimate = estimate_comparison_count(
            self._count_a,
            self._count_b,
            same_domain=scope_a == scope_b,
        )
        duration = estimate_duration_label(self._comparison_estimate)
        self._estimate_label.setText(
            f"Počet položek v oblasti A:\n{self._count_a}\n\n"
            f"Počet položek v oblasti B:\n{self._count_b}\n\n"
            f"Bude porovnáno přibližně:\n{self._comparison_estimate} dvojic\n\n"
            f"Orientační doba:\n{duration}"
        )

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

        self._results_counts = QLabel()
        self._results_counts.setWordWrap(True)
        self._results_counts.setObjectName("InfoText")
        layout.addWidget(self._results_counts)

        self._bulk_hint = QLabel(
            "ℹ Zaškrtněte dvojice, které jsou v pořádku (nejde o skutečné duplicity). "
            "Po dokončení je můžete jedním kliknutím skrýt z dalších analýz."
        )
        self._bulk_hint.setWordWrap(True)
        self._bulk_hint.setObjectName("InfoText")
        layout.addWidget(self._bulk_hint)

        self._empty_label = QLabel("Nebyly nalezeny žádné podobné záznamy.")
        self._empty_label.setWordWrap(True)
        self._empty_label.setObjectName("InfoText")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        self._results_table = QTableWidget(0, 7)
        self._results_table.setHorizontalHeaderLabels(
            [
                "",
                "Podobnost",
                "Stav",
                "První otázka",
                "Umístění první",
                "Druhá otázka",
                "Umístění druhé",
            ]
        )
        self._results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._results_table.setWordWrap(False)
        self._results_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._results_table.verticalHeader().setVisible(False)
        header = self._results_table.horizontalHeader()
        header.setSectionResizeMode(_COL_SELECT, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            _COL_SIMILARITY, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_COL_LEFT_TEXT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_LEFT_LOCATION, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_RIGHT_TEXT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            _COL_RIGHT_LOCATION, QHeaderView.ResizeMode.Stretch
        )
        header.sectionResized.connect(self._refresh_result_tooltips)
        self._results_table.itemChanged.connect(self._on_result_item_changed)
        layout.addWidget(self._results_table, 1)

        bulk_row = QHBoxLayout()
        self._bulk_mark_btn = QPushButton("Označit vybrané jako zkontrolované")
        self._bulk_mark_btn.setEnabled(False)
        self._bulk_mark_btn.clicked.connect(self._mark_selected_rows_checked)
        bulk_row.addWidget(self._bulk_mark_btn)
        bulk_row.addStretch()
        layout.addLayout(bulk_row)

        actions = QHBoxLayout()
        self._open_first_btn = QPushButton("Otevřít první")
        self._open_second_btn = QPushButton("Otevřít druhou")
        self._open_both_btn = QPushButton("Otevřít obě")
        self._mark_checked_btn = QPushButton("Označit jako zkontrolované")
        self._open_first_btn.clicked.connect(lambda: self._open_selected("first"))
        self._open_second_btn.clicked.connect(lambda: self._open_selected("second"))
        self._open_both_btn.clicked.connect(lambda: self._open_selected("both"))
        self._mark_checked_btn.clicked.connect(self._mark_selected_checked)
        for btn in (
            self._open_first_btn,
            self._open_second_btn,
            self._open_both_btn,
            self._mark_checked_btn,
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
        self._manage_checked_results_btn = buttons.addButton(
            "Správa zkontrolovaných dvojic...",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        close_btn = buttons.addButton(
            "Zavřít", QDialogButtonBox.ButtonRole.RejectRole
        )
        again_btn.clicked.connect(self._back_to_setup)
        self._manage_checked_results_btn.clicked.connect(
            self._open_checked_pairs_manager
        )
        close_btn.clicked.connect(self._request_close)
        layout.addWidget(buttons)
        return page

    def _start_analysis(self) -> None:
        scope_a = self._selected_scope_a()
        scope_b = self._selected_scope_b()
        self._refresh_scope_estimates()

        if requires_large_analysis_confirmation(self._comparison_estimate):
            message = QMessageBox(self)
            message.setWindowTitle(self.windowTitle())
            message.setIcon(QMessageBox.Icon.Warning)
            message.setText(
                "Vybraná analýza může trvat delší dobu.\n\n"
                "Přesto pokračovat?"
            )
            continue_btn = message.addButton(
                "Pokračovat", QMessageBox.ButtonRole.AcceptRole
            )
            cancel_btn = message.addButton(
                "Zrušit", QMessageBox.ButtonRole.RejectRole
            )
            message.setDefaultButton(cancel_btn)
            message.exec()
            if message.clickedButton() is not continue_btn:
                return

        self._pairs = []
        self._cancelled = False

        label_a = domain_label(scope_a)
        label_b = domain_label(scope_b)
        if scope_a == scope_b:
            self._progress_scope_label.setText(label_a)
        else:
            self._progress_scope_label.setText(f"{label_a} ↔ {label_b}")

        self._progress_bar.setValue(0)
        self._progress_count_label.setText("0 / 0")
        self._progress_found_label.setText("Nalezeno kandidátů: 0")
        self._cancel_btn.setEnabled(True)
        self._stack.setCurrentWidget(self._progress_page)

        self._worker = _DomainAnalysisWorker(scope_a, scope_b, parent=self)
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

    def _open_checked_pairs_manager(self) -> None:
        SimilarityCheckedPairsDialog(self).exec()

    def _show_results(self) -> None:
        status = "Analýza byla zrušena." if self._cancelled else "Analýza dokončena."
        self._results_summary.setText(status)
        self._results_table.blockSignals(True)
        self._results_table.setRowCount(0)

        # Analýza zobrazuje pouze nevyřešené dvojice (SIMILARITY-UX-8).
        pairs = [pair for pair in self._pairs if not pair.checked]
        self._pairs = pairs

        has_pairs = bool(pairs)
        self._empty_label.setVisible(not has_pairs)
        self._results_table.setVisible(has_pairs)
        self._bulk_hint.setVisible(has_pairs)
        self._bulk_mark_btn.setVisible(has_pairs)

        if has_pairs:
            self._results_table.setRowCount(len(pairs))
            for row, pair in enumerate(pairs):
                # Checkbox = pouze aktuální výběr uživatele (nikdy stav z DB).
                select_item = QTableWidgetItem()
                select_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                select_item.setCheckState(Qt.CheckState.Unchecked)
                select_item.setFlags(
                    Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                )
                select_item.setToolTip(
                    "Tuto dvojici chci nyní hromadně označit jako zkontrolovanou."
                )

                similarity = f"{pair.score_percent} % — {pair.match_label}"
                status_item = QTableWidgetItem("")
                status_item.setData(Qt.ItemDataRole.UserRole, pair)

                self._results_table.setItem(row, _COL_SELECT, select_item)
                self._results_table.setItem(
                    row, _COL_SIMILARITY, QTableWidgetItem(similarity)
                )
                self._results_table.setItem(row, _COL_STATUS, status_item)
                self._results_table.setItem(
                    row, _COL_LEFT_TEXT, QTableWidgetItem(pair.left.text)
                )
                self._results_table.setItem(
                    row, _COL_LEFT_LOCATION, QTableWidgetItem(pair.left.location_label)
                )
                self._results_table.setItem(
                    row, _COL_RIGHT_TEXT, QTableWidgetItem(pair.right.text)
                )
                self._results_table.setItem(
                    row,
                    _COL_RIGHT_LOCATION,
                    QTableWidgetItem(pair.right.location_label),
                )

        self._results_table.blockSignals(False)
        self._update_counts()
        self._update_action_buttons()
        self._stack.setCurrentWidget(self._results_page)
        self._refresh_result_tooltips()

    def _refresh_result_tooltips(self, *_args) -> None:
        refresh_elided_cell_tooltips(self._results_table, _RESULT_TEXT_COLUMNS)

    def _on_result_item_changed(self, item: QTableWidgetItem) -> None:
        if item is None or item.column() != _COL_SELECT:
            return
        self._update_counts()

    def _selected_row_indexes(self) -> list[int]:
        selected: list[int] = []
        for row in range(self._results_table.rowCount()):
            item = self._results_table.item(row, _COL_SELECT)
            if item is None:
                continue
            if not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                continue
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(row)
        return selected

    def _pair_at_row(self, row: int):
        item = self._results_table.item(row, _COL_STATUS)
        if item is None:
            return None
        pair = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(pair, (SimilarityAnalysisPair, ControlPointSimilarityPair)):
            return pair
        return None

    def _update_counts(self) -> None:
        total = len(self._pairs)
        selected = len(self._selected_row_indexes())
        remaining = total - selected
        self._results_counts.setText(
            f"Celkem nalezeno: {total}\n"
            f"Vybráno: {selected}\n"
            f"Zbývá k posouzení: {remaining}"
        )
        self._bulk_mark_btn.setEnabled(selected > 0)

    def _selected_pair(self):
        rows = self._results_table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._pair_at_row(rows[0].row())

    def _update_action_buttons(self) -> None:
        pair = self._selected_pair()
        enabled = pair is not None
        self._open_first_btn.setEnabled(enabled)
        self._open_second_btn.setEnabled(enabled)
        self._open_both_btn.setEnabled(enabled)
        self._mark_checked_btn.setEnabled(enabled)
        self._update_counts()

    def _open_selected(self, which: str) -> None:
        pair = self._selected_pair()
        if pair is None:
            return
        if which in {"first", "both"}:
            self._open_similarity_item(pair.left)
        if which in {"second", "both"}:
            self._open_similarity_item(pair.right)

    def _pair_entity_type(self, pair) -> str:
        entity_type = getattr(pair, "pair_entity_type", None)
        if entity_type:
            return str(entity_type)
        return SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT

    def _mark_selected_checked(self) -> None:
        pair = self._selected_pair()
        if pair is None:
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
            self._pair_entity_type(pair),
            pair.left.composite_id,
            pair.right.composite_id,
        )
        self._pairs = [
            item
            for item in self._pairs
            if item.normalized_ids != pair.normalized_ids
        ]
        self._show_results()

    def _mark_selected_rows_checked(self) -> None:
        rows = self._selected_row_indexes()
        if not rows:
            return

        pairs = []
        for row in rows:
            pair = self._pair_at_row(row)
            if pair is None:
                continue
            pairs.append(pair)
        if not pairs:
            return

        marked_ids = {pair.normalized_ids for pair in pairs}
        for pair in pairs:
            similarity_checked_pair_service.mark_checked(
                self._pair_entity_type(pair),
                pair.left.composite_id,
                pair.right.composite_id,
            )
        self._pairs = [
            item for item in self._pairs if item.normalized_ids not in marked_ids
        ]
        self._show_results()

    def _open_similarity_item(self, item) -> None:
        entity_type = getattr(item, "entity_type", SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT)
        composite_id = str(getattr(item, "composite_id", "") or "")
        prefix = f"{SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT}::"
        if composite_id.startswith(prefix):
            composite_id = composite_id[len(prefix) :]
            entity_type = SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT

        if entity_type != SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT:
            QMessageBox.information(
                self,
                self.windowTitle(),
                "Otevření položek této oblasti bude doplněno v dalším sprintu.",
            )
            return

        from moduly.proverky.ui.proverky_knowledge_editor_dialog import (
            ProverkyKnowledgeEditorDialog,
        )

        parsed = parse_control_point_composite_id(composite_id)
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

    def _has_pending_bulk_selection(self) -> bool:
        return bool(self._selected_row_indexes())

    def _prompt_pending_bulk_selection_close(self) -> str:
        """Vrátí ``mark_and_close`` / ``discard`` / ``cancel``."""
        count = len(self._selected_row_indexes())
        message = QMessageBox(self)
        message.setWindowTitle(self.windowTitle())
        message.setIcon(QMessageBox.Icon.Question)
        message.setText(
            f"Máte označeno {count} dvojic jako správné "
            f"(nejde o skutečné duplicity), ale ještě nebyly označeny "
            f"jako zkontrolované.\n\n"
            f"Co chcete udělat?"
        )
        mark_btn = message.addButton(
            "Označit a zavřít",
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard_btn = message.addButton(
            "Zavřít bez uložení",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_btn = message.addButton(
            "Zrušit",
            QMessageBox.ButtonRole.RejectRole,
        )
        message.setDefaultButton(cancel_btn)
        message.exec()

        clicked = message.clickedButton()
        if clicked is mark_btn:
            return "mark_and_close"
        if clicked is discard_btn:
            return "discard"
        return "cancel"

    def _prepare_close_with_pending_selection(self) -> bool:
        """True = smí se zavřít. False = zůstat otevřený."""
        if not self._has_pending_bulk_selection():
            return True
        decision = self._prompt_pending_bulk_selection_close()
        if decision == "cancel":
            return False
        if decision == "mark_and_close":
            self._mark_selected_rows_checked()
        # discard: nic neukládat, jen zavřít
        return True

    def _request_close(self) -> None:
        if self._closing:
            self.accept()
            return
        if not self._prepare_close_with_pending_selection():
            return
        self._closing = True
        self._stop_worker_if_running()
        self.accept()

    def _stop_worker_if_running(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_cancel()
            self._worker.wait(5000)

    def reject(self) -> None:
        if self._closing:
            super().reject()
            return
        if not self._prepare_close_with_pending_selection():
            return
        self._closing = True
        self._stop_worker_if_running()
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._closing:
            self._stop_worker_if_running()
            super().closeEvent(event)
            return
        if not self._prepare_close_with_pending_selection():
            event.ignore()
            return
        self._closing = True
        self._stop_worker_if_running()
        super().closeEvent(event)
