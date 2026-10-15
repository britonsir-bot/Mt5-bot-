from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from gui.formatting import format_volume
from gui.screens import Screen, scrollable
from gui.widgets import DataTable, EmptyState, KpiTile, Panel, StatusPill, label

SCREEN_TITLE = "Orders"

_STATUS_TONES = {"accepted": "up", "rejected": "warn", "failed": "down"}


class OrdersScreen(Screen):
    def __init__(self, context: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._events = context["order_event_repository"]
        self._sandbox = bool(context["settings"].use_mock_connector)

        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        kpis = QHBoxLayout()
        kpis.setSpacing(8)
        self._kpi_total = KpiTile("Events recorded")
        self._kpi_accepted = KpiTile("Accepted", tone="up")
        self._kpi_rejected = KpiTile("Rejected")
        self._kpi_failed = KpiTile("Failed", tone="down")
        self._kpi_last = KpiTile("Last event")
        for tile in (
            self._kpi_total,
            self._kpi_accepted,
            self._kpi_rejected,
            self._kpi_failed,
            self._kpi_last,
        ):
            kpis.addWidget(tile, 1)
        outer.addLayout(kpis)

        split = QHBoxLayout()
        split.setSpacing(8)

        events_panel = Panel("Order events", note="append-only audit trail")
        self._table = DataTable(
            ["Time", "Symbol", "Side", "Volume", "Status", "Reason"], numeric_columns=(3,)
        )
        self._table.set_empty_message("No order events recorded yet")
        self._table.stretch_columns(stretch_last=True)
        events_panel.body.addWidget(self._table, 1)
        split.addWidget(events_panel, 3)

        side = QVBoxLayout()
        side.setSpacing(8)

        positions_panel = Panel("Open positions", note="not connected")
        positions_panel.body.addWidget(
            EmptyState(
                "Position tracking is not implemented",
                "The connector exposes account information and order submission only. "
                "There is no positions or deals feed, so open trades cannot be listed "
                "and the maximum-concurrent-trades limit cannot be evaluated.",
            )
        )
        side.addWidget(positions_panel)

        mode_panel = Panel("Execution mode")
        self._mode_pill = StatusPill(
            "SANDBOX (simulated)" if self._sandbox else "LIVE (real account)",
            tone="warn" if self._sandbox else "down",
        )
        mode_panel.body.addWidget(self._mode_pill)
        mode_note = (
            "Orders route to the mock broker. Nothing reaches a real account."
            if self._sandbox
            else "Orders route to the MetaTrader 5 terminal. Confirm the account before submitting."
        )
        note = label(mode_note, role="muted")
        note.setWordWrap(True)
        mode_panel.body.addWidget(note)
        side.addWidget(mode_panel)
        side.addStretch(1)
        split.addLayout(side, 2)
        outer.addLayout(split, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scrollable(body))

    def refresh(self) -> None:
        rows = list(self._events.list_all())
        self._table.clear_rows()
        counts = {"accepted": 0, "rejected": 0, "failed": 0}
        for event in rows:
            status = str(event["status"])
            counts[status] = counts.get(status, 0) + 1
            self._table.append_row(
                [
                    str(event["created_at"]).replace("T", " ")[:19],
                    event["symbol"],
                    event["side"],
                    format_volume(event["volume"]),
                    status,
                    event["reason"],
                ],
                roles=(None, None, None, None, _STATUS_TONES.get(status), None),
            )
        self._kpi_total.set_value(str(len(rows)))
        self._kpi_accepted.set_value(str(counts.get("accepted", 0)))
        self._kpi_rejected.set_value(str(counts.get("rejected", 0)))
        self._kpi_failed.set_value(str(counts.get("failed", 0)))
        self._kpi_last.set_value(
            str(rows[-1]["created_at"]).replace("T", " ")[11:19] if rows else "--"
        )
