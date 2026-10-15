from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from gui.theme import current_palette
from gui.widgets import mono_font

PRICE_AXIS_WIDTH = 62
TIME_AXIS_HEIGHT = 20
GRID_ROWS = 5
COMPACT_GRID_ROWS = 3
TIME_LABELS = 5
MIN_LABEL_GAP = 11.0


class _ChartBase(QWidget):
    def __init__(self, empty_message: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._empty_message = empty_message
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(200)

    def _plot_rect(self, *, right_axis: bool = True, bottom_axis: bool = True) -> QRectF:
        return QRectF(self.rect()).adjusted(
            0.0,
            2.0,
            -float(PRICE_AXIS_WIDTH) if right_axis else -2.0,
            -float(TIME_AXIS_HEIGHT) if bottom_axis else -2.0,
        )

    def _grid_rows(self, plot: QRectF) -> int:
        return GRID_ROWS if plot.height() >= 140 else COMPACT_GRID_ROWS

    def _grid_positions(self, plot: QRectF, rows: int) -> list[float]:
        """Grid lines, nudged inward so the outer price labels are never clipped."""
        positions = []
        lowest = plot.top() + 7.0
        highest = plot.bottom() - 7.0
        for row in range(rows + 1):
            y = plot.top() + plot.height() * row / rows
            positions.append(min(max(y, lowest), highest))
        return positions

    def _draw_grid(self, painter: QPainter, plot: QRectF, positions: list[float]) -> None:
        palette = current_palette()
        painter.setPen(QPen(QColor(palette["grid"]), 1))
        for y in positions:
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

    def _draw_axis_label(
        self, painter: QPainter, plot: QRectF, y: float, text: str, color: QColor
    ) -> None:
        painter.setPen(color)
        painter.setFont(mono_font(7))
        painter.drawText(
            QRect(
                int(plot.right()) + 4,
                int(y) - 7,
                PRICE_AXIS_WIDTH - 6,
                14,
            ),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            text,
        )

    def _draw_empty(self, painter: QPainter) -> None:
        palette = current_palette()
        painter.setPen(QColor(palette["text_muted"]))
        painter.setFont(mono_font(8))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignCenter),
            self._empty_message,
        )


class CandlestickChart(_ChartBase):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("No price history", parent=parent)
        self._candles: list = []
        self._digits = 5

    def set_candles(self, candles: list, digits: int = 5) -> None:
        self._candles = list(candles)
        self._digits = int(digits)
        self.update()

    def paintEvent(self, event) -> None:
        palette = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(palette["surface"]))

        if not self._candles:
            self._draw_empty(painter)
            painter.end()
            return

        plot = self._plot_rect()
        if plot.width() < 40 or plot.height() < 40:
            painter.end()
            return

        lows = [candle.low for candle in self._candles]
        highs = [candle.high for candle in self._candles]
        lowest, highest = min(lows), max(highs)
        span = highest - lowest or (highest * 0.001 or 1.0)
        lowest -= span * 0.06
        highest += span * 0.06
        span = highest - lowest

        def price_to_y(price: float) -> float:
            return plot.bottom() - (price - lowest) / span * plot.height()

        rows = self._grid_rows(plot)
        positions = self._grid_positions(plot, rows)
        self._draw_grid(painter, plot, positions)

        last_y = price_to_y(self._candles[-1].close)
        axis_color = QColor(palette["text_muted"])
        for row, y in enumerate(positions):
            if abs(y - last_y) < MIN_LABEL_GAP:
                continue
            self._draw_axis_label(
                painter, plot, y, f"{highest - span * row / rows:.{self._digits}f}", axis_color
            )

        total = len(self._candles)
        slot = plot.width() / total
        body_width = max(1.0, min(slot * 0.66, 14.0))
        up_color = QColor(palette["up"])
        down_color = QColor(palette["down"])

        for index, candle in enumerate(self._candles):
            centre = plot.left() + slot * (index + 0.5)
            color = up_color if candle.close >= candle.open else down_color
            painter.setPen(QPen(color, 1))
            painter.drawLine(
                QPointF(centre, price_to_y(candle.high)),
                QPointF(centre, price_to_y(candle.low)),
            )
            top = price_to_y(max(candle.open, candle.close))
            bottom = price_to_y(min(candle.open, candle.close))
            body = QRectF(centre - body_width / 2.0, top, body_width, max(bottom - top, 1.0))
            painter.fillRect(body, color)

        last_close = self._candles[-1].close
        painter.setPen(QPen(QColor(palette["accent"]), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(plot.left(), last_y), QPointF(plot.right(), last_y))
        painter.setPen(QColor(palette["accent"]))
        painter.setFont(mono_font(7, bold=True))
        painter.drawText(
            QRect(int(plot.right()) + 4, int(last_y) - 7, PRICE_AXIS_WIDTH - 6, 14),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            f"{last_close:.{self._digits}f}",
        )

        painter.setPen(QColor(palette["text_muted"]))
        painter.setFont(mono_font(7))
        step = max(1, total // TIME_LABELS)
        for index in range(0, total, step):
            stamp: datetime = self._candles[index].timestamp
            x = plot.left() + slot * (index + 0.5)
            if x > plot.right() - 26 or x - 24 < plot.left():
                continue
            painter.drawText(
                QRect(int(x) - 24, int(plot.bottom()) + 3, 48, TIME_AXIS_HEIGHT - 4),
                int(Qt.AlignmentFlag.AlignCenter),
                stamp.strftime("%H:%M"),
            )
        painter.end()


class LineChart(_ChartBase):
    def __init__(self, empty_message: str = "No data", *, parent: QWidget | None = None) -> None:
        super().__init__(empty_message, parent=parent)
        self._points: list[float] = []
        self._decimals = 2
        self._prefix = ""

    def set_points(self, points: list[float], *, decimals: int = 2, prefix: str = "") -> None:
        self._points = [float(point) for point in points]
        self._decimals = int(decimals)
        self._prefix = prefix
        self.update()

    def points(self) -> list[float]:
        return list(self._points)

    def paintEvent(self, event) -> None:
        palette = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(palette["surface"]))

        if len(self._points) < 2:
            self._draw_empty(painter)
            painter.end()
            return

        plot = self._plot_rect()
        if plot.width() < 40 or plot.height() < 30:
            painter.end()
            return

        lowest, highest = min(self._points), max(self._points)
        span = highest - lowest
        if span <= 0:
            span = abs(highest) * 0.001 or 1.0
        lowest -= span * 0.08
        highest += span * 0.08
        span = highest - lowest

        rows = self._grid_rows(plot)
        positions = self._grid_positions(plot, rows)
        self._draw_grid(painter, plot, positions)

        axis_color = QColor(palette["text_muted"])
        for row, y in enumerate(positions):
            value = highest - span * row / rows
            self._draw_axis_label(
                painter, plot, y, f"{self._prefix}{value:,.{self._decimals}f}", axis_color
            )

        step = plot.width() / (len(self._points) - 1)
        polygon = QPolygonF()
        for index, value in enumerate(self._points):
            x = plot.left() + step * index
            y = plot.bottom() - (value - lowest) / span * plot.height()
            polygon.append(QPointF(x, y))

        area = QPolygonF(polygon)
        area.append(QPointF(plot.right(), plot.bottom()))
        area.append(QPointF(plot.left(), plot.bottom()))
        fill = QColor(palette["accent"])
        fill.setAlpha(38)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawPolygon(area)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(palette["accent"]), 1.6))
        painter.drawPolyline(polygon)
        painter.end()
