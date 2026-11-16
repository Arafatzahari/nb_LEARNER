"""Momentum scanner for US stocks.

Pipeline:

1. download daily prices for a fixed universe (or load the saved snapshot)
2. compute momentum, ADR, liquidity, trend and contraction for each stock
3. keep the leaders that pass the filters
4. score each survivor from 0 to 100
5. build the returns matrix, the correlation matrix and the PCA
6. group the survivors into themes (stocks that move together)

The universe, the thresholds and the score weights are starting values for
learning. None of them has been validated against forward returns.
"""
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
FIELDS = ["Close", "High", "Low", "Volume"]
BENCHMARKS = ["SPY", "QQQ"]

# A learning universe of liquid US names across sectors. It is hand-picked and
# small, so it carries selection bias. A real scan covers the whole market.
UNIVERSE = sorted(set("""
AAPL MSFT NVDA GOOGL AMZN META TSLA AVGO ORCL NFLX
AMD MU INTC QCOM TXN AMAT LRCX KLAC ASML TSM MRVL ARM ON MCHP SMCI ANET DELL
WDC STX COHR CRDO ALAB
CRM ADBE NOW SNOW PLTR DDOG NET MDB SHOP UBER ABNB APP TTD RBLX SPOT DASH
CRWD PANW ZS FTNT OKTA S
COIN HOOD SOFI AFRM XYZ PYPL MSTR MARA RIOT CLSK IREN
JPM BAC GS MS WFC C SCHW V MA AXP BLK
XOM CVX COP OXY SLB HAL EOG DVN MPC VLO PSX
CCJ UEC LEU OKLO SMR NNE VST CEG NRG GEV
FSLR ENPH RUN SEDG NEE
LLY NVO UNH JNJ PFE MRK ABBV AMGN GILD VRTX REGN MRNA ISRG HIMS
LMT RTX NOC GD BA GE RKLB ASTS LUNR KTOS AVAV
RIVN LCID NIO F GM
WMT COST TGT HD LOW NKE SBUX MCD CMG LULU CELH ELF CAVA
CAT DE HON UNP UPS FDX ETN PWR VRT
FCX NEM GOLD AA CLF NUE MP ALB
IONQ RGTI QBTS SOUN AI BBAI UPST CVNA DKNG RDDT DUOL AXON TOST
DIS CMCSA T VZ TMUS
""".split()))


def download_prices(tickers=None, period="1y"):
    """Download daily prices from Yahoo Finance and save a snapshot.

    Returns a dictionary of DataFrames (Close, High, Low, Volume), each with
    one row per trading day and one column per ticker. Tickers with no data
    are dropped. Prices are adjusted for splits and dividends.
    """
    import yfinance as yf

    tickers = list(tickers or UNIVERSE) + BENCHMARKS
    raw = yf.download(tickers, period=period, progress=False,
                      auto_adjust=True, threads=True)
    prices = {}
    for field in FIELDS:
        frame = raw[field].dropna(axis=1, how="all").sort_index()
        frame.index = pd.to_datetime(frame.index).tz_localize(None)
        prices[field] = frame
    DATA_DIR.mkdir(exist_ok=True)
    for field, frame in prices.items():
        frame.round(4).to_csv(DATA_DIR / f"prices_{field.lower()}.csv")
    return prices


def load_prices(refresh=False, period="1y"):
    """Return prices, from the saved snapshot unless ``refresh`` is True.

    If a refresh fails (no internet), the saved snapshot is used and the
    reason is printed.
    """
    if refresh:
        try:
            prices = download_prices(period=period)
            if len(prices["Close"]) > 150:
                return prices
            print("Download returned too little data; using the saved snapshot.")
        except Exception as error:               # no internet, blocked host
            print(f"Download failed ({type(error).__name__}); "
                  f"using the saved snapshot.")
    prices = {}
    for field in FIELDS:
        path = DATA_DIR / f"prices_{field.lower()}.csv"
        prices[field] = pd.read_csv(path, index_col=0, parse_dates=True)
    return prices


def market_regime(close, benchmark="QQQ"):
    """Regime gate on a benchmark: 10-day MA above 20-day MA, both rising."""
    px = close[benchmark].dropna()
    ma10, ma20 = px.rolling(10).mean(), px.rolling(20).mean()
    gate = (ma10.iloc[-1] > ma20.iloc[-1] and ma10.iloc[-1] > ma10.iloc[-6]
            and ma20.iloc[-1] > ma20.iloc[-6])
    return {"benchmark": benchmark, "close": px.iloc[-1],
            "ma10": ma10.iloc[-1], "ma20": ma20.iloc[-1], "gate_open": bool(gate)}


def compute_metrics(prices):
    """One row of scan metrics per stock (benchmarks excluded)."""
    close = prices["Close"].drop(columns=BENCHMARKS, errors="ignore")
    high = prices["High"][close.columns]
    low = prices["Low"][close.columns]
    volume = prices["Volume"][close.columns]

    last = close.iloc[-1]
    day_range = high / low - 1.0                      # daily high-to-low move
    ma10, ma20, ma50 = (close.rolling(n).mean() for n in (10, 20, 50))

    m = pd.DataFrame(index=close.columns)
    m["price"] = last
    m["ret_1m"] = close.iloc[-1] / close.iloc[-22] - 1.0
    m["ret_3m"] = close.iloc[-1] / close.iloc[-64] - 1.0
    m["ret_6m"] = close.iloc[-1] / close.iloc[-127] - 1.0
    m["adr_pct"] = 100 * day_range.iloc[-20:].mean()
    m["dollar_vol_m"] = (close * volume).iloc[-20:].mean() / 1e6
    m["trend_ok"] = ((ma10.iloc[-1] > ma20.iloc[-1])
                     & (ma10.iloc[-1] > ma10.iloc[-6])
                     & (ma20.iloc[-1] > ma20.iloc[-6]))
    m["above_ma50"] = last > ma50.iloc[-1]
    # Extension: how far price sits above the 10-day MA, in ADR units.
    m["ext_adr"] = (last / ma10.iloc[-1] - 1.0) * 100 / m["adr_pct"]
    # Contraction: recent daily ranges against the last month's ranges.
    m["tightness"] = day_range.iloc[-5:].mean() / day_range.iloc[-20:].mean()
    # Volume dry-up: recent volume against the last 50 days.
    m["vol_dryup"] = volume.iloc[-5:].mean() / volume.iloc[-50:].mean()

    # Momentum rank: percentile of each return across the universe, then the
    # best of the three. A stock leads if it leads on any one horizon.
    ranks = m[["ret_1m", "ret_3m", "ret_6m"]].rank(pct=True) * 100
    m["mom_rank"] = ranks.max(axis=1)
    return m.dropna(subset=["ret_6m", "adr_pct"])


def apply_filters(metrics, min_price=5.0, min_dollar_vol_m=20.0, min_adr=4.0,
                  min_mom_rank=90.0, require_trend=True):
    """Add one True/False column per filter and a ``passed`` column."""
    f = metrics.copy()
    f["f_price"] = f["price"] >= min_price
    f["f_liquid"] = f["dollar_vol_m"] >= min_dollar_vol_m
    f["f_adr"] = f["adr_pct"] >= min_adr
    f["f_leader"] = f["mom_rank"] >= min_mom_rank
    f["f_trend"] = f["trend_ok"] if require_trend else True
    f["passed"] = f[["f_price", "f_liquid", "f_adr", "f_leader", "f_trend"]].all(axis=1)
    return f


def setup_score(metrics):
    """Score from 0 to 100. Higher means closer to a textbook setup.

    40 points: momentum rank (stronger leader)
    25 points: tightness (daily ranges contracting)
    15 points: volume dry-up (volume fading in the consolidation)
    20 points: not extended (price near the 10-day MA, within 1 ADR)
    """
    mom = np.clip((metrics["mom_rank"] - 50) / 50, 0, 1)
    tight = np.clip((1.3 - metrics["tightness"]) / 0.8, 0, 1)
    dry = np.clip((1.3 - metrics["vol_dryup"]) / 0.8, 0, 1)
    near = np.clip(1.0 - metrics["ext_adr"].abs() / 2.0, 0, 1)
    return (40 * mom + 25 * tight + 15 * dry + 20 * near).round(1)


def returns_matrix(close, tickers, lookback=120):
    """Daily returns, shape (days, stocks), last ``lookback`` days."""
    return close[list(tickers)].pct_change().dropna(how="any").tail(lookback)


def pca(returns):
    """Principal components of the correlation matrix.

    Returns (eigenvalues, eigenvectors, share), largest first. ``share`` is
    the fraction of total variance each component explains.
    """
    corr = np.corrcoef(returns.to_numpy(), rowvar=False)
    values, vectors = np.linalg.eigh(corr)
    order = np.argsort(values)[::-1]
    values, vectors = values[order], vectors[:, order]
    return values, vectors, values / values.sum()


def find_themes(corr, threshold=0.60):
    """Group stocks into themes and return (theme labels, graph).

    Two stocks are linked when their correlation is at or above
    ``threshold``. The linked stocks form a graph. A theme is a community
    of that graph: a set of stocks with many links inside the set and few
    links to the outside (found by modularity maximisation). A stock with
    no link is ``solo``.

    Plain connected groups are not used, because one weak chain of links
    (A-B, B-C, C-D) would merge unrelated sectors into one large group.
    """
    graph = nx.Graph()
    graph.add_nodes_from(corr.index)
    for i, a in enumerate(corr.index):
        for b in corr.index[i + 1:]:
            if corr.loc[a, b] >= threshold:
                graph.add_edge(a, b, weight=float(corr.loc[a, b]))
    labels = pd.Series("solo", index=corr.index, dtype=object)
    linked = graph.subgraph([n for n in graph.nodes if graph.degree(n) > 0])
    if linked.number_of_nodes():
        groups = nx.community.greedy_modularity_communities(linked, weight="weight")
        groups = sorted(groups, key=lambda g: (-len(g), sorted(g)[0]))
        for number, members in enumerate(groups, start=1):
            for ticker in members:
                labels[ticker] = f"T{number}"
    return labels, graph


def run_scan(prices, min_price=5.0, min_dollar_vol_m=20.0, min_adr=4.0,
             min_mom_rank=90.0, theme_corr=0.60, corr_lookback=120):
    """Run the whole scan and return its results in one dictionary.

    Keys: ``regime`` (market gate), ``filters`` (every stock with its filter
    columns), ``counts`` (stocks left after each filter), ``themes`` (theme
    label of each high-ADR stock) and ``candidates`` (the scored survivors,
    best first, with their theme).
    """
    close = prices["Close"]
    metrics = compute_metrics(prices)
    flt = apply_filters(metrics, min_price, min_dollar_vol_m, min_adr, min_mom_rank)

    alive = pd.Series(True, index=flt.index)
    counts = {"Universe": int(alive.sum())}
    for label, column in [("Price", "f_price"), ("Liquidity", "f_liquid"),
                          ("ADR", "f_adr"), ("Leader", "f_leader"),
                          ("Trend", "f_trend")]:
        alive &= flt[column]
        counts[label] = int(alive.sum())

    group = flt[flt["f_price"] & flt["f_liquid"] & flt["f_adr"]].index
    corr = returns_matrix(close, group, corr_lookback).corr()
    themes, _ = find_themes(corr, theme_corr)

    cands = flt[flt["passed"]].copy()
    cands["score"] = setup_score(cands)
    cands["theme"] = themes.reindex(cands.index).fillna("solo")
    cands = cands.sort_values("score", ascending=False)
    key = np.where(cands["theme"] == "solo", cands.index, cands["theme"])
    cands["best_in_theme"] = ~pd.Series(key, index=cands.index).duplicated()

    return {"regime": market_regime(close, "QQQ"), "filters": flt,
            "counts": counts, "themes": themes, "candidates": cands,
            "as_of": close.index[-1].date()}
