# Linear Algebra Trading Lab — Manual

This manual covers Phases 0 to 6 of the lab: what each part does, how the
engines work, how stocks are selected, what every term and abbreviation
means, and what the lab leaves out.

The lab is a learning project. It is a study tool, not financial advice.
Every result depends on the inputs, and several inputs are assumptions.

Contents

1. What the lab is for
2. Structure: files and data flow
3. Phase by phase
4. Logic of the engines
5. How the selection works
6. What the lab ignores, and the likely impact
7. Assumptions and tunable numbers
8. Abbreviations
9. Glossary: trading terms
10. Glossary: statistics and simulation terms
11. Glossary: linear algebra terms
12. Glossary: terms introduced by this lab
13. How to run and how to use your own data

---

## 1. What the lab is for

The trading method is a momentum breakout system on US stocks: long only,
no leverage, at most two open positions, a fixed small risk per trade (1R),
stops based on the average daily range, a low win rate and large winners.

The lab answers four questions about that method, in order.

| Question | Phase |
|---|---|
| If my edge is what I assume, what range of futures should I expect? | 1 |
| What is my edge, measured from my own trades, and how sure am I? | 2 |
| Given that uncertainty, how much should I risk per trade? | 3 |
| Which stocks fit the method today, and which of them are one bet? | 4 |
| Which two do I take, in what size, and which rule limits me? | 5 |
| Put together: what do my rules allow today? | 6 |

Phase 0 teaches the linear algebra the other phases use.

---

## 2. Structure: files and data flow

All files sit in the folder `03_trading_lab`.

| File | Type | Role |
|---|---|---|
| `00_setup_linear_algebra.ipynb` | notebook | Phase 0: tool check and linear algebra warm-up |
| `01_monte_carlo_engine.ipynb` | notebook | Phase 1: simulate futures with a fixed edge |
| `02_bayesian_edge_tracker.ipynb` | notebook | Phase 2: estimate the edge from a trade log |
| `03_bayesian_monte_carlo.ipynb` | notebook | Phase 3: simulate with an uncertain edge, choose risk |
| `04_momentum_scanner.ipynb` | notebook | Phase 4: scan, score and group stocks |
| `05_two_slot_allocator.ipynb` | notebook | Phase 5: pick two positions and their sizes with a linear program |
| `06_daily_report.ipynb` | notebook | Phase 6: run every phase, one dashboard, one verdict |
| `mc_engine.py` | module | simulation functions (Phases 1 and 3) |
| `bayes_edge.py` | module | Bayesian update functions and sizing rule (Phases 2 and 3) |
| `scanner.py` | module | download, metrics, filters, score, PCA, themes (Phase 4) |
| `allocator.py` | module | linear program: build, solve, shadow prices, orders (Phase 5) |
| `daily_report.py` | module | the whole pipeline in one call; also runs from a terminal (Phase 6) |
| `lab_style.py` | module | chart colours and matplotlib defaults |
| `sample_trade_log.csv` | data | 40 made-up trades for practice; not real trades |
| `data/prices_*.csv` | data | saved price snapshot (close, high, low, volume) |
| `candidates.csv` | output | Phase 4 result, input for Phase 5 |
| `allocation.csv` | output | Phase 5 result: the order ticket |
| `reports/daily_report_<date>.md`, `.png` | output | Phase 6 result: written report and dashboard |
| `requirements.txt` | setup | libraries to install |
| `README.md`, `MANUAL.md` | docs | overview and this manual |

Notebooks hold the explanation, the inputs and the charts. Modules hold the
calculations. A notebook imports a module and calls its functions, so the
same calculation is never written twice.

Data flow:

```
your trade log ──► Phase 2 (belief about the edge)
                        │
                        ▼
assumed edge ──► Phase 1 (engine) ──► Phase 3 (futures with uncertain edge)
                                              │
                                              ▼
                                      risk per trade

Yahoo prices ──► Phase 4 (scan, score, themes) ──► candidates.csv
                                                         │
                                                         ▼
                              Phase 5 (linear program) ──► allocation.csv
```

Each notebook has one cell marked `KEY IN HERE`. Edit only that cell, then
run the whole notebook.

---

## 3. Phase by phase

### Phase 0 — Setup and linear algebra warm-up

Purpose: confirm that Python and the libraries work, then practise the six
ideas the lab is built on.

| Section | Idea | Used later in |
|---|---|---|
| 1 | vector, dot product | expectancy = probabilities · sizes |
| 2 | matrix, rows and columns | the Monte Carlo grid |
| 3 | matrix product `@`, transpose `.T` | portfolio return, covariance |
| 4 | covariance matrix, quadratic form `wᵀΣw` | two-slot risk |
| 5 | Cholesky factor | simulating correlated slots |
| 6 | eigenvectors, eigenvalues | finding hidden drivers (PCA) |

Key result: the rule "two slots with correlation ρ swing √((1+ρ)/2) as much
as one double-size slot" is the 2×2 case of `wᵀΣw`.

### Phase 1 — Monte Carlo risk engine

Purpose: replace one smooth growth curve with the full range of possible
futures.

Inputs: starting equity, risk per trade, win rate, average winner in R,
number of trades, number of simulated futures, random seed.

Steps: one future with a loop; ten thousand futures with one matrix; fan
chart; drawdown histogram; losing-streak histogram; rule scenarios (gaps,
cash cap, higher risk, half the edge); two correlated slots; risk map;
milestone table.

Outputs: percentiles of final equity, maximum drawdown, chance of a 30% and
a 50% drawdown, longest losing streak, chance of reaching each multiple of
the account.

Headline results at the baseline (assumed 23% win rate, 8R average winner,
1% risk, 300 trades): the median future ends near $31,500 against $48,720 on
the smooth curve; the median worst drawdown is 20%; 99.8% of futures contain
ten or more losers in a row.

### Phase 2 — Bayesian edge tracker

Purpose: estimate the win rate, the average winner and the expectancy from a
trade log, each with its uncertainty.

Inputs: a trade log CSV (a column `R`, or `pnl` and `risk_dollars`), and the
prior: its centre and its strength.

Steps: load the log; Bayes' rule by hand on a grid; the Beta shortcut;
belief replayed trade by trade; belief about the average winner; belief
about expectancy; sizing decision; how many trades are needed; sensitivity
to the prior.

Outputs: credible intervals, P(edge > 0), a risk setting (0.5R, 1R or
pause), and a warning when the prior dominates the answer.

Headline results on the made-up sample log: win rate 13% to 30%; median
expectancy +0.11R; P(edge > 0) = 62%; risk setting 0.5R; the answer moves
from 20% to 99% across prior strengths, so 40 trades settle nothing.

### Phase 3 — Bayesian Monte Carlo

Purpose: join Phases 1 and 2. Every simulated future draws its own edge from
the Phase 2 belief and trades with it.

Inputs: the trade log, risk per trade, a drawdown limit and the largest
accepted chance of reaching it.

Steps: load the belief; broadcasting example; three runs (borrowed edge,
plug-in median, uncertain edge); split of futures by the sign of the true
edge; sweep of risk per trade; growth-rate curve; decision.

Outputs: comparison table, risk sweep table, growth-maximising risk, and the
risk per trade the evidence supports.

Headline results on the sample log: median final equity near $2,400 against
$31,500 with the borrowed edge; 43% of futures end below the start; the
chance of ending below the start stays between 40% and 48% at every risk
setting; supported risk 0.3% per trade.

### Phase 4 — Momentum scanner and themes

Purpose: find the stocks that fit the method today and group them into
themes, so two slots are never one bet.

Inputs: the price snapshot or a fresh download, and the thresholds for
price, dollar volume, ADR, momentum rank and theme correlation.

Steps: load prices; market regime gate; metrics; filter funnel; momentum
map; setup score; returns and covariance matrices; PCA; themes as a graph;
candidate list.

Outputs: the state of the regime gate, a scored candidate table with a theme
for each stock, and `candidates.csv`.

Headline results on the snapshot to 13 November 2026: regime gate closed;
180 stocks reduce to 10 candidates; the first principal component explains
33% of movement; eight themes among 89 high-ADR stocks.

### Phase 5 — Two-slot allocator

Purpose: choose which candidates fill the two slots, and with how many
shares, by solving a linear program; then measure which rule limits the
result.

Inputs: `candidates.csv`, account size, risk per trade, stop distance in
ADR, slot count, gap budget, and the largest extension allowed.

Steps: prepare per-stock numbers; show the program as three arrays; solve;
draw the feasible region; shadow prices; cost of each rule; stop width and
risk grid; account size; correlation of the pair; order ticket.

Outputs: the picks with shares, stop prices, cost and risk; the binding
limits and their shadow prices; `allocation.csv`.

Headline results on the snapshot to 13 November 2026 ($2,000, 1% risk,
0.5 ADR stops): MRNA 1 share and CVNA 10 shares; 1.50R deployed of 2R; 47%
of cash used; the gap budget binds and cash does not; the regime gate is
closed, so the ticket is an exercise.

### Phase 6 — Daily report

Purpose: run every phase in order and state what the rules allow today.

Inputs: account size, trade log, whether to refresh prices, the risk rule,
stop distance, gap budget, drawdown limit and accepted chance.

Steps: load prices; scan; estimate the edge from the trade log; find the
supported risk; allocate at that risk; simulate the outlook at that risk;
write the verdict; draw the dashboard; save the report.

Outputs: a verdict (GO, CAUTION or STOP) with one line per check, a
six-panel dashboard, a written report, and both saved in `reports/`.

Headline results on the snapshot to 13 November 2026 with the made-up
sample log: verdict STOP (regime gate closed); P(edge > 0) = 62%; supported
risk 0.3% per trade ($6); allocation, as an exercise, CELH 7 shares and
CVNA 3 shares; 40% of futures end below the start.

Note the difference from Phase 5. Phase 5 sizes positions at the 1% rule.
Phase 6 sizes them at the supported risk, which here is 0.3%. At $6 of risk
one MRNA share is 1.9R, more than the 1R cap, so MRNA cannot be bought and
the picks change.

---

## 4. Logic of the engines

### 4.1 Monte Carlo engine (`mc_engine.py`)

One trade result, in R:

1. Draw a uniform random number. If it is below the win rate, the trade wins.
2. A winner's size is drawn from a lognormal distribution whose mean is the
   average winner (8R) and whose shape is `win_sigma` (0.9). Most winners
   are modest and a few are very large.
3. A loser is −1R. With probability `gap_prob` it is −`gap_R` instead (the
   stock opened past the stop).
4. With probability `capped_prob` the trade is scaled by `capped_frac` (the
   cash cap made the position smaller than 1R).

All trades of all futures are held in one matrix `R` of shape
(paths, trades). Equity is

```
equity after trade t = start × (1 + R₁·risk) × (1 + R₂·risk) × … × (1 + R_t·risk)
```

computed for every future at once with `np.cumprod` along the trade axis.
Risk is a fraction of current equity, so position size grows and shrinks
with the account.

Derived measures:

- Maximum drawdown: for each future, the largest value of
  `1 − equity ÷ running peak`.
- Longest losing streak: the longest run of consecutive negative results.
- Milestone: the first trade at which the running peak reaches a multiple of
  the starting equity.

Two correlated slots: independent normal numbers `z` are mixed with the
Cholesky factor `L` of the 2×2 correlation matrix (`z @ L.T`), mapped to
uniform numbers with the normal CDF, and used as the win-or-loss draws of
slot A and slot B. Both slots are open in every round and their results add.
Only win or loss is correlated; winner sizes are independent.

Uncertain edge (`simulate_R_uncertain`): each future picks one row of the
Phase 2 posterior draws and keeps that win rate, average winner, winner
spread and average loser for all its trades. The per-future values are
column vectors of shape (paths, 1), broadcast across the trade matrix.

### 4.2 Bayesian engine (`bayes_edge.py`)

Win rate. The prior is Beta(a₀, b₀) with
`a₀ = prior win rate × strength` and `b₀ = (1 − prior win rate) × strength`.
After W wins and L losses the posterior is Beta(a₀ + W, b₀ + L). A trade
counts as a win when R > 0.

Average winner. The logarithm of each winner's size is modelled as Normal
with unknown mean and variance. The prior is Normal-Inverse-Gamma, centred
so that the implied average winner is 8R with spread 0.9, and worth
`size_strength` imaginary winners. The posterior is sampled: first the
variance, then the mean. The average winner of each draw is
`exp(mean + variance ÷ 2)`.

Average loser. A weighted average of the prior value (1R, worth
`loss_strength` imaginary losers) and the logged losers. It is a single
value, with no uncertainty.

Expectancy. For each of 20,000 draws:

```
expectancy = win rate × average winner − (1 − win rate) × average loser
```

P(edge > 0) is the share of draws above zero.

Sizing rule (`sizing_decision`):

| Evidence | Setting |
|---|---|
| fewer than 30 trades logged | 0.5R |
| P(edge > 0) ≥ 90% | 1R |
| 60% ≤ P(edge > 0) < 90% | 0.5R |
| P(edge > 0) < 60% | pause |

### 4.3 Risk decision (Phase 3)

Three limits are computed and the smallest is used:

1. Drawdown limit: the largest risk per trade, on a grid of 0.1% steps, at
   which the chance of the chosen drawdown (default 30%) is at or below the
   accepted chance (default 10%), over the uncertain-edge futures.
2. Evidence limit: the Phase 2 setting (1%, 0.5% or 0).
3. The rule: 1% of equity.

The growth-rate curve is the average of `log(1 + R × risk)` over all
simulated trades, for each risk setting. Its peak is the growth-maximising
(Kelly) risk. It is shown as an upper bound, not a target.

### 4.4 Scanner engine (`scanner.py`)

Described in section 5.

### 4.5 Allocator engine (`allocator.py`)

Per-stock numbers (`prepare`):

| Number | Formula |
|---|---|
| `stop_pct` | stop distance in ADR × ADR% ÷ 100 |
| `share_R` | price × `stop_pct` ÷ 1R (risk of one share, in R) |
| `cost_per_R` | 1R ÷ `stop_pct` (dollars of stock per 1R of risk) |
| `gap_R` | 1 ÷ stop distance in ADR (loss in R, per 1R risked, on a one-ADR gap) |
| `max_R` | the smaller of 1R and slot cash ÷ `cost_per_R` |
| `value` | setup score ÷ 100 |

Decision variables, for each candidate i: `s_i`, a whole number of shares,
and `x_i`, 1 if the stock is picked and 0 if not. The risk in stock i is
`y_i = share_R_i × s_i`.

Objective: maximise the sum of `value_i × y_i` (score-weighted risk).

Constraints, each one row of the matrix `A` in `A v ≤ b`:

| Row | Inequality | Rule it encodes |
|---|---|---|
| slots | Σ x_i ≤ 2 | at most two open positions |
| cash | Σ price_i × s_i ≤ equity | no leverage |
| gap | Σ gap_R_i × y_i ≤ gap budget | limit on the loss if every pick opens one ADR lower |
| theme T | Σ x_i over the theme ≤ 1 | one theme is one bet |
| link i | y_i − max_R_i × x_i ≤ 0 | no shares unless picked; at most 1R, or the slot's cash cap |

The program is solved with `scipy.optimize.milp` (the HiGHS solver), with
all variables integer.

Shadow prices (`shadow_prices`): the picks are held fixed and shares are
allowed to be fractional, which leaves a plain linear program in the risks
`y`. The solver's dual values are the shadow prices: the gain in objective
per unit of each limit. A limit with spare room has a shadow price of zero.

Cost of a rule: the program is solved again with that rule removed, and the
objectives are compared. This handles large changes, where a shadow price
(valid only for small changes) would mislead.

### 4.6 Daily report engine (`daily_report.py`)

`run(cfg)` calls the other engines in this order:

1. `scanner.load_prices` and `scanner.run_scan`: regime, filters, scores,
   themes, candidates.
2. `bayes_edge.sample_edge`: 20,000 draws of the edge from the trade log.
3. `supported_risk`: simulates uncertain-edge futures once, then finds the
   three limits of section 4.3 and takes the smallest.
4. `allocator.allocate`: on the candidates that are not extended, at the
   supported risk. The gap budget in R is the gap budget as a share of
   equity divided by the supported risk.
5. Outlook: the same simulated trades, compounded at the supported risk.
6. `verdict`: one line per check.

Verdict rules:

| Line | GO | CAUTION | STOP |
|---|---|---|---|
| Regime | gate open | — | gate closed |
| Edge | sizing rule says 1R | sizing rule says 0.5R | sizing rule says pause |
| Risk | supported risk equals the rule | supported risk is below the rule | supported risk is zero |
| Allocation | positions sized, gate open | gate closed, or nothing can be sized | no eligible candidate |

The overall verdict is STOP if any line is STOP, otherwise CAUTION if any
line is CAUTION, otherwise GO.

---

## 5. How the selection works

### 5.1 Universe

180 hand-picked liquid US stocks across sectors, plus SPY and QQQ as
benchmarks. One year of daily prices, adjusted for splits and dividends.

### 5.2 Market regime gate

On QQQ: the 10-day moving average is above the 20-day moving average, and
both are higher than five trading days earlier. If not, the gate is closed
and the scan is a watch list.

### 5.3 Metrics

| Metric | Formula |
|---|---|
| `ret_1m`, `ret_3m`, `ret_6m` | close today ÷ close 21, 63, 126 trading days ago − 1 |
| `mom_rank` | percentile rank of each return across the universe; the best of the three |
| `adr_pct` | 100 × average of (high ÷ low − 1) over the last 20 days |
| `dollar_vol_m` | average of (close × volume) over the last 20 days, in $ million |
| `trend_ok` | the stock's own 10-day MA above its 20-day MA, both rising over 5 days |
| `ext_adr` | (close ÷ 10-day MA − 1) × 100 ÷ `adr_pct` |
| `tightness` | 5-day average daily range ÷ 20-day average daily range |
| `vol_dryup` | 5-day average volume ÷ 50-day average volume |

### 5.4 Filters, applied in order

| Filter | Default | Reason |
|---|---|---|
| price | ≥ $5 | avoid very low-priced stocks |
| dollar volume | ≥ $20 million a day | can enter and exit |
| ADR | ≥ 4% | the stock moves enough to pay 8R |
| momentum rank | ≥ 90 | a leader on at least one horizon |
| trend | `trend_ok` is true | the stock's own short trend is up |

### 5.5 Setup score, 0 to 100

| Points | Part | Zero marks | Full marks |
|---|---|---|---|
| 40 | momentum rank | rank 50 | rank 100 |
| 25 | tightness | ratio 1.3 | ratio 0.5 |
| 15 | volume dry-up | ratio 1.3 | ratio 0.5 |
| 20 | not extended | 2 ADR from the 10-day MA | on the 10-day MA |

Each part is scaled in a straight line between the two ends and clipped.
The score orders the list. It has not been tested as a predictor.

### 5.6 Themes

1. Take every stock that passes the price, liquidity and ADR filters (wider
   than the final candidates, so links between sectors are visible).
2. Build the returns matrix of the last 120 trading days and its
   correlation matrix.
3. Link two stocks when their correlation is at or above 0.60.
4. Split the linked stocks into communities by modularity maximisation:
   groups with many links inside and few links to the outside. Each
   community is a theme (T1, T2, … by size). A stock with no link is `solo`.

Plain connected groups are not used, because a chain of single links would
merge unrelated sectors into one group.

### 5.7 Final list

Candidates are sorted by score. Within each theme only the best-scored
candidate is flagged `best_in_theme`; each `solo` stock is its own theme.
This applies rule B1, "one theme is one bet".

### 5.8 From candidates to positions (Phase 5)

1. Drop candidates further than 1 ADR above their 10-day MA (extended).
2. Solve the program of section 4.5. The optimiser prefers high scores, but
   a high-scored stock can lose its place when one share is too large a
   part of 1R, or when its gap loss uses too much of the gap budget.
3. Check the correlation of the chosen pair (below 0.30 green, 0.30 to 0.60
   amber, 0.60 or more red).
4. Read the regime gate. If it is closed, the ticket is an exercise.

---

## 6. What the lab ignores, and the likely impact

"Direction" says which way the omission pushes the results.

### Costs and execution

| Ignored | Direction | Size of impact |
|---|---|---|
| Commissions and fees | results too good | small at most brokers |
| Slippage on entries and stops | results too good | moderate; larger in fast, low-priced stocks |
| Whole-share rounding | results too good | large on $2,000: risk per trade is often well below 1R |
| Cash cap (Phase 3) | results too good | large for tight stops; Phase 1 shows a scenario |
| Gaps past the stop (Phase 3) | drawdowns too small | moderate; Phase 1 shows a scenario |
| Taxes | results too good | depends on the country |

### Behaviour of the edge

| Ignored | Direction | Size of impact |
|---|---|---|
| Edge changes with market regime | drawdowns too small | large; losses cluster in bad markets |
| Trades are not independent | streaks too short | moderate to large |
| The trader learns, pauses or quits | worst futures too bad | moderate; a pause rule cuts them short |
| Winner sizes follow an assumed lognormal shape | either | unknown until the log has many winners |
| The +3R trim and the 9 EMA trail | either | folded into the average winner, not modelled |
| Uncertainty of the average loser | range too narrow | small |

### Portfolio

| Ignored | Direction | Size of impact |
|---|---|---|
| Correlation of winner sizes between slots | drawdowns too small | small to moderate |
| Correlation rising in selloffs | drawdowns too small | large in a market break |
| Deposits and withdrawals | — | not modelled; deposits dominate early growth of a small account |

### Allocator

| Ignored | Direction | Size of impact |
|---|---|---|
| The objective is the untested setup score, not expected profit | unknown | large; "optimal" means consistent with the ranking and the rules |
| Entry at the breakout price, stop at the low of day | sizes differ | moderate; the program uses the snapshot close and a fixed fraction of ADR |
| Variance of the pair (`wᵀΣw`) | risk understated | small with the theme rule; a quadratic program would handle it |
| Positions already open, trading costs, decisions through time | — | not modelled; one day, from cash |
| Whole shares, in the shadow prices | prices approximate | moderate on a small account |

### Scanner

| Ignored | Direction | Size of impact |
|---|---|---|
| Forward test of the score | unknown | the score may have no predictive value |
| Whole-market universe | leaders overstated | "top 10% of 180" is much weaker than "top 1–2% of the market" |
| Hand-picked universe (selection and survivorship bias) | leaders overstated | moderate |
| Intraday data | entry rules unchecked | low of day, first 30 minutes and 5-minute break are not tested |
| Earnings dates, news, catalysts | risk understated | a candidate may report earnings tomorrow |
| Fundamentals, float, short interest | — | not read |
| Stability of correlation | themes may shift | 120 days of Pearson correlation is one window |

### Evidence

| Ignored | Direction | Size of impact |
|---|---|---|
| The borrowed 23% and 8R come from two exceptional traders | results too good | very large; this is the main assumption |
| A log that omits losing trades | edge overstated | very large; log every trade |
| The sample log is made up | — | its results describe nobody |

---

## 7. Assumptions and tunable numbers

| Number | Default | Where | Status |
|---|---|---|---|
| Win rate | 23% | `mc.Rules`, `be.Prior` | borrowed |
| Average winner | 8R | `mc.Rules`, `be.Prior` | borrowed |
| Winner spread `win_sigma` | 0.9 | `mc.Rules`, `be.Prior` | placeholder |
| Gap frequency, gap loss | 5% of losers, 2.5R | Phase 1 scenario | placeholder |
| Cash-cap frequency, size | 30% of trades, half size | Phase 1 scenario | placeholder |
| Prior strength, win rate | 20 imaginary trades | `be.Prior` | choice |
| Prior strength, winner size | 5 imaginary winners | `be.Prior` | choice |
| Sizing thresholds | 30 trades, 60%, 90% | `sizing_decision` | choice |
| Drawdown limit, accepted chance | 30%, 10% | Phase 3 | choice |
| Price, dollar volume, ADR floors | $5, $20M, 4% | Phase 4 | choice |
| Momentum rank floor | 90 | Phase 4 | choice |
| Score weights | 40 / 25 / 15 / 20 | `setup_score` | untested |
| Theme correlation, lookback | 0.60, 120 days | Phase 4 | choice |
| Stop distance | 0.5 ADR | Phase 5 | choice |
| Gap budget | 3% of equity | Phase 5 | choice |
| Largest extension allowed | 1 ADR above the 10-day MA | Phase 5 | choice |
| Objective value of a stock | setup score ÷ 100 | `allocator.prepare` | untested |

"Borrowed" means taken from published statistics of other traders.
"Placeholder" means a guess to be replaced by a measurement. "Choice" means
a preference you should set yourself. "Untested" means not checked against
outcomes.

---

## 8. Abbreviations

| Short | Full |
|---|---|
| 1R, R | one unit of risk; see glossary |
| ADR | average daily range |
| BE | breakeven |
| CDF | cumulative distribution function |
| CSV | comma-separated values (a plain text table file) |
| DD | drawdown |
| EMA | exponential moving average |
| ETF | exchange-traded fund |
| IV | implied volatility |
| LOD | low of day |
| LP | linear program |
| MA | moving average (simple, unless stated) |
| MC | Monte Carlo |
| MILP | mixed-integer linear program |
| NIG | Normal-Inverse-Gamma (a prior for an unknown mean and variance) |
| P(…) | probability of … |
| PB | pullback |
| PCA | principal component analysis |
| PC1 | first principal component |
| pct | percentile, or percent, as the context shows |
| QQQ | the ETF that tracks the Nasdaq-100 index |
| SPY | the ETF that tracks the S&P 500 index |
| ρ (rho) | correlation |
| Σ (Sigma) | covariance matrix |
| σ (sigma) | standard deviation |

---

## 9. Glossary: trading terms

**ADR (average daily range).** The average distance from a day's high to its
low, as a percentage. Here: the 20-day average of (high ÷ low − 1).

**Breakeven (BE).** Moving the stop to the entry price, so the remaining
position can no longer lose.

**Breakeven win rate.** The win rate at which expectancy is zero:
1 ÷ (1 + payoff). At an 8R payoff it is 11.1%.

**Breakout.** Price leaving a consolidation upward, usually on higher volume.

**Cash cap.** With no leverage and two slots, a position can cost at most
half the account. A very tight stop asks for more shares than that, so the
position is cut and the actual risk is less than 1R.

**Consolidation / contraction.** A period of narrowing daily ranges and
fading volume after a run-up.

**Dollar volume.** Price × shares traded; a measure of liquidity.

**Drawdown.** The fall from the highest equity so far to the current
equity, as a percentage. Maximum drawdown is the largest such fall.

**Edge.** A positive expectancy.

**Expectancy.** The average result of a trade:
win rate × average winner − loss rate × average loser, in R.

**Extended.** Price far above its short moving average. Here measured in ADR
units above the 10-day MA.

**Gap.** An open far from the previous close. A stop cannot protect a
position inside a gap.

**Gap-R.** The loss, in R, if the stock opens one ADR against the position:
ADR ÷ stop distance.

**Leader.** A stock among the strongest performers over 1, 3 or 6 months.

**Leverage.** Holding positions worth more than the account. Not used here.

**Liquidity.** How easily a position can be bought or sold without moving
the price.

**Moving average (MA).** The average close of the last N days.

**Payoff.** Average winner ÷ average loser.

**Position size.** Number of shares: 1R ÷ (entry − stop).

**R, 1R.** The money lost if a trade is stopped out. In this method 1R is 1%
of current equity. Results are stated in multiples of R: a +8R winner made
eight times what the trade risked.

**Regime.** The state of the overall market: trending up, sideways or down.

**Regime gate.** The rule that allows new breakout entries only when the
10-day MA is above the 20-day MA and both are rising.

**Risk per trade.** 1R as a fraction of equity.

**Slot.** One of the two allowed open positions.

**Stop.** The price at which a losing trade is closed.

**Theme.** A group of stocks that move together because they share a driver
(for example chips, or bitcoin miners).

**Trim.** Selling part of a position (here one third at +3R) and keeping the
rest.

**Trail.** Moving the stop up behind a rising price (here under the 9 EMA).

**Win rate.** The share of trades that make money.

---

## 10. Glossary: statistics and simulation terms

**Bayes' rule.** Belief after the data is proportional to belief before the
data times how well each candidate explains the data:
posterior ∝ prior × likelihood.

**Beta distribution.** A distribution over values between 0 and 1, used for
an unknown win rate. Beta(a, b) behaves like having seen a wins and b
losses.

**Bootstrap.** Estimating uncertainty by resampling the data with
replacement.

**Conjugate prior.** A prior whose posterior has the same form, so updating
is simple arithmetic. Beta is conjugate for win or loss data.

**Correlation (ρ).** A number from −1 to +1 for how closely two series move
together. Covariance divided by both standard deviations.

**Covariance.** The average product of two series' deviations from their
means.

**Credible interval.** A range that holds the true value with a stated
probability, given the data and the prior. A 90% interval runs from the 5th
to the 95th percentile of the posterior.

**Distribution.** The full set of possible values with their probabilities.

**Fan chart.** A chart of percentile bands over time, widening like a fan.

**Fat tail.** Extreme outcomes occurring more often than a normal
distribution predicts.

**Growth rate (log growth).** The average of log(1 + return). It is what
compounds in the long run.

**Kelly fraction.** The bet size that maximises long-run growth. Betting
more lowers growth and raises the risk of ruin. Practitioners use a fraction
of it.

**Likelihood.** How probable the observed data is, for one candidate value
of the unknown.

**Lognormal.** The distribution of a number whose logarithm is normal.
Always positive, with a long right tail. Used for winner sizes.

**Median.** The middle value: half of the outcomes are above it.

**Monte Carlo simulation.** Estimating a range of outcomes by generating
many random scenarios and counting.

**Path, future.** One simulated sequence of trades.

**Percentile.** The value below which a given percentage of outcomes fall.
The 5th percentile is a bad-luck outcome; the 95th is a good-luck one.

**Posterior.** The belief after seeing the data.

**Prior.** The belief before seeing the data.

**Prior strength.** How much the prior counts, stated as a number of
imaginary observations.

**Seed.** The starting value of the random number generator. The same seed
gives the same random numbers, so results can be repeated.

**Standard deviation (σ), volatility.** The typical size of deviations from
the mean.

**Variance.** Standard deviation squared.

---

## 11. Glossary: linear algebra terms

**Vector.** An ordered list of numbers.

**Matrix.** A table of numbers with rows and columns. Its shape is
(rows, columns).

**Dot product.** Multiply matching entries of two vectors and add.

**Matrix product (`@`).** Combine rows of the first matrix with columns of
the second. Shapes (m, n) @ (n, k) give (m, k).

**Transpose (`.T`).** Swap rows and columns.

**Broadcasting.** NumPy stretching a smaller array (for example a column of
shape (paths, 1)) across a larger one (paths, trades) so they can be
combined without a loop.

**Cumulative product (`cumprod`).** Running product along a row. It turns
per-trade growth factors into an equity path.

**Returns matrix (R in Phase 4).** Rows are days, columns are stocks, entries
are daily returns.

**Covariance matrix (Σ).** A square table holding the covariance of every
pair of stocks. Σ = RᵀR ÷ (T − 1) on returns with their means removed.

**Correlation matrix.** The covariance matrix scaled so every diagonal entry
is 1.

**Quadratic form (wᵀΣw).** The variance of a portfolio with weights w.

**Cholesky factor (L).** A lower-triangular matrix with Σ = LLᵀ. Multiplying
independent random numbers by L gives them the correlation in Σ.

**Eigenvector, eigenvalue.** A direction that a matrix only stretches, and
the amount of stretch. For a covariance matrix, eigenvectors are the main
directions of joint movement and eigenvalues are their variances.

**Principal component analysis (PCA).** Finding those directions and ranking
them by the share of variance they explain.

**Loading.** A stock's weight in a principal component.

**Linear program (LP).** Choosing values for decision variables to maximise
a linear objective `cᵀv` subject to linear limits `A v ≤ b`.

**Decision variable.** A quantity the optimiser is free to choose (here,
shares and pick flags).

**Objective.** The quantity being maximised.

**Constraint.** A limit the solution must obey; one row of `A` and one
entry of `b`.

**Feasible region.** All combinations of the decision variables that obey
every constraint. For a linear program it is a shape with flat sides, and
the optimum sits at one of its corners.

**Binding constraint.** A limit that is fully used at the optimum. A limit
with spare room is slack.

**Shadow price (dual value, marginal value).** The gain in objective from
relaxing a limit by one unit. Zero for a slack limit.

**Integer program, mixed-integer linear program (MILP).** A linear program
in which some or all variables must be whole numbers.

**Relaxation.** The same program with the whole-number requirement dropped.
Its optimum is at least as good as the integer optimum.

**Adjacency matrix.** A square table saying which pairs of nodes in a graph
are linked. A thresholded correlation matrix is one.

**Graph, node, edge.** A set of points (nodes) and links between them
(edges). Here nodes are stocks and edges are strong correlations.

**Community.** A group of nodes with many links inside and few to the
outside.

**Modularity.** A score for how well a split into communities matches the
links. The theme finder searches for a high-modularity split.

---

## 12. Glossary: terms introduced by this lab

**Borrowed edge.** The 23% win rate and 8R average winner taken from
published trader statistics, used before your own data exists.

**Plug-in run.** A simulation that uses the single best estimate of the edge
as if it were certain (Phase 3, run B).

**Uncertain-edge run.** A simulation in which each future draws its own edge
from the posterior (Phase 3, run C).

**True edge (of a future).** The expectancy that one simulated future drew
and trades with.

**Evidence limit.** The risk setting from the Phase 2 rule.

**Drawdown limit (risk).** The largest risk per trade that keeps the chance
of a chosen drawdown within the accepted chance.

**Supported risk.** The smallest of the drawdown limit, the evidence limit
and the 1% rule.

**Momentum rank (`mom_rank`).** A stock's best percentile rank, across the
universe, of its 1-, 3- and 6-month returns.

**Tightness.** 5-day average daily range ÷ 20-day average daily range.
Below 1 means the stock is contracting.

**Volume dry-up (`vol_dryup`).** 5-day average volume ÷ 50-day average
volume. Below 1 means volume is fading.

**Extension (`ext_adr`).** Distance of price above its 10-day MA, in ADR
units.

**Setup score.** A 0 to 100 ranking number built from momentum rank,
tightness, volume dry-up and extension.

**Filter funnel.** The count of stocks left after each filter in turn.

**Solo.** A stock with no correlation link at or above the threshold.

**Best in theme.** The highest-scored candidate of its theme.

**Watch list.** The scan output while the regime gate is closed.

**Share risk (`share_R`).** The risk of one share, in R. It measures how
coarse the sizing is: a value of 0.57 means positions come in steps of 0.57R.

**Cost per R (`cost_per_R`).** Dollars of stock that carry 1R of risk:
1R ÷ stop distance. A tight stop makes it large.

**Risk cap (`max_R`).** The most risk one slot may carry: 1R, or less when
the slot's cash runs out first.

**Gap budget.** The largest total loss accepted if every open position
opens one ADR lower, stated in R or as a share of equity.

**Score-weighted risk.** The allocator's objective: the sum over picks of
setup score ÷ 100 times risk in R.

**Link constraint.** The row that ties shares to the pick flag: no shares
unless picked, and no more risk than the risk cap.

**Order ticket.** The allocator's output: picks, shares, stop prices, cost
and risk.

**Verdict.** The daily report's conclusion: GO, CAUTION or STOP, with one
line per check (regime, edge, risk, allocation).

**Outlook.** The range of simulated futures at the supported risk.

**Dashboard.** The six-panel figure of the daily report.

**Eligible candidate.** A scan candidate that is not extended beyond the
allowed distance above its 10-day MA.

---

## 13. How to run and how to use your own data

### 13.1 One-time setup

1. Install Python 3.11 or newer (python.org, or Anaconda).
2. Put the `03_trading_lab` folder anywhere on your computer. Keep every
   file in that one folder; the notebooks import the `.py` modules from it.
3. Open a terminal (Windows: Anaconda Prompt or PowerShell) and go to the
   folder:

   ```
   cd path\to\03_trading_lab
   ```

4. Install the libraries:

   ```
   pip install -r requirements.txt
   ```

5. Start Jupyter:

   ```
   jupyter notebook
   ```

   A browser page opens and lists the files.

### 13.2 Running a notebook

1. Click the notebook to open it.
2. Edit only the cell marked `KEY IN HERE`.
3. Choose `Kernel ▸ Restart & Run All` (in newer Jupyter:
   `Run ▸ Restart Kernel and Run All Cells`).
4. Read from the top. Tables and charts appear under each cell.

Always run the whole notebook. Running single cells out of order leaves old
values in memory and gives wrong results.

### 13.3 Order, inputs and outputs

| Step | Notebook | Needs | Writes | Internet |
|---|---|---|---|---|
| 0 | `00_setup_linear_algebra` | nothing | nothing | no |
| 1 | `01_monte_carlo_engine` | nothing | nothing | no |
| 2 | `02_bayesian_edge_tracker` | a trade log CSV | nothing | no |
| 3 | `03_bayesian_monte_carlo` | the same trade log | nothing | no |
| 4 | `04_momentum_scanner` | `data/` snapshot, or a download | `candidates.csv` | only with `REFRESH = True` |
| 5 | `05_two_slot_allocator` | `candidates.csv` from step 4 | `allocation.csv` | no |
| 6 | `06_daily_report` | trade log, `data/` snapshot or a download | `reports/…` | only with `refresh = True` |

Notebooks 0 to 3 stand alone and can run in any order. Notebook 5 must run
after notebook 4. Notebook 6 does not need the others to have run: it calls
the modules itself.

### 13.4 Two ways to use the lab

To learn: run notebooks 0 to 6 once each, in order, and do the exercises at
the end of each.

Each trading day: run only notebook 6 with `refresh = True`, or from a
terminal:

```
python daily_report.py --refresh
python daily_report.py --refresh --equity 2000 --log my_trades.csv
```

Open notebooks 4 and 5 when you want the detail behind the scan or the
allocation.

### 13.5 Your own data

Your trade log (notebooks 2, 3 and 6). Make a CSV with one row per closed
trade, oldest first, and either a column `R`, or the columns `pnl` and
`risk_dollars`. Example:

```
date,ticker,R
2026-06-01,ABCD,-1.0
2026-06-03,EFGH,4.2
```

Save it in the lab folder and put its name in `TRADE_LOG` (notebooks 2 and
3) or `trade_log` (notebook 6). Include every trade, losers above all.

Fresh prices (notebooks 4 and 6). Set `REFRESH = True` (notebook 4) or
`refresh = True` (notebook 6). This needs internet access to Yahoo Finance
and overwrites the snapshot in `data/`. If the download fails, the notebook
says so and uses the saved snapshot.

Your account. Set the equity and the risk rule in the `KEY IN HERE` cells.

### 13.6 Changing the lab

- Universe: edit the `UNIVERSE` list in `scanner.py`.
- Scan thresholds: the `KEY IN HERE` cell of notebook 4, or the arguments of
  `run_scan` in `scanner.py` (used by the daily report).
- Score weights: `setup_score` in `scanner.py`.
- Sizing thresholds: `sizing_decision` in `bayes_edge.py`.
- A new allocator constraint: add a row in `build_problem` in `allocator.py`.
- Daily report defaults: the `Config` class in `daily_report.py`.

After editing a `.py` module, restart the notebook kernel so the change is
loaded.

### 13.7 Common problems

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'mc_engine'` | Jupyter was started in another folder, or files were separated | start Jupyter inside `03_trading_lab`; keep all files together |
| `ModuleNotFoundError: No module named 'yfinance'` (or another library) | libraries not installed | `pip install -r requirements.txt` |
| `FileNotFoundError: candidates.csv` | notebook 5 run before notebook 4 | run notebook 4 first |
| "Download failed … using the saved snapshot" | no internet, or Yahoo is blocked | check the connection; the snapshot still works |
| `ValueError: Trade log needs a column 'R' …` | the log has other column names | rename the columns as in 13.5 |
| A changed `.py` file has no effect | the kernel still holds the old module | `Kernel ▸ Restart & Run All` |
| Numbers differ slightly from this manual | prices were refreshed, or inputs changed | expected |
