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
| 3 | Feed the Bayesian estimate into the Monte Carlo engine | next |
| 4 | Momentum scanner, covariance matrix, themes by PCA | planned |
| 5 | Two-slot allocator as a linear program | planned |
| 6 | One daily report joining all phases | planned |

## Files

- `mc_engine.py` — the simulation functions (trade matrix, equity paths,
  drawdown, losing streaks, correlated slots through Cholesky).
- `bayes_edge.py` — the Bayesian update functions and the sizing rule.
- `sample_trade_log.csv` — 40 made-up trades for practice. Not real trades.
- `lab_style.py` — shared chart colours and matplotlib defaults.
- `requirements.txt` — libraries to install.

## How to run

```
pip install -r requirements.txt
jupyter notebook
```

Open `00_setup_linear_algebra.ipynb`, choose `Kernel ▸ Restart & Run All`,
then do the same for notebooks 01 and 02. Edit only the cell marked
`KEY IN HERE`.

## Assumptions to replace with your own data

The 23% win rate and 8R average winner are borrowed from published trader
statistics. The winner-size spread, gap frequency and cash-cap frequency are
placeholders. Phase 2 replaces them with estimates from your own trade log:
set `TRADE_LOG` in notebook 02 to a CSV with a column `R` (result of each
closed trade in R, oldest first), or the columns `pnl` and `risk_dollars`.
