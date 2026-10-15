"""Strategy specifications, rule evaluation and backtesting.

The specs come from the ``britonsir-bot/mt5-trading-strategies`` repository,
vendored under ``strategies/catalogue``. ``load_specs`` returns every strategy
the config declares together with the reason any of them cannot be evaluated
here, so an unsupported strategy is reported rather than silently skipped.
"""

from strategies.backtest import BacktestMetrics, BacktestResult, BacktestTrade, Backtester, run_all
from strategies.rules import (
    Condition,
    ConditionGroup,
    UnsupportedConditionError,
    group_mask,
)
from strategies.series import SeriesProvider, UnknownSeriesError, available_series
from strategies.spec import (
    DocumentedStats,
    StrategySpec,
    load_documented_stats,
    load_specs,
    ml_settings,
    summarise,
)

__all__ = [
    "BacktestMetrics",
    "BacktestResult",
    "BacktestTrade",
    "Backtester",
    "Condition",
    "ConditionGroup",
    "DocumentedStats",
    "SeriesProvider",
    "StrategySpec",
    "UnknownSeriesError",
    "UnsupportedConditionError",
    "available_series",
    "group_mask",
    "load_documented_stats",
    "load_specs",
    "ml_settings",
    "run_all",
    "summarise",
]
