"""Backtest of the scanner's setup score.

The question: does a higher setup score lead to a better outcome?

Method, with no look-ahead:

1. Step through history one scan date at a time (every 5 trading days).
2. On each date, cut the price tables at that date and run the scanner's
   own functions (``compute_metrics``, ``apply_filters``, ``setup_score``),
   so the test uses exactly the code the daily report uses.
3. For every stock that passes the price, liquidity and ADR filters, record
   the score, the filter flags, and what happened next:
   * forward returns over 5, 10 and 20 trading days, from the next open
   * the result in R of a trade run by the lab's rules (see
     ``simulate_trade``)

Known weaknesses: the universe is today's hand-picked list (survivorship
bias), entries are at the next day's open (the real entry is an intraday
breakout), and scan dates overlap in time.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import scanner as sc

DATA_DIR = Path(__file__).parent / "data"
HIST_FIELDS = ["Open", "High", "Low", "Close", "Volume"]
WARMUP = 130          # trading days needed before the first scan date
HORIZONS = [5, 10, 20]


def download_history(period="5y"):
    """Download long daily history and save it compressed in ``data/``."""
    import yfinance as yf

    raw = yf.download(list(sc.UNIVERSE) + sc.BENCHMARKS, period=period,
                      progress=False, auto_adjust=True, threads=True)
    DATA_DIR.mkdir(exist_ok=True)
    prices = {}
    for field in HIST_FIELDS:
        frame = raw[field].dropna(axis=1, how="all").sort_index()
        frame.index = pd.to_datetime(frame.index).tz_localize(None)
        prices[field] = frame
        frame.round(3).to_csv(DATA_DIR / f"history_{field.lower()}.csv.gz")
    return prices


def load_history(refresh=False, period="5y"):
    """Return the long history, from the saved files unless ``refresh``."""
    if refresh:
        try:
            prices = download_history(period)
            if len(prices["Close"]) > 400:
                return prices
            print("Download returned too little data; using the saved history.")
        except Exception as error:
            print(f"Download failed ({type(error).__name__}); using the saved history.")
    return {field: pd.read_csv(DATA_DIR / f"history_{field.lower()}.csv.gz",
                               index_col=0, parse_dates=True)
            for field in HIST_FIELDS}


def simulate_trade(o, h, l, c, ema, start, stop_dist, trim_R=3.0, max_hold=40):
    """Run one long trade by the lab's rules and return its result in R.

    ``o, h, l, c, ema`` are arrays of open, high, low, close and the 9-day
    EMA for one stock. The trade enters at the open of bar ``start``.

    Rules, checked bar by bar:

    * stop at ``entry - stop_dist``; if the bar opens below the stop the
      exit is at the open (a gap), otherwise at the stop
    * at ``+trim_R`` sell one third and move the stop to the entry price
    * from the third bar on, or after the trim, exit the rest on a close
      below the 9-day EMA
    * exit at the close after ``max_hold`` bars

    When a bar touches both the stop and the trim level, the stop is taken
    first (the cautious reading of a daily bar).

    Returns (R, bars_held, exit_reason), or None if there is no entry.
    """
    n = len(o)
    if start >= n or np.isnan(o[start]) or stop_dist <= 0:
        return None
    entry = o[start]
    stop = entry - stop_dist
    target = entry + trim_R * stop_dist
    banked, size, trimmed = 0.0, 1.0, False

    last = min(start + max_hold, n - 1)
    for i in range(start, last + 1):
        if np.isnan(c[i]):
            return None
        if o[i] <= stop:
            return banked + size * (o[i] - entry) / stop_dist, i - start, "gap"
        if l[i] <= stop:
            reason = "breakeven" if trimmed else "stop"
            return banked + size * (stop - entry) / stop_dist, i - start, reason
        if not trimmed and h[i] >= target:
            banked += (1.0 / 3.0) * trim_R
            size, trimmed, stop = 2.0 / 3.0, True, entry
        if (trimmed or i - start >= 2) and c[i] < ema[i]:
            return banked + size * (c[i] - entry) / stop_dist, i - start, "trail"
    return banked + size * (c[last] - entry) / stop_dist, last - start, "time"


def build_panel(prices, step=5, stop_adrs=(0.5, 1.0)):
    """One row per (scan date, stock) with the score and what happened next.

    Only stocks that pass the price, liquidity and ADR filters on the scan
    date are kept. Columns added to the scanner's metrics:

    * ``gate``       market regime gate open on the scan date
    * ``fwd_5/10/20`` return from the next open to the close N bars later
    * ``R_<stop>``   trade result in R with a stop of <stop> ADR
    * ``bars_<stop>``, ``exit_<stop>``  holding time and exit reason
    """
    close, opens = prices["Close"], prices["Open"]
    high, low = prices["High"], prices["Low"]
    dates = close.index
    ema9 = close.ewm(span=9, adjust=False).mean()

    arrays = {t: (opens[t].to_numpy(), high[t].to_numpy(), low[t].to_numpy(),
                  close[t].to_numpy(), ema9[t].to_numpy())
              for t in close.columns if t not in sc.BENCHMARKS}

    rows = []
    last_start = len(dates) - max(HORIZONS) - 2
    for pos in range(WARMUP, last_start, step):
        window = {f: prices[f].iloc[:pos + 1] for f in sc.FIELDS}
        flt = sc.apply_filters(sc.compute_metrics(window))
        flt = flt[flt["f_price"] & flt["f_liquid"] & flt["f_adr"]].copy()
        if flt.empty:
            continue
        flt["score"] = sc.setup_score(flt)
        gate = sc.market_regime(window["Close"], "QQQ")["gate_open"]

        for ticker, m in flt.iterrows():
            o, h, l, c, e = arrays[ticker]
            start = pos + 1
            if np.isnan(o[start]):
                continue
            row = m.to_dict()
            row.update(date=dates[pos], ticker=ticker, gate=gate)
            for k in HORIZONS:
                row[f"fwd_{k}"] = c[start + k - 1] / o[start] - 1.0
            adr_dollars = m["adr_pct"] / 100.0 * o[start]
            for s in stop_adrs:
                trade = simulate_trade(o, h, l, c, e, start, s * adr_dollars)
                if trade:
                    row[f"R_{s}"], row[f"bars_{s}"], row[f"exit_{s}"] = trade
            rows.append(row)

    panel = pd.DataFrame(rows)
    flags = ["trend_ok", "above_ma50", "f_price", "f_liquid", "f_adr",
             "f_leader", "f_trend", "passed", "gate"]
    panel[flags] = panel[flags].astype(bool)
    return panel.set_index(["date", "ticker"]).sort_index()


def rank_ic(panel, signal, outcome, min_names=5):
    """Spearman rank correlation of ``signal`` with ``outcome``, per date.

    Returns a Series indexed by date. Dates with fewer than ``min_names``
    stocks are skipped.
    """
    def one(day):
        day = day[[signal, outcome]].dropna()
        if len(day) < min_names or day[signal].nunique() < 2:
            return np.nan
        return day[signal].rank().corr(day[outcome].rank())
    return panel.groupby(level="date").apply(one).dropna()


def ic_summary(ic):
    """Mean IC, its t-statistic and the share of dates with a positive IC."""
    n = len(ic)
    mean, sd = ic.mean(), ic.std(ddof=1)
    return {"dates": n, "mean IC": mean,
            "t-stat": mean / (sd / np.sqrt(n)) if n > 1 and sd > 0 else np.nan,
            "% dates positive": 100 * np.mean(ic > 0)}


def trade_stats(R):
    """Win rate, average winner, average loser and expectancy of R results."""
    R = np.asarray(R, dtype=float)
    R = R[~np.isnan(R)]
    if len(R) == 0:
        return {"trades": 0}
    wins, losses = R[R > 0], R[R <= 0]
    return {"trades": len(R), "win rate %": 100 * len(wins) / len(R),
            "avg winner R": wins.mean() if len(wins) else np.nan,
            "avg loser R": losses.mean() if len(losses) else np.nan,
            "expectancy R": R.mean(), "median R": np.median(R)}


def bootstrap_by_date(panel, column, stat=np.mean, draws=2000, seed=0):
    """Bootstrap a statistic of ``column`` by resampling whole scan dates.

    Trades opened on the same date share the same market, so they are not
    independent. Resampling dates, not single trades, keeps that link and
    gives a more honest interval. Returns the array of bootstrap values.
    """
    rng = np.random.default_rng(seed)
    groups = [g[column].dropna().to_numpy() for _, g in panel.groupby(level="date")]
    groups = [g for g in groups if len(g)]
    out = np.empty(draws)
    for d in range(draws):
        pick = rng.integers(0, len(groups), len(groups))
        out[d] = stat(np.concatenate([groups[i] for i in pick]))
    return out


def bootstrap_diff(panel_a, panel_b, column, draws=2000, seed=0):
    """Bootstrap of mean(A) - mean(B), resampling scan dates in each group."""
    a = bootstrap_by_date(panel_a, column, np.mean, draws, seed)
    b = bootstrap_by_date(panel_b, column, np.mean, draws, seed + 1)
    return a - b
