from __future__ import annotations

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


def create_app_context(base_dir: str | None = None) -> dict[str, Any]:
    settings = Settings.from_env(Path(base_dir) if base_dir else None)
    settings.ensure_directories()

    logger = configure_logging(settings.log_dir)
    database = Database(settings.db_path)
    database.initialize()

    account_repository = AccountRepository(database)
    order_event_repository = OrderEventRepository(database)

    connector = build_connector(settings.use_mock_connector)
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

    account_repository.upsert(
        profile_name="default-demo",
        login="demo",
        server="MockBroker-Demo" if settings.use_mock_connector else "LiveBroker",
        terminal_path="mock-terminal",
    )

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
