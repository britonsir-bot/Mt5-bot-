from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="the desktop shell requires PySide6")

from PySide6.QtCore import QTime  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import create_app_context  # noqa: E402
from core.mt5_connector import MockMt5Connector  # noqa: E402
from gui.canvas import CandlestickChart, LineChart  # noqa: E402
from gui.main_window import SCREEN_TITLES, MainWindow  # noqa: E402
from gui.screens import NotConnectedScreen  # noqa: E402
from gui.theme import current_theme  # noqa: E402
from gui.widgets import EmptyState  # noqa: E402

DASHBOARD, TERMINAL, ORDERS, STRATEGY, RISK, AI, LOGS, SETTINGS = range(8)


@pytest.fixture(scope="session")
def qt_application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(tmp_path, monkeypatch, qt_application):
    monkeypatch.setenv("MT5_USE_MOCK", "1")
    context = create_app_context(base_dir=str(tmp_path))
    main_window = MainWindow(context)
    main_window.resize(1440, 900)
    yield main_window
    main_window._clock.stop()
    main_window.close()


def test_every_tab_builds_and_refreshes(window):
    assert window._tabs.count() == len(SCREEN_TITLES)
    for index in range(window._tabs.count()):
        window._tabs.setCurrentIndex(index)
        window.refresh_current()
        assert "refreshed" in window._status_label.text()


def test_tab_titles_match_the_designed_screens(window):
    titles = [window._tabs.tabText(index) for index in range(window._tabs.count())]
    assert titles == [
        "Dashboard",
        "Market Terminal",
        "Orders",
        "Strategy Manager",
        "Risk",
        "AI Assistant",
        "Logs",
        "Settings",
    ]


def test_dashboard_reflects_the_account_snapshot(window):
    dashboard = window._screens[DASHBOARD]
    dashboard.refresh()
    snapshot = window.context["account_service"].get_account_snapshot()
    assert dashboard._kpi_balance.value_text() == f"{snapshot.balance:,.2f}"
    assert dashboard._kpi_equity.value_text() == f"{snapshot.equity:,.2f}"
    assert dashboard._account_rows["login"].value_text() == snapshot.login


def test_dashboard_populates_the_market_watch(window):
    dashboard = window._screens[DASHBOARD]
    dashboard.refresh()
    assert dashboard._watch.rowCount() == len(window.context["market_data_service"].watchlist())


def test_terminal_loads_candles_for_the_selected_symbol(window):
    terminal = window._screens[TERMINAL]
    terminal.refresh()
    candles = terminal._chart._candles
    assert len(candles) == 160
    assert candles[-1].simulated is True


def test_selecting_a_watchlist_row_switches_the_chart_symbol(window):
    terminal = window._screens[TERMINAL]
    terminal.refresh()
    terminal._watch.selectRow(2)
    assert terminal._symbol == "USDJPY"
    assert terminal._ticket_symbol.text() == "USDJPY"


def test_timeframe_toggle_reloads_the_chart(window):
    terminal = window._screens[TERMINAL]
    terminal._set_timeframe("H1")
    assert terminal._timeframe == "H1"
    assert terminal._chart._candles


def test_sandbox_order_is_recorded_in_the_audit_trail(window):
    terminal = window._screens[TERMINAL]
    terminal._volume.setValue(0.10)
    terminal._buy_button.click()
    events = window.context["order_event_repository"].list_all()
    assert [event["status"] for event in events] == ["accepted"]
    assert "Simulated" in terminal._result_label.text()


def test_order_above_the_lot_limit_is_rejected_before_execution(window):
    terminal = window._screens[TERMINAL]
    terminal._volume.setValue(5.00)
    terminal._buy_button.click()
    events = window.context["order_event_repository"].list_all()
    assert [event["status"] for event in events] == ["rejected"]
    assert "exceeds max lot size" in terminal._result_label.text()


def test_orders_screen_counts_every_status(window):
    terminal = window._screens[TERMINAL]
    terminal._volume.setValue(0.10)
    terminal._buy_button.click()
    terminal._volume.setValue(5.00)
    terminal._buy_button.click()
    orders_screen = window._screens[ORDERS]
    orders_screen.refresh()
    assert orders_screen._kpi_total.value_text() == "2"
    assert orders_screen._kpi_accepted.value_text() == "1"
    assert orders_screen._kpi_rejected.value_text() == "1"
    assert orders_screen._table.rowCount() == 2


def test_risk_screen_loads_the_profile_at_construction(window):
    """An editor that has never been refreshed must not overwrite the live limits."""
    risk_screen = window._screens[RISK]
    risk_screen._apply_button.click()
    profile = window.context["risk_profile"]
    assert profile.max_lot_size == 1.0
    assert profile.max_daily_loss == 500.0
    assert profile.max_trades == 5


def test_risk_screen_applies_limits_to_the_running_profile(window):
    risk_screen = window._screens[RISK]
    risk_screen.refresh()
    risk_screen._money_spins["max_daily_loss"].setValue(250.0)
    risk_screen._max_trades.setValue(3)
    risk_screen._apply_button.click()
    profile = window.context["risk_profile"]
    assert profile.max_daily_loss == 250.0
    assert profile.max_trades == 3
    assert risk_screen._summary_rows["max_daily_loss"].value_text() == "250.00"


def test_risk_screen_applies_an_overnight_session_window(window):
    risk_screen = window._screens[RISK]
    risk_screen._session_enabled.setChecked(True)
    risk_screen._session_start.setTime(QTime(22, 0))
    risk_screen._session_end.setTime(QTime(2, 0))
    risk_screen._apply_button.click()
    profile = window.context["risk_profile"]
    assert (profile.allowed_start_time.hour, profile.allowed_end_time.hour) == (22, 2)
    assert risk_screen._summary_rows["session"].value_text() == "22:00-02:00"


def test_risk_screen_can_clear_the_session_window(window):
    risk_screen = window._screens[RISK]
    risk_screen._session_enabled.setChecked(True)
    risk_screen._apply_button.click()
    assert window.context["risk_profile"].allowed_start_time is not None
    risk_screen._session_enabled.setChecked(False)
    risk_screen._apply_button.click()
    assert window.context["risk_profile"].allowed_start_time is None
    assert risk_screen._summary_rows["session"].value_text() == "any time"


def test_risk_screen_evaluates_a_sample_order(window):
    risk_screen = window._screens[RISK]
    risk_screen._probe_button.click()
    assert risk_screen._probe_result.text().startswith("Approved")


def test_risk_screen_reports_a_rejection_from_the_engine(window):
    risk_screen = window._screens[RISK]
    risk_screen._money_spins["equity_protection"].setValue(50_000.0)
    risk_screen._apply_button.click()
    risk_screen._probe_button.click()
    assert risk_screen._probe_result.text().startswith("Rejected")
    assert "equity protection" in risk_screen._probe_result.text().lower()


def test_settings_screen_lists_the_stored_profile(window):
    settings_screen = window._screens[SETTINGS]
    settings_screen.refresh()
    assert settings_screen._profiles.rowCount() == 1
    assert settings_screen._profiles.item(0, 1).text() == "demo"


def test_settings_screen_reports_sandbox_mode(window):
    settings_screen = window._screens[SETTINGS]
    settings_screen.refresh()
    assert settings_screen._rows["connector"].value_text() == "MockMt5Connector"


def test_theme_switch_updates_state(window):
    window.apply_theme("light")
    assert current_theme() == "light"
    window.apply_theme("dark")
    assert current_theme() == "dark"


def test_theme_change_from_the_settings_combo_applies(window):
    settings_screen = window._screens[SETTINGS]
    settings_screen._theme_combo.setCurrentText("light")
    assert current_theme() == "light"
    settings_screen._theme_combo.setCurrentText("dark")
    assert current_theme() == "dark"


def test_placeholder_screens_state_what_is_missing(window):
    for index in (STRATEGY, AI, LOGS):
        screen = window._screens[index]
        screen.refresh()
        assert isinstance(screen, NotConnectedScreen)
        assert screen.findChildren(EmptyState)


def test_charts_paint_with_and_without_data(qt_application):
    chart = CandlestickChart()
    chart.resize(600, 320)
    chart.grab()

    chart.set_candles(MockMt5Connector().get_ohlc("EURUSD", "M15", 60), 5)
    chart.grab()
    assert len(chart._candles) == 60

    line = LineChart("no data")
    line.resize(300, 120)
    line.grab()
    line.set_points([1.0, 2.0, 1.5, 3.0])
    line.grab()
    assert line.points() == [1.0, 2.0, 1.5, 3.0]
