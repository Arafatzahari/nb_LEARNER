"""Monte Carlo engine for an R-multiple trading system.

Everything here is matrix maths on NumPy arrays:

* a matrix of trade results in R, shape (paths, trades)
* a cumulative product along the trade axis turns it into equity paths
* a Cholesky factor turns independent random numbers into correlated ones,
  which is how two slots that move together are simulated

The numbers in ``Rules`` are assumptions, not measurements. Replace them with
your own trade-log statistics when you have them (Phase 2).
"""
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm


@dataclass
class Rules:
    """The trading system, as numbers."""
    start_equity: float = 2000.0
    risk_pct: float = 0.01        # 1R as a fraction of current equity
    win_rate: float = 0.23        # probability that a trade is a winner
    avg_win_R: float = 8.0        # mean winner, in R, after trim and trail
    win_sigma: float = 0.9        # spread of winner sizes (lognormal shape)
    gap_prob: float = 0.0         # share of losers that gap past the stop
    gap_R: float = 2.5            # loss, in R, when a loser gaps
    capped_prob: float = 0.0      # share of trades cut down by the cash cap
    capped_frac: float = 0.5      # size of a capped trade, as a share of 1R

    @property
    def expectancy_R(self):
        """Mean result of one trade, in R."""
        avg_loss = 1.0 + self.gap_prob * (self.gap_R - 1.0)
        size = 1.0 - self.capped_prob * (1.0 - self.capped_frac)
        return size * (self.win_rate * self.avg_win_R
                       - (1.0 - self.win_rate) * avg_loss)


def simulate_R(rules, paths, trades, rng, win_uniform=None):
    """Return a (paths, trades) matrix of trade results in R.

    ``win_uniform`` is an optional matrix of uniform(0, 1) numbers that
    decides win or loss. Pass correlated uniforms to make slots move together.
    """
    shape = (paths, trades)
    if win_uniform is None:
        win_uniform = rng.random(shape)
    is_win = win_uniform < rules.win_rate

    # Winner size: lognormal with mean avg_win_R. Most winners are modest,
    # a few are very large, which is what a trend-following method produces.
    mu = np.log(rules.avg_win_R) - 0.5 * rules.win_sigma ** 2
    win_R = rng.lognormal(mu, rules.win_sigma, shape)

    # Loser size: -1R at the stop, or -gap_R when price opens past the stop.
    is_gap = rng.random(shape) < rules.gap_prob
    loss_R = np.where(is_gap, -rules.gap_R, -1.0)

    R = np.where(is_win, win_R, loss_R)

    # Cash cap: a tight stop asks for more shares than the slot's cash can
    # buy, so the trade is smaller than 1R, on wins and losses alike.
    is_capped = rng.random(shape) < rules.capped_prob
    return np.where(is_capped, R * rules.capped_frac, R)


def equity_paths(R, start_equity, risk_pct):
    """Compound a matrix of R results into equity paths.

    Each trade multiplies equity by (1 + R * risk_pct). The result has one
    more column than ``R``: column 0 is the starting equity.
    """
    growth = np.cumprod(1.0 + R * risk_pct, axis=1)
    start = np.ones((R.shape[0], 1))
    return start_equity * np.hstack([start, growth])


def max_drawdown(equity):
    """Largest peak-to-trough fall of each path, as a fraction (0.30 = 30%)."""
    peak = np.maximum.accumulate(equity, axis=1)
    return (1.0 - equity / peak).max(axis=1)


def longest_losing_streak(R):
    """Longest run of consecutive losing trades in each path."""
    current = np.zeros(R.shape[0], dtype=int)
    longest = np.zeros(R.shape[0], dtype=int)
    for t in range(R.shape[1]):
        current = np.where(R[:, t] < 0, current + 1, 0)
        longest = np.maximum(longest, current)
    return longest


def correlated_uniforms(rho, paths, rounds, rng):
    """Two streams of uniform(0, 1) numbers with correlation ``rho``.

    Returns an array of shape (paths, rounds, 2). The Cholesky factor L of
    the 2x2 correlation matrix mixes independent normals into correlated
    normals; the normal CDF then maps them to uniforms.
    """
    corr = np.array([[1.0, rho], [rho, 1.0]])
    # A tiny diagonal bump keeps the factorisation valid at rho = 1.
    L = np.linalg.cholesky(corr + 1e-12 * np.eye(2))
    z = rng.standard_normal((paths, rounds, 2))
    return norm.cdf(z @ L.T)


def simulate_two_slots(rules, rho, paths, rounds, rng):
    """Equity paths when two slots are open together in every round.

    Each slot risks ``rules.risk_pct``. Returns (equity, R_total) where
    R_total is the combined result of both slots in each round.
    """
    u = correlated_uniforms(rho, paths, rounds, rng)
    R_a = simulate_R(rules, paths, rounds, rng, win_uniform=u[:, :, 0])
    R_b = simulate_R(rules, paths, rounds, rng, win_uniform=u[:, :, 1])
    R_total = R_a + R_b
    return equity_paths(R_total, rules.start_equity, rules.risk_pct), R_total


def summarize(equity, R):
    """Headline statistics of a simulation, as a dictionary."""
    final = equity[:, -1]
    dd = max_drawdown(equity)
    start = equity[0, 0]
    return {
        "Final equity, 5th pct ($)": np.percentile(final, 5),
        "Final equity, median ($)": np.median(final),
        "Final equity, 95th pct ($)": np.percentile(final, 95),
        "P(end below start) %": 100 * np.mean(final < start),
        "Max drawdown, median %": 100 * np.median(dd),
        "Max drawdown, 95th pct %": 100 * np.percentile(dd, 95),
        "P(drawdown >= 30%) %": 100 * np.mean(dd >= 0.30),
        "P(drawdown >= 50%) %": 100 * np.mean(dd >= 0.50),
        "Losing streak, median": np.median(longest_losing_streak(R)),
    }


def simulate_R_uncertain(edge, paths, trades, rng):
    """Trade results in R when the edge itself is uncertain.

    ``edge`` is the table of posterior draws from ``bayes_edge.sample_edge``
    (columns win_rate, avg_win_R, win_sigma, avg_loss_R). Each simulated
    future picks one row, so each future has its own plausible edge and keeps
    it for all of its trades.

    The per-future numbers are column vectors of shape (paths, 1). NumPy
    stretches them across the (paths, trades) matrix; this is broadcasting.

    Returns (R, row_index), where row_index says which draw each future used.
    """
    shape = (paths, trades)
    row = rng.integers(0, len(edge), paths)
    win_rate = edge["win_rate"].to_numpy()[row][:, None]
    avg_win = edge["avg_win_R"].to_numpy()[row][:, None]
    sigma = edge["win_sigma"].to_numpy()[row][:, None]
    avg_loss = edge["avg_loss_R"].to_numpy()[row][:, None]

    is_win = rng.random(shape) < win_rate
    mu = np.log(avg_win) - 0.5 * sigma ** 2
    win_R = np.exp(mu + sigma * rng.standard_normal(shape))
    return np.where(is_win, win_R, -avg_loss), row
