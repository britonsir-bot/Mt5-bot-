from __future__ import annotations

import pytest

from config.settings import Settings
from core.exceptions import ConfigurationError


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "True", "yes", "on", " true "])
def test_truthy_literals_enable_mock_mode(monkeypatch, raw):
    monkeypatch.setenv("MT5_USE_MOCK", raw)
    assert Settings.from_env().use_mock_connector is True


@pytest.mark.parametrize("raw", ["0", "false", "FALSE", "False", "no", "off", " off "])
def test_falsy_literals_disable_mock_mode(monkeypatch, raw):
    monkeypatch.setenv("MT5_USE_MOCK", raw)
    assert Settings.from_env().use_mock_connector is False


def test_blank_value_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("MT5_USE_MOCK", "   ")
    assert Settings.from_env().use_mock_connector is True


def test_invalid_boolean_raises_a_configuration_error(monkeypatch):
    monkeypatch.setenv("MT5_USE_MOCK", "maybe")
    with pytest.raises(ConfigurationError):
        Settings.from_env()


def test_invalid_auto_login_raises_a_configuration_error(monkeypatch):
    monkeypatch.setenv("MT5_AUTO_LOGIN", "sometimes")
    with pytest.raises(ConfigurationError):
        Settings.from_env()


def test_auto_login_is_parsed_with_the_same_literals(monkeypatch):
    monkeypatch.setenv("MT5_AUTO_LOGIN", "yes")
    assert Settings.from_env().auto_login is True


def test_account_fields_are_parsed(monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "999888")
    monkeypatch.setenv("MT5_SERVER", "ICMarkets-Live")
    monkeypatch.setenv("MT5_TERMINAL_PATH", r"C:\MT5\terminal64.exe")
    settings = Settings.from_env()
    assert settings.account_login == "999888"
    assert settings.account_server == "ICMarkets-Live"
    assert settings.account_terminal_path == r"C:\MT5\terminal64.exe"


def test_account_fields_default_to_none():
    settings = Settings.from_env()
    assert settings.account_login is None
    assert settings.account_server is None
    assert settings.account_terminal_path is None


def test_blank_account_fields_are_treated_as_unset(monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "  ")
    assert Settings.from_env().account_login is None


def test_theme_is_parsed(monkeypatch):
    monkeypatch.setenv("MT5_THEME", "light")
    assert Settings.from_env().theme == "light"
