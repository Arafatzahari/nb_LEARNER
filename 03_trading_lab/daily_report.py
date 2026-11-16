"""Daily report: run every phase of the lab in one pass.

Order of work:

1. prices            load the snapshot, or download fresh prices
2. scan              regime gate, filters, scores, themes      (Phase 4)
3. edge              belief about the edge from the trade log  (Phase 2)
4. risk              risk per trade the evidence supports      (Phase 3)
5. allocation        picks and whole-share sizes               (Phase 5)
6. outlook           simulated futures at the supported risk   (Phases 1, 3)
7. verdict           what the rules allow today

Run it from a notebook (``06_daily_report.ipynb``) or from a terminal:

    python daily_report.py
    python daily_report.py --refresh --equity 2000 --log my_trades.csv

The report is a study tool. It applies the lab's rules to the lab's
assumptions; it is not advice and not an instruction to trade.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import allocator as al
import bayes_edge as be
import mc_engine as mc
import scanner as sc

REPORT_DIR = Path(__file__).parent / "reports"


@dataclass
class Config:
    """Every input of the daily report."""
    equity: float = 2000.0
    trade_log: str = "sample_trade_log.csv"
    refresh: bool = False            # True = download fresh prices
    rule_risk_pct: float = 0.01      # your rule: 1R = 1% of equity
    stop_adr: float = 0.5            # stop distance, in ADR
    max_slots: int = 2
    gap_budget_pct: float = 0.03     # loss accepted if every pick gaps one ADR
    max_ext_adr: float = 1.0         # skip candidates more extended than this
    drawdown_limit: float = 0.30     # a drawdown you do not want to live through
    max_chance: float = 0.10         # largest accepted chance of that drawdown
    trades: int = 300                # horizon of the outlook, in trades
    paths: int = 10_000
    seed: int = 42


def supported_risk(edge, n_trades, cfg):
    """Risk per trade supported by the evidence, and the three limits.

    The smallest of: the drawdown limit (largest risk that keeps the chance
    of ``drawdown_limit`` within ``max_chance``), the evidence limit (the
    Phase 2 sizing rule) and the rule (``rule_risk_pct``).
    """
    R, _ = mc.simulate_R_uncertain(edge, cfg.paths, cfg.trades,
                                   np.random.default_rng(cfg.seed))
    grid = np.arange(0.001, cfg.rule_risk_pct * 2.5 + 1e-9, 0.001)
    chance = np.array([np.mean(mc.max_drawdown(
        mc.equity_paths(R, cfg.equity, rp)) >= cfg.drawdown_limit) for rp in grid])
    allowed = grid[chance <= cfg.max_chance]
    dd_risk = float(allowed.max()) if len(allowed) else 0.0

    p_positive = float(np.mean(edge["expectancy_R"] > 0))
    setting, reason = be.sizing_decision(p_positive, n_trades)
    evidence_risk = {"1R": 1.0, "0.5R": 0.5, "pause": 0.0}[setting] * cfg.rule_risk_pct

    return {"drawdown_limit_risk": dd_risk, "evidence_risk": evidence_risk,
            "rule_risk": cfg.rule_risk_pct,
            "supported": min(dd_risk, evidence_risk, cfg.rule_risk_pct),
            "p_positive": p_positive, "setting": setting, "reason": reason,
            "R": R}


def run(cfg=None):
    """Run the whole pipeline and return every result in one dictionary."""
    cfg = cfg or Config()

    prices = sc.load_prices(refresh=cfg.refresh)
    scan = sc.run_scan(prices)

    log = be.load_trade_log(cfg.trade_log)
    edge = be.sample_edge(log["R"].to_numpy(), be.Prior(), draws=20_000, seed=0)
    risk = supported_risk(edge, len(log), cfg)

    cands = scan["candidates"]
    eligible = cands[cands["ext_adr"] <= cfg.max_ext_adr]
    orders, objective = None, 0.0
    if risk["supported"] > 0 and len(eligible):
        orders, objective, _ = al.allocate(
            eligible, cfg.equity, risk["supported"], cfg.stop_adr, cfg.max_slots,
            cfg.gap_budget_pct / risk["supported"])

    equity = (mc.equity_paths(risk["R"], cfg.equity, risk["supported"])
              if risk["supported"] > 0 else None)
    outlook = None
    if equity is not None:
        final, dd = equity[:, -1], mc.max_drawdown(equity)
        outlook = {"p5": np.percentile(final, 5), "median": np.median(final),
                   "p95": np.percentile(final, 95),
                   "p_below_start": float(np.mean(final < cfg.equity)),
                   "dd_median": float(np.median(dd)),
                   "p_dd_limit": float(np.mean(dd >= cfg.drawdown_limit))}

    result = {"cfg": cfg, "as_of": scan["as_of"], "prices": prices, "scan": scan,
              "log": log, "edge": edge, "risk": risk, "eligible": eligible,
              "orders": orders, "objective": objective, "equity": equity,
              "outlook": outlook}
    result["verdict"] = verdict(result)
    return result


def verdict(r):
    """Plain-language conclusions, as a list of (status, text) pairs.

    Status is one of GO, CAUTION, STOP. The first STOP decides the day.
    """
    cfg, scan, risk = r["cfg"], r["scan"], r["risk"]
    lines = []
    if scan["regime"]["gate_open"]:
        lines.append(("GO", "Regime gate open: QQQ 10-day MA above 20-day MA, both rising."))
    else:
        lines.append(("STOP", "Regime gate closed. Your rule allows no new breakout entries."))

    if risk["setting"] == "pause":
        lines.append(("STOP", f"Edge unproven: P(edge > 0) = {risk['p_positive']:.0%}. "
                              "Pause and review the method."))
    elif risk["setting"] == "0.5R":
        lines.append(("CAUTION", f"P(edge > 0) = {risk['p_positive']:.0%} from "
                                 f"{len(r['log'])} trades. Evidence supports half risk."))
    else:
        lines.append(("GO", f"P(edge > 0) = {risk['p_positive']:.0%}. Full risk is supported."))

    if risk["supported"] <= 0:
        lines.append(("STOP", "No risk per trade passes the drawdown and evidence limits."))
    else:
        status = "GO" if risk["supported"] >= cfg.rule_risk_pct else "CAUTION"
        lines.append((status, f"Supported risk {risk['supported']:.1%} per trade "
                              f"(${cfg.equity * risk['supported']:,.0f}); "
                              f"your rule is {cfg.rule_risk_pct:.1%}."))

    n = len(r["eligible"])
    if n == 0:
        lines.append(("STOP", "No candidate passes the scan and the extension filter."))
    elif r["orders"] is None or len(r["orders"]) == 0:
        lines.append(("CAUTION", f"{n} candidates, but none can be sized in whole shares "
                                 "at the supported risk."))
    else:
        picks = ", ".join(f"{t} x{int(s)}" for t, s in r["orders"]["shares"].items())
        if scan["regime"]["gate_open"]:
            lines.append(("GO", f"Allocation: {picks}."))
        else:
            lines.append(("CAUTION", f"Allocation, as an exercise only: {picks}."))
    return lines


def overall(lines):
    """One word for the day: STOP if any line says STOP, else CAUTION or GO."""
    states = [s for s, _ in lines]
    return "STOP" if "STOP" in states else "CAUTION" if "CAUTION" in states else "GO"


def to_markdown(r):
    """The report as Markdown text."""
    cfg, scan, risk = r["cfg"], r["scan"], r["risk"]
    reg, out = scan["regime"], []
    add = out.append
    add(f"# Daily report — prices to {r['as_of']}")
    add("")
    add(f"Account ${cfg.equity:,.0f} · trade log `{cfg.trade_log}` "
        f"({len(r['log'])} trades) · study tool, not advice.")
    add("")
    add(f"## Verdict: {overall(r['verdict'])}")
    add("")
    for status, text in r["verdict"]:
        add(f"- **{status}** — {text}")
    add("")
    add("## 1. Market regime")
    add("")
    add(f"QQQ close {reg['close']:.2f}, 10-day MA {reg['ma10']:.2f}, "
        f"20-day MA {reg['ma20']:.2f}. Gate "
        f"{'open' if reg['gate_open'] else 'closed'}.")
    add("")
    add("## 2. Scan")
    add("")
    add(" → ".join(f"{k} {v}" for k, v in scan["counts"].items()))
    add("")
    cols = ["price", "adr_pct", "mom_rank", "ext_adr", "tightness", "score", "theme"]
    add(scan["candidates"][cols].round(2).to_markdown())
    add("")
    add("## 3. Edge (from the trade log)")
    add("")
    q = r["edge"][["win_rate", "avg_win_R", "expectancy_R"]].quantile([0.05, 0.5, 0.95]).T
    q.columns = ["5%", "median", "95%"]
    add(q.round(2).to_markdown())
    add("")
    add(risk["reason"])
    add("")
    add("## 4. Risk per trade")
    add("")
    add("| Limit | Risk per trade |")
    add("|---|---|")
    add(f"| Drawdown limit (P(drawdown ≥ {cfg.drawdown_limit:.0%}) ≤ {cfg.max_chance:.0%}) "
        f"| {risk['drawdown_limit_risk']:.1%} |")
    add(f"| Evidence limit | {risk['evidence_risk']:.1%} |")
    add(f"| Your rule | {risk['rule_risk']:.1%} |")
    add(f"| **Supported (smallest)** | **{risk['supported']:.1%}** |")
    add("")
    add("## 5. Allocation")
    add("")
    if r["orders"] is not None and len(r["orders"]):
        one_R = cfg.equity * risk["supported"]
        t = r["orders"][["price", "stop_price", "shares", "cost", "risk_R",
                         "score", "theme"]].copy()
        t["risk $"] = t["risk_R"] * one_R
        add(t.round(2).to_markdown())
        add("")
        add(f"Total cost ${t['cost'].sum():,.2f} "
            f"({t['cost'].sum() / cfg.equity:.0%} of the account), "
            f"total risk ${t['risk $'].sum():,.2f}.")
        if not reg["gate_open"]:
            add("")
            add("The regime gate is closed, so this allocation is an exercise.")
    else:
        add("No allocation.")
    add("")
    add(f"## 6. Outlook over {cfg.trades} trades at the supported risk")
    add("")
    o = r["outlook"]
    if o:
        add(f"- Final account: 5th percentile ${o['p5']:,.0f}, median "
            f"${o['median']:,.0f}, 95th percentile ${o['p95']:,.0f}")
        add(f"- Chance of ending below the start: {o['p_below_start']:.0%}")
        add(f"- Median worst drawdown: {o['dd_median']:.0%}; chance of "
            f"{cfg.drawdown_limit:.0%} or more: {o['p_dd_limit']:.0%}")
    else:
        add("No outlook: supported risk is zero.")
    add("")
    add("## Limits of this report")
    add("")
    add("- The setup score is untested as a predictor of returns.")
    add("- The prior on the edge is borrowed from other traders' statistics.")
    add("- Prices are daily closes; entry and stop rules need intraday data.")
    add("- No costs, slippage, earnings dates or news. See `MANUAL.md`, section 6.")
    return "\n".join(out) + "\n"


def save(r, figure=None):
    """Write the Markdown report (and the dashboard image) to ``reports/``."""
    REPORT_DIR.mkdir(exist_ok=True)
    stem = REPORT_DIR / f"daily_report_{r['as_of']}"
    paths = [stem.with_suffix(".md")]
    paths[0].write_text(to_markdown(r), encoding="utf-8")
    if figure is not None:
        paths.append(stem.with_suffix(".png"))
        figure.savefig(paths[1], dpi=130, bbox_inches="tight")
    return paths


def main():
    parser = argparse.ArgumentParser(description="Run the trading lab's daily report.")
    parser.add_argument("--refresh", action="store_true", help="download fresh prices")
    parser.add_argument("--equity", type=float, default=Config.equity)
    parser.add_argument("--log", default=Config.trade_log, help="trade log CSV")
    args = parser.parse_args()
    result = run(Config(equity=args.equity, trade_log=args.log, refresh=args.refresh))
    for path in save(result):
        print(f"Saved {path}")
    print()
    print(f"VERDICT: {overall(result['verdict'])}")
    for status, text in result["verdict"]:
        print(f"  {status:8s} {text}")


if __name__ == "__main__":
    main()
