# Mt5-bot-

Backend-first scaffold for an MT5 AI trading bot desktop application.

## Status

| Area | State |
|---|---|
| Configuration, logging, SQLite persistence | Implemented |
| MT5 account, tick and order access | Implemented (`MetaTrader5Connector`) |
| Mock broker for offline development | Implemented (`MockMt5Connector`, the default) |
| Risk controls | Implemented |
| Indicators (SMA, EMA, RSI) | Implemented |
| Strategy rule evaluation | **Not implemented** — `StrategyEngine.evaluate_tick` returns no signals |
| AI prediction and training | **Not implemented** — advisory placeholder and a `skipped` trainer |
| Desktop screens | **Not implemented** — the GUI is a tab shell |

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
repositories, the risk matrix, order-event auditing, the live connector against a
fake `MetaTrader5` module, and application-context startup in both broker modes.
No test requires network access, a terminal, or PySide6.
