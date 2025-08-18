# ui/viewer.py
from __future__ import annotations

from typing import Optional, Dict

from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore

import control
from pipeline.context import PipelineContext
from pipeline.stages.fetch_stage import run_fetch_stage
from pipeline.stages.process_stage import run_process_stage
from pipeline.stages.result_stage import run_result_stage
from registries.pipeline_registry import apply_pipeline_registry


class ValResultsWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AmpyFin — Val Results (Live)")
        self.resize(1000, 620)

        self._paused = False
        self._last_strategy_names: list[str] = []

        main = QtWidgets.QVBoxLayout(self)

        # --- Top bar ---
        top_bar = QtWidgets.QHBoxLayout()
        self._meta = QtWidgets.QLabel("Generated at: -")
        self._status = QtWidgets.QLabel("Status: idle")
        self._status.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        top_bar.addWidget(self._meta, 2)
        top_bar.addWidget(self._status, 1)
        main.addLayout(top_bar)

        # --- Controls ---
        controls = QtWidgets.QHBoxLayout()
        self._btn_refresh = QtWidgets.QPushButton("Refresh now")
        self._btn_pause = QtWidgets.QPushButton("Pause updates")
        self._interval_spin = QtWidgets.QSpinBox()
        self._interval_spin.setRange(5, 3600)
        self._interval_spin.setValue(int(getattr(control, "LOOP_SLEEP_SECONDS", 180)))
        self._interval_spin.setSuffix(" s")
        controls.addWidget(self._btn_refresh)
        controls.addWidget(self._btn_pause)
        controls.addStretch(1)
        controls.addWidget(QtWidgets.QLabel("Update every:"))
        controls.addWidget(self._interval_spin)
        main.addLayout(controls)

        # --- Table ---
        self._table = QtWidgets.QTableWidget(0, 0)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        # Prevent loading cursor on hover
        self._table.setCursor(QtCore.Qt.ArrowCursor)
        main.addWidget(self._table)

        # Connect controls
        self._btn_refresh.clicked.connect(self.trigger_manual_refresh)
        self._btn_pause.clicked.connect(self.toggle_pause)
        self._interval_spin.valueChanged.connect(self._on_interval_changed)

        # Timer (configured by gui_run_continuous)
        self._timer: Optional[QtCore.QTimer] = None

    # -------- helpers --------
    def _fmt(self, v: Optional[float], p: int = 2) -> str:
        return f"{v:.{p}f}" if isinstance(v, (int, float)) else "-"

    def _colorize_discount_cell(self, item: QtWidgets.QTableWidgetItem, discount: Optional[float]) -> None:
        """
        Color-code the discount% cell:
          >= +20%  : strong green
           0%..20% : soft green
           <   0%  : soft red
        """
        if not isinstance(discount, (int, float)):
            return
        if discount >= 0.20:
            item.setBackground(QtGui.QColor(198, 239, 206))  # green strong
            item.setForeground(QtGui.QBrush(QtGui.QColor(0, 97, 0)))
        elif discount >= 0.0:
            item.setBackground(QtGui.QColor(226, 239, 218))  # green soft
            item.setForeground(QtGui.QBrush(QtGui.QColor(0, 97, 0)))
        else:
            item.setBackground(QtGui.QColor(255, 199, 206))  # red soft
            item.setForeground(QtGui.QBrush(QtGui.QColor(156, 0, 6)))

    def _ensure_headers(self, strategy_headers: list[str]) -> None:
        base_headers = ["Ticker", "Price", "Consensus FV", "Discount %"]
        headers = base_headers + strategy_headers
        if headers != (["Ticker", "Price", "Consensus FV", "Discount %"] + self._last_strategy_names):
            self._table.clear()
            self._table.setColumnCount(len(headers))
            self._table.setHorizontalHeaderLabels(headers)
            self._table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
            self._table.horizontalHeader().setStretchLastSection(True)
            self._last_strategy_names = strategy_headers

    # -------- public API --------
    def update_with_context(self, ctx: PipelineContext) -> None:
        # Header text
        self._meta.setText(f"Generated at: {ctx.generated_at_iso or '-'}")

        # Ensure columns
        strategy_headers = list(ctx.strategy_names)
        self._ensure_headers(strategy_headers)

        # Rows
        self._table.setSortingEnabled(False)  # avoid jumpiness during bulk update
        self._table.setRowCount(len(ctx.tickers))
        
        # Ensure cursor stays normal during updates
        self.setCursor(QtCore.Qt.ArrowCursor)
        self._table.setCursor(QtCore.Qt.ArrowCursor)

        for r, tk in enumerate(ctx.tickers):
            bt = ctx.results_by_ticker.get(tk, {})
            discount = bt.get("consensus_discount")

            cells = [
                tk,
                self._fmt(bt.get("current_price")),
                self._fmt(bt.get("consensus_fair_value")),
                (f"{discount*100:.1f}%" if isinstance(discount, (int, float)) else "-"),
            ]
            # strategy values
            for sname in strategy_headers:
                fv = (bt.get("strategy_fair_values") or {}).get(sname)
                cells.append(self._fmt(fv))

            for c, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(str(text))
                if c == 0:
                    item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable)
                # Color discount column
                if c == 3:
                    self._colorize_discount_cell(item, discount)
                # Right-align numbers
                if c >= 1:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self._table.setItem(r, c, item)

        self._table.setSortingEnabled(True)
        self._status.setText("Status: refreshed")

    def bind_timer(self, interval_seconds: int) -> None:
        # Set/update a QTimer to refresh at an interval
        if self._timer is None:
            self._timer = QtCore.QTimer(self)
            self._timer.timeout.connect(self.trigger_manual_refresh)
        self._timer.setInterval(max(1, interval_seconds) * 1000)
        if not self._paused:
            self._timer.start()

    # -------- actions --------
    def trigger_manual_refresh(self) -> None:
        if self._paused:
            self._status.setText("Status: paused")
            return
        try:
            self._status.setText("Status: updating…")
            # Set cursor to normal to prevent loading cursor from appearing
            self.setCursor(QtCore.Qt.ArrowCursor)
            QtWidgets.QApplication.processEvents()
            ctx = PipelineContext.new_run()
            run_fetch_stage(ctx)
            run_process_stage(ctx)
            # Run result stage without popping its own GUI; still prints & may broadcast.
            run_result_stage(ctx, show_gui=False)
            self.update_with_context(ctx)
        except Exception as e:
            self._status.setText(f"Status: error: {e}")
        finally:
            # Ensure cursor is reset to normal
            self.setCursor(QtCore.Qt.ArrowCursor)

    def toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._timer:
            if self._paused:
                self._timer.stop()
                self._btn_pause.setText("Resume updates")
                self._status.setText("Status: paused")
            else:
                self._timer.start()
                self._btn_pause.setText("Pause updates")
                self._status.setText("Status: scheduled")

    def _on_interval_changed(self, val: int) -> None:
        self.bind_timer(val)
        if not self._paused:
            self._status.setText(f"Status: interval set to {val}s")


def gui_run_once(overrides: Optional[Dict[str, object]] = None) -> None:
    apply_pipeline_registry(overrides if overrides else None)
    app = QtWidgets.QApplication([])
    w = ValResultsWindow()
    w.show()
    w.trigger_manual_refresh()
    app.exec_()


def gui_run_continuous(interval_seconds: Optional[int] = None,
                       overrides: Optional[Dict[str, object]] = None) -> None:
    apply_pipeline_registry(overrides if overrides else None)
    delay = int(interval_seconds or getattr(control, "LOOP_SLEEP_SECONDS", 180))

    app = QtWidgets.QApplication([])
    w = ValResultsWindow()
    w.show()

    # Initial run + schedule
    w.trigger_manual_refresh()
    w.bind_timer(delay)

    app.exec_()
