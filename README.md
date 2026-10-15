# Mt5-bot-

Backend-first scaffold for an MT5 AI trading bot desktop application.

## Status

| Area | State |
|---|---|
| Configuration, logging, SQLite persistence | Implemented |
| MT5 account, tick, candle and order access | Implemented (`MetaTrader5Connector`) |
| Mock broker for offline development | Implemented (`MockMt5Connector`, the default) |
| Risk controls | Implemented |
| Indicators (SMA, EMA, RSI) | Implemented |
| Desktop screens | Implemented — five live screens, three explicit placeholders |
| Chart rendering | Implemented — candlesticks and line charts painted with `QPainter` |
| Strategy rule evaluation | Implemented — declarative conditions, evaluated vectorised |
| Backtesting | Implemented — causal single-symbol bar-by-bar simulator |
| AI prediction and training | Implemented — scikit-learn meta-filter with walk-forward validation |
| Position, daily P/L and drawdown tracking | **Not implemented** — the connector has no positions or deals feed |

Live order submission is implemented but has not been exercised against a real
terminal. Run it against a demo account first.

## Layout

```
app.py                      application context factory
main.py                     entry point (GUI when PySide6 is present, backend report otherwise)
ai/                         advisory inference and training stubs
config/settings.py          Settings loaded from the environment
core/                       connectors, indicators, risk, orders, strategy registry
database/                   SQLite schema and repositories
gui/                        PySide6 window shell and theme
tests/                      pytest suite
```

## Setup

```
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Install the broker binding only on a machine running the MetaTrader 5 terminal:

```
pip install -e ".[mt5]"
```

## Configuration

All settings come from the environment.

| Variable | Default | Meaning |
|---|---|---|
| `MT5_USE_MOCK` | `1` | `1`/`true`/`yes`/`on` uses the mock broker; `0`/`false`/`no`/`off` uses the live terminal |
| `MT5_LOGIN` | unset | Live account login, persisted as the local account profile |
| `MT5_SERVER` | unset | Live broker server name |
| `MT5_TERMINAL_PATH` | unset | Path to `terminal64.exe` |
| `MT5_AUTO_LOGIN` | `0` | Connect to the terminal during startup |
| `MT5_THEME` | `dark` | `dark` or `light`; unknown values fall back to `dark` |

Boolean variables reject values outside the accepted literals with a
`ConfigurationError` rather than guessing.

An account profile is seeded once, only when it does not already exist. In mock
mode the demo profile is written; in live mode nothing is written unless
`MT5_LOGIN`, `MT5_SERVER` and `MT5_TERMINAL_PATH` are all set, so a saved
profile is never overwritten.

## Running

```
python main.py
```

With PySide6 installed the desktop shell opens. Otherwise the process reports
the account snapshot from the backend and exits. Startup failures caused by an
unavailable terminal print a single readable message and exit with status 2.

## Desktop shell

| Tab | Backed by | Notes |
|---|---|---|
| Dashboard | `AccountService`, `MarketDataService`, `OrderEventRepository` | KPI strip, price chart, watchlist, recent order events, risk summary |
| Market Terminal | `MarketDataService`, `OrderManager` | Watchlist, candlesticks with timeframes, quote strip, order ticket |
| Orders | `OrderEventRepository` | Append-only audit trail and per-status counts |
| Risk | `RiskManager`, live `RiskProfile` | Editor for the running profile; probe evaluates a sample order |
| Settings | `Settings`, `AccountRepository` | Connection, storage paths, account profiles, theme |
| Strategy Manager, AI Assistant, Logs | — | Placeholders that state what is missing and what is planned |

Conventions the screens follow:

- **Nothing pretends to be live.** Panels without a data source show an explicit
  *not connected* state and list what they would need, rather than sample rows.
- **Simulated data is labelled.** Candles from the mock broker carry a
  `simulated` flag, and any panel showing them displays a `SIMULATED` pill.
- **Order entry is sandbox-only.** In mock mode the ticket submits to the mock
  broker. In live mode the buttons are disabled, because open positions, daily
  P/L and drawdown are not tracked, so the risk limits could not be evaluated
  before sending an order. The ticket says so on screen.
- **Risk limits live in memory.** The Risk tab applies to the running session.
  Persisting the profile would need a `risk_profiles` table; the database stores
  account profiles and order events only.

Themes are dark (default) and light, selected with `MT5_THEME` or from the
Settings tab. Both use solid surfaces, a single accent colour and monospace
figures for prices; there are no gradients, glows or decorative animation.

## Strategies and backtesting

`strategies/catalogue/` holds configs taken from the
`britonsir-bot/mt5-trading-strategies` repository. `load_specs()` returns all 16
executable strategies and `summarise()` reports which of them can be evaluated
here and why any cannot. At present 15 of 16 evaluate; `dual_momentum` is
blocked because its ranking, rotation and safe-haven logic needs a multi-asset
universe.

**The `documented` block on each spec is a citation, not a measurement.** Those
win rates, profit factors and drawdowns are what the YAML quotes from external
literature and vendor research; nothing in this repository measured them. Only
`BacktestResult` carries numbers this codebase computed, and every result states
its `data_source` and a `simulated` flag so a run on mock candles cannot be
mistaken for an edge.

```python
from core.mt5_connector import MockMt5Connector
from strategies import Backtester, load_specs, summarise

specs = load_specs()
print(summarise(specs))
result = Backtester().run(specs[8], MockMt5Connector().get_ohlc("XAUUSD", "H1", 1000),
                          data_source="simulated")
print(result.metrics)
```

The rule evaluator covers the whole vocabulary the configs use: `calendar`,
`price`, `indicator`, `indicator_compare` and `indicator_crossover` conditions
over `eq`, `lt`, `lte`, `gt`, `gte`, `cross_above`, `cross_below` and `btwn`,
against scalars, other indicators, `prev_close` / `prev_high` / `prev_low`,
`prev_value` (a series against its own previous value) and higher-timeframe
references such as `ema_200_h4`. An unresolvable field blocks the strategy
instead of silently comparing the wrong series.

`Backtester` fills a signal seen on bar `t` at the open of bar `t + 1`, moves a
trailing stop only on a closed bar, and measures drawdown on the closed-trade
equity curve. Positions are sized from `risk_per_trade_pct` against the initial
stop distance. Rules that cannot fire are reported rather than left as a silent
zero: a run explains whether the conditions never fired on the data or never
coincided at all.

## Risk controls

`RiskManager.evaluate` requires the account state explicitly — open trade count,
daily P&L, current drawdown and equity — so no limit can be skipped by omitting
an argument. A threshold of zero disables its check.

Enforced: maximum lot size, maximum concurrent trades, maximum daily loss,
maximum drawdown, equity protection floor, daily profit target, and the allowed
session window.

Session windows support overnight ranges such as `22:00`–`02:00`, and timezone
aware window bounds are honoured by converting `now` into the window's timezone.
When the window carries no timezone it is compared against the wall clock of
`now`.

## AI meta-filter

`ai/` is a traditional scikit-learn meta-filter that predicts `next_bar_return`
and gates strategy signals, matching the `ml:` block in the bot config
(`confidence_threshold: 0.65`, `lookback_bars: 200`). Models are
`random_forest` (default), `extra_trees`, `gradient_boosting` and
`logistic_regression`; no deep-learning dependency is used. The config names
`xgboost`, which is not installed and is not required.

Correctness rules the module enforces and tests: a feature row at bar `t` uses
only bars up to `t`; the label is `close[t + horizon] > close[t]` with the final
`horizon` rows dropped; rows with non-finite warm-up features are dropped with
`X`, `y` and the index kept aligned; the train/validation split is
chronological and never shuffled. `MLEngine.walk_forward` validates on anchored
out-of-sample folds.

The tests include a leakage guard, a shuffled-label control that must not
generalise, and a synthetic-signal test that requires the pipeline to clear a
stated accuracy floor above chance. Those tests measure the *machinery*, not
market edge. `InferenceService.recommend()` reports `trend="untrained"` while no
model is fitted rather than inventing a neutral view.

## Tests

```
python -m pytest
```

The suite covers the indicators, configuration parsing, logging reconfiguration,
repositories, the risk matrix, order-event auditing, number formatting, the live
connector against a fake `MetaTrader5` module, and application-context startup in
both broker modes. `tests/test_gui.py` drives the desktop shell — every tab
refreshes, the order ticket records accepted and risk-rejected orders, the risk
editor round-trips into the live profile, and the charts paint with and without
data — using Qt's `offscreen` platform, which `tests/conftest.py` selects before
PySide6 is imported. That module skips itself when PySide6 is absent.

No test requires network access, a running terminal, or a display.
