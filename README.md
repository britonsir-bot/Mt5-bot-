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
| Strategy rule evaluation | **Not implemented** — `StrategyEngine.evaluate_tick` returns no signals |
| AI prediction and training | **Not implemented** — advisory placeholder and a `skipped` trainer |
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
