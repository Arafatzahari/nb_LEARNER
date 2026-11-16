"""Two-slot allocator: choose positions with a mixed-integer linear program.

Decision variables, for each candidate stock i:

* s_i  number of shares to buy (a whole number, 0 or more)
* x_i  1 if the stock is picked, 0 if not

The risk taken in stock i, in R, is  y_i = r_i * s_i,  where r_i is the
risk of one share in R (price x stop distance / 1R).

Objective: maximise  sum of value_i * y_i

Constraints, all linear (A @ variables <= b):

* slots   at most ``max_slots`` picks
* cash    total position cost within the account (no leverage)
* gap     total loss if every pick opens one ADR lower, within a budget
* theme   at most one pick per theme
* link    y_i <= u_i * x_i, where u_i is the largest risk the slot may
          carry: 1R, or less when the slot's cash runs out first

The structure is the same as a refinery planning LP: activities to choose,
a value per unit of each, and limited resources they compete for.

``value`` is the setup score divided by 100. The score has not been tested
as a predictor of returns, so the result ranks candidates by the scanner's
taste, under the rules; it is not an expected-profit maximiser.
"""
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, linprog, milp


def prepare(cands, equity, risk_pct, stop_adr, max_slots=2):
    """Add the per-stock numbers the program needs.

    stop_pct      stop distance as a fraction of price (stop_adr x ADR)
    share_R       risk of one share, in R (price x stop_pct / 1R)
    cost_per_R    dollars of stock bought for 1R of risk (1R / stop_pct)
    gap_R         loss in R, per 1R of risk, if the stock opens one ADR lower
    max_R         largest risk the slot may carry: 1R or the slot's cash cap
    value         setup score / 100
    """
    c = cands.copy()
    one_R = equity * risk_pct
    slot_cash = equity / max_slots
    c["stop_pct"] = stop_adr * c["adr_pct"] / 100.0
    c["share_R"] = c["price"] * c["stop_pct"] / one_R
    c["cost_per_R"] = one_R / c["stop_pct"]
    c["gap_R"] = 1.0 / stop_adr
    c["max_R"] = np.minimum(1.0, slot_cash / c["cost_per_R"])
    c["value"] = c["score"] / 100.0
    return c


def build_problem(c, equity, max_slots=2, gap_budget_R=3.0, use_themes=True):
    """Build the objective vector, constraint matrix and limits.

    Variables are ordered [s_1 .. s_n, x_1 .. x_n].
    Returns a dictionary with ``c`` (objective, to maximise), ``A``, ``b``,
    ``rows`` (a name for each constraint) and ``tickers``.
    """
    n = len(c)
    tickers = list(c.index)
    share_R = c["share_R"].to_numpy()
    objective = np.concatenate([c["value"].to_numpy() * share_R, np.zeros(n)])

    rows, A, b = [], [], []

    def add(name, s_part, x_part, limit):
        rows.append(name)
        A.append(np.concatenate([s_part, x_part]))
        b.append(limit)

    zeros = np.zeros(n)
    add("slots", zeros, np.ones(n), max_slots)
    add("cash", c["price"].to_numpy(), zeros, equity)
    add("gap", c["gap_R"].to_numpy() * share_R, zeros, gap_budget_R)
    if use_themes:
        for theme, members in c.groupby("theme").groups.items():
            if theme != "solo" and len(members) > 1:
                add(f"theme {theme}", zeros,
                    np.isin(tickers, list(members)).astype(float), 1.0)
    for i, ticker in enumerate(tickers):
        s_part, x_part = zeros.copy(), zeros.copy()
        s_part[i], x_part[i] = share_R[i], -c["max_R"].iloc[i]
        add(f"link {ticker}", s_part, x_part, 0.0)

    return {"c": objective, "A": np.array(A), "b": np.array(b),
            "rows": rows, "tickers": tickers, "n": n}


def solve(problem):
    """Solve the program. Returns (shares, objective value)."""
    n = problem["n"]
    upper = np.concatenate([np.full(n, np.inf), np.ones(n)])
    result = milp(c=-problem["c"],
                  constraints=LinearConstraint(problem["A"], -np.inf, problem["b"]),
                  integrality=np.ones(2 * n),
                  bounds=Bounds(np.zeros(2 * n), upper))
    if not result.success:
        raise RuntimeError(f"Solver failed: {result.message}")
    shares = np.round(result.x[:n]).astype(int)
    return pd.Series(shares, index=problem["tickers"]), float(-result.fun)


def allocate(cands, equity, risk_pct, stop_adr, max_slots=2, gap_budget_R=3.0,
             use_themes=True):
    """Prepare, build, solve and return (orders table, objective, prepared)."""
    c = prepare(cands, equity, risk_pct, stop_adr, max_slots)
    problem = build_problem(c, equity, max_slots, gap_budget_R, use_themes)
    shares, value = solve(problem)
    return to_orders(c, shares), value, c


def to_orders(c, shares):
    """Order table for the picked stocks."""
    picked = c[shares > 0].copy()
    picked["shares"] = shares[shares > 0]
    picked["stop_price"] = picked["price"] * (1.0 - picked["stop_pct"])
    picked["cost"] = picked["shares"] * picked["price"]
    picked["risk_R"] = picked["shares"] * picked["share_R"]
    picked["gap_loss_R"] = picked["risk_R"] * picked["gap_R"]
    return picked[["price", "stop_price", "stop_pct", "shares", "cost",
                   "risk_R", "max_R", "gap_loss_R", "score", "theme"]]


def shadow_prices(c, picks, equity, gap_budget_R=3.0):
    """Shadow price of each limit, with the picks fixed and shares divisible.

    With the picks fixed and fractional shares allowed, the problem is a
    plain linear program in the risks y. The shadow price of a limit is how
    much the objective would rise if that limit were relaxed by one unit.
    A limit with slack has a shadow price of zero.
    """
    chosen = c.loc[picks]
    k = len(chosen)
    A = np.vstack([chosen["cost_per_R"].to_numpy(),
                   chosen["gap_R"].to_numpy(),
                   np.eye(k)])
    b = np.concatenate([[equity, gap_budget_R], chosen["max_R"].to_numpy()])
    names = ["cash", "gap budget"] + [f"risk cap of {t}" for t in picks]
    units = ["per $1"] + ["per 1R"] * (k + 1)
    res = linprog(-chosen["value"].to_numpy(), A_ub=A, b_ub=b,
                  bounds=[(0, None)] * k, method="highs")
    return pd.DataFrame({"limit": b, "used": A @ res.x,
                         "shadow price": -res.ineqlin.marginals,
                         "unit": units}, index=names), res.x
