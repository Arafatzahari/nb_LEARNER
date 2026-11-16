"""Shared chart style for the trading lab notebooks.

One place for colours and matplotlib defaults, so every chart in the lab
looks the same. Import it and call ``use_lab_style()`` once per notebook.
"""
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SOFT = "#52514e"
GRID = "#e4e3df"

BLUE = "#2a78d6"      # main series
ORANGE = "#eb6834"    # second series / comparison
AQUA = "#1baf7a"      # third series
CRITICAL = "#d03b3b"  # rule limits and danger lines
BLUE_BAND_OUTER = "#cde2fb"   # 5-95 percentile band
BLUE_BAND_INNER = "#86b6ef"   # 25-75 percentile band


def use_lab_style():
    """Apply the lab's matplotlib defaults."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "figure.dpi": 110,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_SOFT,
        "axes.titlecolor": TEXT,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "xtick.color": TEXT_SOFT,
        "ytick.color": TEXT_SOFT,
        "text.color": TEXT,
        "lines.linewidth": 2.0,
        "legend.frameon": False,
        "font.size": 10,
    })
