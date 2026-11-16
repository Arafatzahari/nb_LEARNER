# Daily report — prices to 2026-11-13

Account $2,000 · trade log `sample_trade_log.csv` (40 trades) · study tool, not advice.

## Verdict: STOP

- **STOP** — Regime gate closed. Your rule allows no new breakout entries.
- **CAUTION** — P(edge > 0) = 62% from 40 trades. Evidence supports half risk.
- **CAUTION** — Supported risk 0.3% per trade ($6); your rule is 1.0%.
- **CAUTION** — Allocation, as an exercise only: CELH x7, CVNA x3.

## 1. Market regime

QQQ close 679.89, 10-day MA 677.40, 20-day MA 695.45. Gate closed.

## 2. Scan

Universe 180 → Price 175 → Liquidity 175 → ADR 89 → Leader 22 → Trend 10

|      |   price |   adr_pct |   mom_rank |   ext_adr |   tightness |   score | theme   |
|:-----|--------:|----------:|-----------:|----------:|------------:|--------:|:--------|
| MRNA |  223.37 |     10.2  |     100    |     -0.78 |        0.7  |    84.2 | solo    |
| CELH |   32.42 |      4.74 |      95.56 |      0.53 |        0.8  |    77   | solo    |
| CVNA |   72.37 |      5.12 |      98.33 |     -0.24 |        0.94 |    76.7 | solo    |
| ELF  |  117.98 |      4.63 |      98.89 |      0.57 |        0.87 |    68.8 | solo    |
| RUN  |    8.63 |      7.48 |      92.22 |     -0.58 |        0.92 |    63.6 | solo    |
| RIOT |   17.52 |      9.35 |      92.78 |      0.87 |        0.82 |    61.4 | T5      |
| DUOL |  165.31 |      5.88 |      97.78 |      1.25 |        1.07 |    57.5 | solo    |
| APP  |  409.1  |      5.42 |     100    |      3.08 |        1.04 |    55.5 | solo    |
| LUNR |   13    |      9.25 |      91.11 |      1.8  |        1.14 |    39.8 | T2      |
| TTD  |   15.68 |      5.04 |      98.89 |      2.09 |        1.52 |    39.1 | solo    |

## 3. Edge (from the trade log)

|              |    5% |   median |   95% |
|:-------------|------:|---------:|------:|
| win_rate     |  0.13 |     0.21 |  0.3  |
| avg_win_R    |  2.89 |     4.23 |  7.22 |
| expectancy_R | -0.36 |     0.11 |  0.98 |

P(edge > 0) = 62%, between 60% and 90%. Stay at half risk.

## 4. Risk per trade

| Limit | Risk per trade |
|---|---|
| Drawdown limit (P(drawdown ≥ 30%) ≤ 10%) | 0.3% |
| Evidence limit | 0.5% |
| Your rule | 1.0% |
| **Supported (smallest)** | **0.3%** |

## 5. Allocation

|      |   price |   stop_price |   shares |   cost |   risk_R |   score | theme   |   risk $ |
|:-----|--------:|-------------:|---------:|-------:|---------:|--------:|:--------|---------:|
| CELH |   32.42 |        31.65 |        7 | 226.94 |     0.9  |    77   | solo    |     5.38 |
| CVNA |   72.37 |        70.52 |        3 | 217.11 |     0.93 |    76.7 | solo    |     5.56 |

Total cost $444.05 (22% of the account), total risk $10.94.

The regime gate is closed, so this allocation is an exercise.

## 6. Outlook over 300 trades at the supported risk

- Final account: 5th percentile $1,378, median $2,169, 95th percentile $4,870
- Chance of ending below the start: 40%
- Median worst drawdown: 11%; chance of 30% or more: 7%

## Limits of this report

- The setup score is untested as a predictor of returns.
- The prior on the edge is borrowed from other traders' statistics.
- Prices are daily closes; entry and stop rules need intraday data.
- No costs, slippage, earnings dates or news. See `MANUAL.md`, section 6.
