from __future__ import annotations

from app import PROFILE_NAME, create_app_context


def test_create_app_context_contains_services(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_USE_MOCK", "1")
    context = create_app_context(base_dir=str(tmp_path))
    assert "settings" in context
    assert "database" in context
    assert "account_service" in context
    assert "order_manager" in context


def test_context_artifacts_stay_inside_the_configured_base_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_USE_MOCK", "1")
    create_app_context(base_dir=str(tmp_path))
    assert (tmp_path / "runtime" / "db" / "mt5_bot.sqlite3").exists()
    assert (tmp_path / "runtime" / "logs" / "application.log").exists()


def test_mock_mode_seeds_the_demo_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_USE_MOCK", "1")
    context = create_app_context(base_dir=str(tmp_path))
    profiles = context["account_repository"].list_profiles()
    assert [(p.login, p.server, p.terminal_path) for p in profiles] == [
        ("demo", "MockBroker-Demo", "mock-terminal")
    ]


def test_startup_does_not_overwrite_a_saved_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_USE_MOCK", "1")
    first = create_app_context(base_dir=str(tmp_path))
    first["account_repository"].upsert(
        PROFILE_NAME, "REAL-999888", "ICMarkets-Live", r"C:\MT5\terminal64.exe"
    )
    second = create_app_context(base_dir=str(tmp_path))
    profiles = second["account_repository"].list_profiles()
    assert [(p.login, p.server, p.terminal_path) for p in profiles] == [
        ("REAL-999888", "ICMarkets-Live", r"C:\MT5\terminal64.exe")
    ]


def test_live_mode_does_not_seed_a_fabricated_profile(tmp_path, monkeypatch, install_fake_mt5):
    install_fake_mt5()
    monkeypatch.setenv("MT5_USE_MOCK", "0")
    context = create_app_context(base_dir=str(tmp_path))
    assert context["account_repository"].list_profiles() == []


def test_live_mode_seeds_a_configured_profile(tmp_path, monkeypatch, install_fake_mt5):
    install_fake_mt5()
    monkeypatch.setenv("MT5_USE_MOCK", "0")
    monkeypatch.setenv("MT5_LOGIN", "999888")
    monkeypatch.setenv("MT5_SERVER", "ICMarkets-Live")
    monkeypatch.setenv("MT5_TERMINAL_PATH", r"C:\MT5\terminal64.exe")
    context = create_app_context(base_dir=str(tmp_path))
    profiles = context["account_repository"].list_profiles()
    assert [(p.login, p.server, p.terminal_path) for p in profiles] == [
        ("999888", "ICMarkets-Live", r"C:\MT5\terminal64.exe")
    ]


def test_auto_login_connects_at_startup(tmp_path, monkeypatch, install_fake_mt5):
    fake = install_fake_mt5()
    monkeypatch.setenv("MT5_USE_MOCK", "0")
    monkeypatch.setenv("MT5_AUTO_LOGIN", "1")
    context = create_app_context(base_dir=str(tmp_path))
    assert context["connector"].is_connected() is True
    assert fake.initialized is True


def test_auto_login_is_skipped_when_disabled(tmp_path, monkeypatch, install_fake_mt5):
    fake = install_fake_mt5()
    monkeypatch.setenv("MT5_USE_MOCK", "0")
    context = create_app_context(base_dir=str(tmp_path))
    assert context["connector"].is_connected() is False
    assert fake.initialized is False
