"""Dialog hromadné analýzy podobností (SIMILARITY-2 / SIMILARITY-10)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
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
    SCOPE_PROVERKY,
    SIMILARITY_DOMAINS,
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
from core.shared.sluzby.similarity_item_opener import (
    SimilarityItemOpenError,
    open_similarity_item,
)
from core.shared.sluzby.similarity_location_format import (
    format_similarity_location,
    similarity_location_root,
)
from core.ui.similarity_checked_pairs_dialog import SimilarityCheckedPairsDialog
from core.widgets.chunked_ui_pump import ChunkedUiPump
from core.widgets.dialog_utils import prepare_work_dialog_maximized
from core.widgets.long_operation_dialog import (
    DEFAULT_DELAY_MS,
    LongOperationDialog,
)
from core.widgets.long_operation_runner import (
    LongOperationContext,
    LongOperationRunner,
)
from core.widgets.info_tooltip import set_widget_tooltip
from core.widgets.table_utils import apply_cell_tooltip, refresh_elided_cell_tooltips
from moduly.proverky.sluzby.control_point_similarity_analysis import (
    ControlPointSimilarityPair,
)

logger = logging.getLogger(__name__)

# Sloupce výsledkové tabulky:
# výběr uživatele | podobnost | stav z DB | texty…
_COL_SELECT = 0
_COL_SIMILARITY = 1
_COL_STATUS = 2
_COL_LEFT_TEXT = 3
_COL_LEFT_LOCATION = 4
_COL_RIGHT_TEXT = 5
_COL_RIGHT_LOCATION = 6

# Textové sloupce s ElideRight + tooltipem podle zkrácení
_RESULT_QUESTION_COLUMNS = (
    _COL_LEFT_TEXT,
    _COL_RIGHT_TEXT,
)
_RESULT_LOCATION_COLUMNS = (
    _COL_LEFT_LOCATION,
    _COL_RIGHT_LOCATION,
)
_RESULT_TEXT_COLUMNS = _RESULT_QUESTION_COLUMNS + _RESULT_LOCATION_COLUMNS

PHASE_ANALYZING = "Analyzuji podobnosti…"
PHASE_PREPARING_RESULTS = "Připravuji výsledky k zobrazení…"
PREPARING_CANCELLED_MESSAGE = "Příprava výsledků byla zrušena."
RESULT_TABLE_BATCH_SIZE = 50

FLOW_IDLE = "idle"
FLOW_ANALYZING = "analyzing"
FLOW_PREPARING_RESULTS = "preparing_results"
FLOW_RESULTS_READY = "results_ready"
FLOW_CANCELLED = "cancelled"
FLOW_FAILED = "failed"


class LocationElideLeftDelegate(QStyledItemDelegate):
    """Kreslí text sloupce Umístění se zkrácením zleva (konec cesty zůstane vidět)."""

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        super().initStyleOption(option, index)
        option.textElideMode = Qt.TextElideMode.ElideLeft


class _ElidingLabel(QLabel):
    """Jednořádkový popisek: dlouhý text zkrátí a dá celý název do tooltipu."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setWordWrap(False)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

    def set_full_text(self, text: str) -> None:
        self._full_text = str(text or "")
        self._apply_elide()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        available = max(0, self.contentsRect().width())
        elided = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            available,
        )
        if super().text() != elided:
            super().setText(elided)
        if elided != self._full_text and self._full_text.strip():
            set_widget_tooltip(self, self._full_text)
        else:
            self.setToolTip("")


@dataclass(frozen=True)
class SimilarityAnalysisSnapshot:
    """Čistý vstup workeru — bez dialogu a bez Qt widgetů."""

    scope_a: str
    scope_b: str
    include_checked: bool = False


@dataclass
class SimilarityAnalysisWorkResult:
    pairs: list
    cancelled: bool


def run_similarity_analysis(
    ctx: LongOperationContext,
    snapshot: SimilarityAnalysisSnapshot,
) -> SimilarityAnalysisWorkResult:
    """Výpočet podobností mimo GUI vlákno. Sort a mapování DTO zůstává ve službě."""
    ctx.set_phase(PHASE_ANALYZING)

    def on_progress(current: int, total: int, found: int) -> None:
        ctx.set_progress(current, total)
        ctx.set_status(f"Nalezeno kandidátů: {found}")

    pairs, cancelled = analyze_domain_similarities(
        snapshot.scope_a,
        snapshot.scope_b,
        include_checked=snapshot.include_checked,
        progress_callback=on_progress,
        should_cancel=ctx.is_cancel_requested,
    )
    # 100 % porovnávací smyčky ≠ hotové zobrazení.
    ctx.set_phase(PHASE_PREPARING_RESULTS, indeterminate=True)
    ctx.set_status("")
    return SimilarityAnalysisWorkResult(pairs=list(pairs), cancelled=bool(cancelled))


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

        self._pairs: list[SimilarityAnalysisPair | ControlPointSimilarityPair] = []
        self._cancelled = False
        self._closing = False
        self._close_when_idle = False
        self._count_a = 0
        self._count_b = 0
        self._comparison_estimate = 0
        self._flow_state = FLOW_IDLE
        self._fill_row = 0
        self._suspend_resize_tooltips = False
        self._progress_delay_ms = DEFAULT_DELAY_MS
        self._result_batch_size = RESULT_TABLE_BATCH_SIZE
        self._progress_dialog: LongOperationDialog | None = None
        self._header_resize_connected = False
        self._result_snapshot: SimilarityAnalysisSnapshot | None = None
        self._location_delegate = LocationElideLeftDelegate(self)

        self._runner = LongOperationRunner(self)
        self._pump = ChunkedUiPump(self)
        self._runner.succeeded.connect(self._on_runner_succeeded)
        self._runner.cancelled.connect(self._on_runner_cancelled)
        self._runner.failed.connect(self._on_runner_failed)
        self._runner.finished.connect(self._on_runner_finished)
        self._pump.progress.connect(self._on_pump_progress)
        self._pump.succeeded.connect(self._on_pump_succeeded)
        self._pump.cancelled.connect(self._on_pump_cancelled)
        self._pump.failed.connect(self._on_pump_failed)

        root = QVBoxLayout(self)
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        self._setup_page = self._build_setup_page()
        self._results_page = self._build_results_page()
        self._stack.addWidget(self._setup_page)
        self._stack.addWidget(self._results_page)

        self._stack.setCurrentWidget(self._setup_page)
        self._refresh_scope_estimates()
        self._apply_controls_for_state()

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

        self._scope_info_row = QWidget()
        scope_row = QHBoxLayout(self._scope_info_row)
        scope_row.setContentsMargins(0, 0, 0, 0)
        self._scope_first_label = _ElidingLabel()
        self._scope_first_label.setObjectName("InfoText")
        self._scope_second_label = _ElidingLabel()
        self._scope_second_label.setObjectName("InfoText")
        scope_row.addWidget(self._scope_first_label, 1)
        scope_row.addWidget(self._scope_second_label, 1)
        layout.addWidget(self._scope_info_row)
        self._hide_scope_headings()

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
        self._results_table.setItemDelegateForColumn(
            _COL_LEFT_LOCATION, self._location_delegate
        )
        self._results_table.setItemDelegateForColumn(
            _COL_RIGHT_LOCATION, self._location_delegate
        )
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
        self._again_btn = buttons.addButton(
            "Nová analýza", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._manage_checked_results_btn = buttons.addButton(
            "Správa zkontrolovaných dvojic...",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        close_btn = buttons.addButton(
            "Zavřít", QDialogButtonBox.ButtonRole.RejectRole
        )
        self._again_btn.clicked.connect(self._back_to_setup)
        self._manage_checked_results_btn.clicked.connect(
            self._open_checked_pairs_manager
        )
        close_btn.clicked.connect(self._request_close)
        layout.addWidget(buttons)
        return page

    def _is_busy(self) -> bool:
        return self._flow_state in {FLOW_ANALYZING, FLOW_PREPARING_RESULTS}

    def _results_are_ready(self) -> bool:
        return self._flow_state == FLOW_RESULTS_READY

    def _apply_controls_for_state(self) -> None:
        busy = self._is_busy()
        ready = self._results_are_ready()
        self._start_btn.setEnabled(not busy)
        self._scope_a_combo.setEnabled(not busy)
        self._scope_b_combo.setEnabled(not busy)
        self._manage_checked_setup_btn.setEnabled(not busy)
        self._again_btn.setEnabled(not busy)
        self._manage_checked_results_btn.setEnabled(not busy)
        if not ready:
            self._open_first_btn.setEnabled(False)
            self._open_second_btn.setEnabled(False)
            self._open_both_btn.setEnabled(False)
            self._mark_checked_btn.setEnabled(False)
            self._bulk_mark_btn.setEnabled(False)
            self._results_table.setEnabled(not busy)
        else:
            self._results_table.setEnabled(True)
            self._update_action_buttons()

    def _set_flow_state(self, state: str) -> None:
        self._flow_state = state
        self._apply_controls_for_state()

    def _ensure_progress_dialog(self) -> LongOperationDialog:
        dialog = self._progress_dialog
        if dialog is not None:
            return dialog
        dialog = LongOperationDialog(
            self,
            title=self.windowTitle(),
            runner=self._runner,
            delay_ms=self._progress_delay_ms,
            close_on_success=False,
        )
        dialog.cancel_requested.connect(self._on_progress_cancel_requested)
        self._progress_dialog = dialog
        return dialog

    def _complete_progress_dialog(self) -> None:
        dialog = self._progress_dialog
        if dialog is None:
            return
        dialog.complete()

    def _start_analysis(self) -> None:
        if self._is_busy():
            return
        if self._runner.is_running() or self._pump.is_running():
            return

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
        self._close_when_idle = False
        self._fill_row = 0
        self._hide_scope_headings()
        self._set_flow_state(FLOW_ANALYZING)
        self._stack.setCurrentWidget(self._setup_page)

        snapshot = SimilarityAnalysisSnapshot(
            scope_a=scope_a,
            scope_b=scope_b,
            include_checked=False,
        )
        self._result_snapshot = snapshot
        self._ensure_progress_dialog()
        started = self._runner.start(run_similarity_analysis, snapshot)
        if not started:
            self._set_flow_state(FLOW_IDLE)
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Analýzu se nepodařilo spustit, protože jiná operace ještě běží.",
            )

    def _on_progress_cancel_requested(self) -> None:
        if self._flow_state == FLOW_ANALYZING:
            self._runner.request_cancel()
            return
        if self._flow_state == FLOW_PREPARING_RESULTS:
            self._pump.request_cancel()

    def _on_runner_succeeded(self, result: object) -> None:
        if self._flow_state != FLOW_ANALYZING:
            return
        work = result if isinstance(result, SimilarityAnalysisWorkResult) else None
        pairs = list(work.pairs) if work is not None else list(result or [])
        cancelled = bool(work.cancelled) if work is not None else False
        self._pairs = pairs
        self._cancelled = cancelled

        if self._close_when_idle:
            self._discard_partial_table()
            self._complete_progress_dialog()
            self._set_flow_state(FLOW_CANCELLED)
            self._finish_close()
            return

        self._begin_prepare_results(pairs)

    def _on_runner_cancelled(self) -> None:
        if self._flow_state != FLOW_ANALYZING:
            return
        self._complete_progress_dialog()
        if self._close_when_idle:
            self._set_flow_state(FLOW_CANCELLED)
            self._finish_close()
            return
        self._cancelled = True
        self._pairs = []
        self._set_flow_state(FLOW_CANCELLED)
        self._show_cancelled_without_results()

    def _on_runner_failed(self, message: str) -> None:
        logger.error("Analýza podobností selhala: %s", message)
        self._complete_progress_dialog()
        self._discard_partial_table()
        self._set_flow_state(FLOW_FAILED)
        if self._close_when_idle:
            self._finish_close()
            return
        QMessageBox.critical(
            self,
            self.windowTitle(),
            f"Analýza selhala.\n\n{message}",
        )
        self._hide_scope_headings()
        self._stack.setCurrentWidget(self._setup_page)
        self._set_flow_state(FLOW_IDLE)

    def _on_runner_finished(self) -> None:
        self._apply_controls_for_state()

    def _visible_result_pairs(self, pairs: list) -> list:
        return [pair for pair in pairs if not pair.checked]

    def _begin_prepare_results(self, pairs: list) -> None:
        visible = self._visible_result_pairs(pairs)
        self._pairs = visible
        self._set_flow_state(FLOW_PREPARING_RESULTS)
        self._prepare_results_table_shell(visible)

        progress = self._progress_dialog
        if progress is not None:
            progress.begin_followup()
            progress.set_phase(PHASE_PREPARING_RESULTS)
            progress.set_status("")
            progress.set_progress(0, len(visible) if visible else 0)

        if not visible:
            self._on_pump_succeeded()
            return

        self._fill_row = 0
        self._pump.start(
            visible,
            self._consume_result_batch,
            batch_size=self._result_batch_size,
        )

    def _prepare_results_table_shell(self, pairs: list) -> None:
        header = self._results_table.horizontalHeader()
        if self._header_resize_connected:
            try:
                header.sectionResized.disconnect(self._on_result_section_resized)
            except (TypeError, RuntimeError):
                pass
            self._header_resize_connected = False

        self._suspend_resize_tooltips = True
        self._results_table.blockSignals(True)
        self._results_table.setUpdatesEnabled(False)
        self._results_table.setRowCount(0)
        self._results_table.setRowCount(len(pairs))
        self._results_table.clearSelection()
        self._fill_row = 0

    def _consume_result_batch(self, batch) -> None:
        for pair in batch:
            self._fill_result_row(self._fill_row, pair)
            self._fill_row += 1

    def _fill_result_row(self, row: int, pair) -> None:
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

        scope_a, scope_b = self._result_scope_keys()
        left_full = pair.left.location_label
        right_full = pair.right.location_label
        left_visible = self._visible_location(left_full, scope_a)
        right_visible = self._visible_location(right_full, scope_b)

        left_text = QTableWidgetItem(pair.left.text)
        left_location = QTableWidgetItem(left_visible)
        right_text = QTableWidgetItem(pair.right.text)
        right_location = QTableWidgetItem(right_visible)

        self._results_table.setItem(row, _COL_SELECT, select_item)
        self._results_table.setItem(row, _COL_SIMILARITY, QTableWidgetItem(similarity))
        self._results_table.setItem(row, _COL_STATUS, status_item)
        self._results_table.setItem(row, _COL_LEFT_TEXT, left_text)
        self._results_table.setItem(row, _COL_LEFT_LOCATION, left_location)
        self._results_table.setItem(row, _COL_RIGHT_TEXT, right_text)
        self._results_table.setItem(row, _COL_RIGHT_LOCATION, right_location)

        apply_cell_tooltip(left_text, pair.left.text)
        apply_cell_tooltip(right_text, pair.right.text)
        set_widget_tooltip(left_location, left_full)
        set_widget_tooltip(right_location, right_full)

    def _restore_results_table_after_fill(self) -> None:
        self._results_table.blockSignals(False)
        self._results_table.setUpdatesEnabled(True)
        self._suspend_resize_tooltips = False
        header = self._results_table.horizontalHeader()
        if not self._header_resize_connected:
            header.sectionResized.connect(self._on_result_section_resized)
            self._header_resize_connected = True

    def _on_result_section_resized(self, *_args) -> None:
        if self._suspend_resize_tooltips:
            return
        if self._flow_state != FLOW_RESULTS_READY:
            return
        # Během počátečního plnění se nespouští. Po hotových výsledcích
        # nespouštíme celotabulkový průchod — tooltipy jsou v dávkách.

    def _on_pump_progress(self, processed: int, total: int) -> None:
        if self._flow_state != FLOW_PREPARING_RESULTS:
            return
        progress = self._progress_dialog
        if progress is None:
            return
        progress.set_progress(processed, total)

    def _on_pump_succeeded(self) -> None:
        if self._flow_state != FLOW_PREPARING_RESULTS:
            return
        self._restore_results_table_after_fill()
        if self._close_when_idle:
            self._complete_progress_dialog()
            self._set_flow_state(FLOW_CANCELLED)
            self._finish_close()
            return
        self._complete_progress_dialog()
        self._present_results_page()
        self._set_flow_state(FLOW_RESULTS_READY)

    def _on_pump_cancelled(self) -> None:
        if self._flow_state != FLOW_PREPARING_RESULTS:
            return
        self._discard_partial_table()
        self._complete_progress_dialog()
        self._cancelled = True
        self._set_flow_state(FLOW_CANCELLED)
        if self._close_when_idle:
            self._finish_close()
            return
        self._show_preparing_cancelled()

    def _on_pump_failed(self, message: str) -> None:
        logger.error("Příprava výsledků podobností selhala: %s", message)
        self._discard_partial_table()
        self._complete_progress_dialog()
        self._set_flow_state(FLOW_FAILED)
        if self._close_when_idle:
            self._finish_close()
            return
        QMessageBox.critical(
            self,
            self.windowTitle(),
            f"Příprava výsledků selhala.\n\n{message}",
        )
        self._hide_scope_headings()
        self._stack.setCurrentWidget(self._setup_page)
        self._set_flow_state(FLOW_IDLE)

    def _discard_partial_table(self) -> None:
        self._results_table.blockSignals(True)
        self._results_table.setRowCount(0)
        self._results_table.blockSignals(False)
        self._results_table.setUpdatesEnabled(True)
        self._suspend_resize_tooltips = False
        self._pairs = []
        self._fill_row = 0

    def _show_preparing_cancelled(self) -> None:
        self._pairs = []
        self._results_summary.setText(PREPARING_CANCELLED_MESSAGE)
        self._results_counts.setText(
            "Celkem nalezeno: 0\nVybráno: 0\nZbývá k posouzení: 0"
        )
        self._empty_label.setText(PREPARING_CANCELLED_MESSAGE)
        self._empty_label.setVisible(True)
        self._results_table.setVisible(False)
        self._bulk_hint.setVisible(False)
        self._bulk_mark_btn.setVisible(False)
        self._hide_scope_headings()
        self._stack.setCurrentWidget(self._results_page)
        self._apply_controls_for_state()

    def _show_cancelled_without_results(self) -> None:
        self._show_preparing_cancelled()
        self._results_summary.setText("Analýza byla zrušena.")
        self._empty_label.setText("Analýza byla zrušena.")

    def _present_results_page(self) -> None:
        status = "Analýza byla zrušena." if self._cancelled else "Analýza dokončena."
        self._results_summary.setText(status)
        pairs = self._pairs
        has_pairs = bool(pairs)
        self._empty_label.setText("Nebyly nalezeny žádné podobné záznamy.")
        self._empty_label.setVisible(not has_pairs)
        self._results_table.setVisible(has_pairs)
        self._bulk_hint.setVisible(has_pairs)
        self._bulk_mark_btn.setVisible(has_pairs)
        self._update_counts()
        if self._cancelled:
            self._hide_scope_headings()
        else:
            self._update_scope_headings()
        self._stack.setCurrentWidget(self._results_page)

    def _visible_location(self, full_path: str, scope_key: str) -> str:
        path = str(full_path or "").strip()
        heading_root = domain_label(scope_key)
        formatted = format_similarity_location(path, heading_root)
        if formatted != path:
            return formatted
        location_root = similarity_location_root(scope_key)
        if location_root != heading_root:
            return format_similarity_location(path, location_root)
        return formatted

    def _result_scope_keys(self) -> tuple[str, str]:
        snapshot = self._result_snapshot
        if snapshot is not None:
            return snapshot.scope_a, snapshot.scope_b
        return self._selected_scope_a(), self._selected_scope_b()

    def _hide_scope_headings(self) -> None:
        self._scope_first_label.set_full_text("")
        self._scope_second_label.set_full_text("")
        self._scope_info_row.setVisible(False)

    def _update_scope_headings(self) -> None:
        # Názvy ze snapshotu dokončené analýzy — stejný kořen jako v location_label
        # (ne aktuální combobox a ne domain_label, který u auditů/prověrek
        # neodpovídá prefixu cesty).
        scope_a, scope_b = self._result_scope_keys()
        name_a = similarity_location_root(scope_a)
        name_b = similarity_location_root(scope_b)
        self._scope_first_label.set_full_text(f"První otázka: {name_a}")
        self._scope_second_label.set_full_text(f"Druhá otázka: {name_b}")
        self._scope_info_row.setVisible(True)

    def _open_checked_pairs_manager(self) -> None:
        if self._is_busy():
            return
        SimilarityCheckedPairsDialog(self).exec()

    def _show_results(self) -> None:
        """Synchronní naplnění tabulky (testy a přestavba po označení)."""
        pairs = self._visible_result_pairs(self._pairs)
        self._pairs = pairs
        self._prepare_results_table_shell(pairs)
        self._fill_row = 0
        for pair in pairs:
            self._fill_result_row(self._fill_row, pair)
            self._fill_row += 1
        self._restore_results_table_after_fill()
        self._present_results_page()
        self._set_flow_state(FLOW_RESULTS_READY)

    def _refresh_result_tooltips(self, *_args) -> None:
        if self._suspend_resize_tooltips:
            return
        refresh_elided_cell_tooltips(self._results_table, _RESULT_QUESTION_COLUMNS)

    def _on_result_item_changed(self, item: QTableWidgetItem) -> None:
        if not self._results_are_ready():
            return
        if item is None or item.column() != _COL_SELECT:
            return
        self._update_counts()

    def _selected_row_indexes(self) -> list[int]:
        if not self._results_are_ready():
            return []
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
        if not self._results_are_ready():
            return None
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
        self._bulk_mark_btn.setEnabled(self._results_are_ready() and selected > 0)

    def _selected_pair(self):
        if not self._results_are_ready():
            return None
        rows = self._results_table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._pair_at_row(rows[0].row())

    def _update_action_buttons(self) -> None:
        pair = self._selected_pair()
        enabled = pair is not None and self._results_are_ready()
        self._open_first_btn.setEnabled(enabled)
        self._open_second_btn.setEnabled(enabled)
        self._open_both_btn.setEnabled(enabled)
        self._mark_checked_btn.setEnabled(enabled)
        self._update_counts()

    def _open_selected(self, which: str) -> None:
        if not self._results_are_ready():
            return
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
        if not self._results_are_ready():
            return
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
        if not self._results_are_ready():
            return
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
        try:
            open_similarity_item(self, item)
        except SimilarityItemOpenError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
        except Exception as error:  # noqa: BLE001
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"Položku se nepodařilo otevřít.\n\n{error}",
            )

    def _back_to_setup(self) -> None:
        if self._is_busy():
            return
        self._pairs = []
        self._cancelled = False
        self._result_snapshot = None
        self._results_table.setRowCount(0)
        self._hide_scope_headings()
        self._set_flow_state(FLOW_IDLE)
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
        if self._is_busy():
            return True
        if not self._has_pending_bulk_selection():
            return True
        decision = self._prompt_pending_bulk_selection_close()
        if decision == "cancel":
            return False
        if decision == "mark_and_close":
            self._mark_selected_rows_checked()
        return True

    def _request_operation_cancel(self) -> None:
        if self._flow_state == FLOW_ANALYZING:
            self._runner.request_cancel()
            return
        if self._flow_state == FLOW_PREPARING_RESULTS:
            self._pump.request_cancel()

    def _finish_close(self) -> None:
        self._closing = True
        self._complete_progress_dialog()
        self.accept()

    def _request_close_or_cancel(self) -> bool:
        """True = dialog se smí hned zavřít. False = čeká na zrušení operace."""
        if self._closing:
            return True
        if self._is_busy():
            self._close_when_idle = True
            self._request_operation_cancel()
            return False
        if not self._prepare_close_with_pending_selection():
            return False
        self._closing = True
        return True

    def _request_close(self) -> None:
        if self._request_close_or_cancel():
            self.accept()

    def reject(self) -> None:
        if self._request_close_or_cancel():
            super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._closing:
            super().closeEvent(event)
            return
        if self._is_busy():
            self._close_when_idle = True
            self._request_operation_cancel()
            event.ignore()
            return
        if not self._prepare_close_with_pending_selection():
            event.ignore()
            return
        self._closing = True
        super().closeEvent(event)
