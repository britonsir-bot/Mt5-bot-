from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ai.inference import InferenceService
from config.settings import Settings
from core.account_service import AccountService
from core.logging_config import configure_logging
from core.market_data import MarketDataService
from core.mt5_connector import build_connector
from core.order_manager import OrderManager
from core.risk_manager import RiskManager
from core.strategy_engine import StrategyEngine
from database.db import Database
from database.repositories import AccountRepository, OrderEventRepository

PROFILE_NAME = "default-demo"
DEMO_LOGIN = "demo"
DEMO_SERVER = "MockBroker-Demo"
DEMO_TERMINAL_PATH = "mock-terminal"


def _seed_account_profile(
    settings: Settings, repository: AccountRepository, logger: logging.Logger
) -> None:
    if repository.get_profile(PROFILE_NAME) is not None:
        return

    if settings.use_mock_connector:
        login, server, terminal_path = DEMO_LOGIN, DEMO_SERVER, DEMO_TERMINAL_PATH
    else:
        login = settings.account_login
        server = settings.account_server
        terminal_path = settings.account_terminal_path
        if not (login and server and terminal_path):
            logger.warning(
                "No live account profile was seeded; set MT5_LOGIN, MT5_SERVER and "
                "MT5_TERMINAL_PATH to persist one.",
                extra={
                    "event_payload": {
                        "login_configured": login is not None,
                        "server_configured": server is not None,
                        "terminal_path_configured": terminal_path is not None,
                    }
                },
            )
            return

    repository.upsert(
        profile_name=PROFILE_NAME,
        login=login,
        server=server,
        terminal_path=terminal_path,
    )


def create_app_context(base_dir: str | None = None) -> dict[str, Any]:
    settings = Settings.from_env(Path(base_dir) if base_dir else None)
    settings.ensure_directories()

    logger = configure_logging(settings.log_dir)
    database = Database(settings.db_path)
    database.initialize()

    account_repository = AccountRepository(database)
    order_event_repository = OrderEventRepository(database)

    connector = build_connector(settings.use_mock_connector)
    if settings.auto_login and not connector.is_connected():
        if connector.connect():
            logger.info(
                "Connected to the trading terminal at startup.",
                extra={"event_payload": {"auto_login": True}},
            )
        else:
            logger.warning(
                "Automatic login failed; the terminal connection will be retried on demand.",
                extra={"event_payload": {"auto_login": True}},
            )

    account_service = AccountService(connector)
    market_data_service = MarketDataService(connector)
    risk_manager = RiskManager()
    order_manager = OrderManager(
        connector=connector,
        risk_manager=risk_manager,
        order_event_writer=order_event_repository,
    )
    strategy_engine = StrategyEngine()
    ai_inference = InferenceService()

    _seed_account_profile(settings, account_repository, logger)

    logger.info(
        "Application context initialized",
        extra={"event_payload": {"mock_connector": settings.use_mock_connector}},
    )

    return {
        "settings": settings,
        "logger": logger,
        "database": database,
        "account_repository": account_repository,
        "order_event_repository": order_event_repository,
        "connector": connector,
        "account_service": account_service,
        "market_data_service": market_data_service,
        "risk_manager": risk_manager,
        "order_manager": order_manager,
        "strategy_engine": strategy_engine,
        "ai_inference": ai_inference,
    }
