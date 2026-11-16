# Linear Algebra Trading Lab

A learning project: a Bayesian Monte Carlo risk engine and a two-slot
allocator for an R-multiple momentum system on US stocks, built on linear
algebra. Study material, not financial advice.

## Phases

| Phase | Notebook | Status |
|---|---|---|
| 0 | `00_setup_linear_algebra.ipynb` — tool check and linear algebra warm-up | done |
| 1 | `01_monte_carlo_engine.ipynb` — simulate thousands of futures of the rules | done |
| 2 | `02_bayesian_edge_tracker.ipynb` — win rate, winner size and expectancy from the trade log, with uncertainty | done |
| 3 | `03_bayesian_monte_carlo.ipynb` — simulate with an uncertain edge, choose the risk per trade | done |
| 4 | `04_momentum_scanner.ipynb` — scan US stocks, score setups, covariance, PCA, themes as a graph | done |
| 5 | `05_two_slot_allocator.ipynb` — pick two positions and sizes with a linear program, shadow prices | done |
| 6 | `06_daily_report.ipynb` — every phase in one run: verdict, dashboard, written report | done |
| 7 | `07_score_backtest.ipynb` — backtest of the setup score, the filters and the regime gate | done |

## Files

- `mc_engine.py` — the simulation functions (trade matrix, equity paths,
  drawdown, losing streaks, correlated slots through Cholesky).
- `bayes_edge.py` — the Bayesian update functions and the sizing rule.
- `sample_trade_log.csv` — 40 made-up trades for practice. Not real trades.
- `scanner.py` — price download, scan metrics, filters, setup score, PCA and themes.
- `daily_report.py` — the whole pipeline in one call; also runs from a terminal.
- `reports/` — saved daily reports (Markdown and dashboard image).
- `backtest.py` — point-in-time panel, trade simulation, rank correlation, bootstrap.
- `allocator.py` — the linear program: build, solve, shadow prices, order table.
- `allocation.csv` — Phase 5 output: the order ticket.
- `data/` — saved price snapshot used when no fresh download is requested.
- `candidates.csv` — Phase 4 output, input for Phase 5.
- `MANUAL.md` — full manual: structure, engine logic, selection, ignored effects, glossary.
- `lab_style.py` — shared chart colours and matplotlib defaults.
- `requirements.txt` — libraries to install.

## How to run

```
pip install -r requirements.txt
jupyter notebook
```

Open `00_setup_linear_algebra.ipynb`, choose `Kernel ▸ Restart & Run All`,
then do the same for notebooks 01 to 07. For daily use, run only
notebook 06, or `python daily_report.py --refresh` from a terminal. See
`MANUAL.md`, section 13, for the full run guide. Edit only the cell marked
`KEY IN HERE`.

## Assumptions to replace with your own data

The 23% win rate and 8R average winner are borrowed from published trader
statistics. The winner-size spread, gap frequency and cash-cap frequency are
placeholders. Phase 2 replaces them with estimates from your own trade log:
set `TRADE_LOG` in notebook 02 to a CSV with a column `R` (result of each
closed trade in R, oldest first), or the columns `pnl` and `risk_dollars`.

## Finding from Phase 7

Over five years of history the setup score did not rank candidates: trades
on high-score stocks did no better than trades on low-score stocks, and
neither the filters nor the regime gate showed a reliable benefit. Treat the
scanner's candidate list as unordered. See `07_score_backtest.ipynb`.
