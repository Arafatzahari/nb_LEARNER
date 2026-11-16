"""Bayesian estimate of a trading edge from a trade log.

Three pieces are estimated, each with its uncertainty:

* win rate          - Beta prior, updated by counting wins and losses
* average winner    - log of winner sizes modelled as Normal, with a
                      Normal-Inverse-Gamma prior (winners are lognormal,
                      the same shape the Monte Carlo engine uses)
* average loser     - a simple weighted average of the prior and the log

Draws from the three are combined into draws of expectancy in R.
The priors are centred on borrowed statistics (23% win rate, 8R winner).
They are a starting belief, and the trade log moves the estimate away
from them as evidence accumulates.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import beta as beta_dist


@dataclass
class Prior:
    """Starting belief, before any of your own trades."""
    win_rate: float = 0.23        # centre of the win-rate belief
    win_strength: float = 20.0    # worth this many imaginary trades
    avg_win_R: float = 8.0        # centre of the average-winner belief
    win_sigma: float = 0.9        # spread of winner sizes (lognormal shape)
    size_strength: float = 5.0    # worth this many imaginary winners
    avg_loss_R: float = 1.0       # centre of the average-loser belief
    loss_strength: float = 10.0   # worth this many imaginary losers


def load_trade_log(path):
    """Read a trade log CSV and return it with an ``R`` column.

    The file needs either a column ``R`` (result of each closed trade in R),
    or the two columns ``pnl`` and ``risk_dollars`` (R = pnl / risk_dollars).
    Rows keep the order of the file, which should be oldest trade first.
    """
    log = pd.read_csv(path)
    if "R" not in log.columns:
        if {"pnl", "risk_dollars"} <= set(log.columns):
            log["R"] = log["pnl"] / log["risk_dollars"]
        else:
            raise ValueError("Trade log needs a column 'R', or the columns "
                             "'pnl' and 'risk_dollars'.")
    log = log.dropna(subset=["R"]).reset_index(drop=True)
    return log


def make_sample_log(n_trades=40, seed=7):
    """Build a made-up trade log for practice. These are not real trades.

    The made-up trader has a 20% win rate and a 5R average winner, which is
    weaker than the borrowed 23% and 8R, so the update has something to show.
    """
    rng = np.random.default_rng(seed)
    is_win = rng.random(n_trades) < 0.20
    wins = rng.lognormal(np.log(5.0) - 0.5 * 0.8 ** 2, 0.8, n_trades)
    losses = -rng.choice([1.0, 1.0, 1.0, 0.5, 1.3], n_trades)
    dates = pd.bdate_range("2026-06-01", periods=n_trades, freq="2B")
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "ticker": [f"SAMPLE{i + 1:02d}" for i in range(n_trades)],
        "R": np.where(is_win, wins, losses).round(2),
    })


def win_rate_posterior(R, prior):
    """Beta(a, b) parameters of the win-rate belief after seeing ``R``."""
    R = np.asarray(R, dtype=float)
    wins = int(np.sum(R > 0))
    losses = int(np.sum(R <= 0))
    a = prior.win_rate * prior.win_strength + wins
    b = (1.0 - prior.win_rate) * prior.win_strength + losses
    return a, b


def grid_posterior(wins, losses, prior, points=501):
    """Win-rate belief by brute force on a grid, to show Bayes' rule at work.

    posterior = prior x likelihood, entry by entry, then scaled so the
    area under the curve is 1. Returns (grid, prior_curve, posterior_curve).
    """
    grid = np.linspace(0.001, 0.999, points)
    a0 = prior.win_rate * prior.win_strength
    b0 = (1.0 - prior.win_rate) * prior.win_strength
    prior_curve = beta_dist.pdf(grid, a0, b0)
    likelihood = grid ** wins * (1.0 - grid) ** losses
    unscaled = prior_curve * likelihood
    step = grid[1] - grid[0]
    return grid, prior_curve, unscaled / (unscaled.sum() * step)


def sample_avg_win(R, prior, draws, rng):
    """Draws of the true average winner, in R."""
    R = np.asarray(R, dtype=float)
    y = np.log(R[R > 0])
    n = len(y)
    k0 = prior.size_strength
    mu0 = np.log(prior.avg_win_R) - 0.5 * prior.win_sigma ** 2
    alpha0 = k0 / 2.0 + 1.0
    beta0 = (k0 / 2.0) * prior.win_sigma ** 2

    ybar = y.mean() if n else 0.0
    ss = np.sum((y - ybar) ** 2) if n else 0.0
    kn = k0 + n
    mun = (k0 * mu0 + n * ybar) / kn
    alphan = alpha0 + n / 2.0
    betan = beta0 + 0.5 * ss + k0 * n * (ybar - mu0) ** 2 / (2.0 * kn)

    sigma2 = betan / rng.gamma(alphan, 1.0, draws)
    mu = rng.normal(mun, np.sqrt(sigma2 / kn))
    return np.exp(mu + 0.5 * sigma2), np.sqrt(sigma2)


def avg_loss_estimate(R, prior):
    """Average loser in R (a positive number), prior and log blended."""
    R = np.asarray(R, dtype=float)
    losses = -R[R <= 0]
    total = prior.avg_loss_R * prior.loss_strength + losses.sum()
    return total / (prior.loss_strength + len(losses))


def sample_edge(R, prior, draws=20_000, seed=0):
    """Draws of win rate, average winner, winner spread and expectancy."""
    rng = np.random.default_rng(seed)
    a, b = win_rate_posterior(R, prior)
    win_rate = rng.beta(a, b, draws)
    avg_win, win_sigma = sample_avg_win(R, prior, draws, rng)
    avg_loss = avg_loss_estimate(R, prior)
    expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss
    return pd.DataFrame({"win_rate": win_rate, "avg_win_R": avg_win,
                         "win_sigma": win_sigma, "avg_loss_R": avg_loss,
                         "expectancy_R": expectancy})


def sizing_decision(p_positive, n_trades, upgrade_at=0.90, downgrade_at=0.60,
                    min_trades=30):
    """Turn the evidence into a risk setting. The thresholds are tunable."""
    if n_trades < min_trades:
        return "0.5R", (f"Only {n_trades} trades logged. Stay at half risk "
                        f"until {min_trades} trades.")
    if p_positive >= upgrade_at:
        return "1R", (f"P(edge > 0) = {p_positive:.0%}, at or above "
                      f"{upgrade_at:.0%}. Full risk is supported.")
    if p_positive < downgrade_at:
        return "pause", (f"P(edge > 0) = {p_positive:.0%}, below "
                         f"{downgrade_at:.0%}. Stop and review the method.")
    return "0.5R", (f"P(edge > 0) = {p_positive:.0%}, between "
                    f"{downgrade_at:.0%} and {upgrade_at:.0%}. Stay at half risk.")
