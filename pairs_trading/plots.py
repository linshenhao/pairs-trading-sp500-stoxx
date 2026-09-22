"""Small, consistent plotting helpers for the project notebooks."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.ticker import PercentFormatter

COLORS = {
    "Strategy net": "#0F766E",
    "Strategy gross": "#5AA89D",
    "Benchmark": "#334155",
    "positive": "#2A9D8F",
    "negative": "#E76F51",
    "accent": "#D97706",
}


def set_plot_style() -> None:
    """Apply the shared GitHub-friendly chart style."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#CBD5E1",
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "axes.labelcolor": "#334155",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.alpha": 0.22,
        "legend.frameon": False,
        "font.size": 10,
    })


def plot_equity_drawdown(returns: pd.DataFrame, title: str):
    """Plot market comparison plus readable strategy detail."""
    set_plot_style()
    equity = (1 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1
    colors = [COLORS.get(column, "#64748B") for column in equity]
    strategy_columns = [name for name in ["Strategy net", "Strategy gross"]
                        if name in equity]

    fig = plt.figure(figsize=(12, 8))
    grid = fig.add_gridspec(2, 2, height_ratios=[2.2, 1])
    overview = fig.add_subplot(grid[0, :])
    strategy = fig.add_subplot(grid[1, 0])
    risk = fig.add_subplot(grid[1, 1])

    equity.plot(ax=overview, color=colors, lw=1.8, logy=True)
    overview.set(title=title, ylabel="Growth of 1 (log scale)", xlabel="")
    overview.legend(ncol=3, loc="upper left")

    equity[strategy_columns].plot(
        ax=strategy,
        color=[COLORS[name] for name in strategy_columns],
        lw=1.7,
    )
    strategy.set(title="Strategy wealth", ylabel="Growth of 1", xlabel="")
    strategy.legend(ncol=2, loc="upper left")

    drawdown[strategy_columns].plot(
        ax=risk,
        color=[COLORS[name] for name in strategy_columns],
        lw=1.5,
    )
    risk.axhline(0, color="#94A3B8", lw=0.8)
    risk.set(title="Strategy drawdown", ylabel="Drawdown", xlabel="")
    risk.yaxis.set_major_formatter(PercentFormatter(1))
    risk.legend(ncol=2, loc="lower left")
    fig.tight_layout()
    return fig


def plot_spread(z_score: pd.Series, trading_start: pd.Timestamp, config,
                title: str):
    """Show one frozen spread with entry, exit, and stop thresholds."""
    set_plot_style()
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(z_score.index, z_score, color=COLORS["Strategy net"], lw=1.8)
    ax.axvspan(trading_start, z_score.index[-1], color="#E2E8F0", alpha=0.45,
               label="Trading window")
    ax.axvline(trading_start, color="#334155", ls="--", lw=1.1)
    ax.axhspan(-config.exit_z, config.exit_z, color=COLORS["positive"],
               alpha=0.10, label="Exit zone")
    for level, color, label in [
        (config.entry_z, COLORS["accent"], "Entry"),
        (config.stop_z, COLORS["negative"], "Stop"),
    ]:
        ax.axhline(level, color=color, ls="--", lw=1.1, label=label)
        ax.axhline(-level, color=color, ls="--", lw=1.1)
    ax.set(title=title, ylabel="Spread z-score", xlabel="")
    ax.legend(ncol=4, loc="upper left")
    fig.tight_layout()
    return fig


def plot_diagnostics(net: pd.Series, benchmark: pd.Series, counts: pd.Series,
                     title: str):
    """Plot annual returns, rolling Sharpe, and selected-pair counts."""
    set_plot_style()
    returns = pd.DataFrame({"Strategy net": net, "Benchmark": benchmark})
    annual = (1 + returns).groupby(returns.index.year).prod() - 1
    rolling_sharpe = np.sqrt(52) * net.rolling(52, min_periods=26).mean()
    rolling_sharpe /= net.rolling(52, min_periods=26).std()

    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    bar_colors = np.where(annual["Strategy net"] >= 0,
                          COLORS["positive"], COLORS["negative"])
    axes[0].bar(annual.index.astype(str), annual["Strategy net"],
                color=bar_colors, width=0.75)
    axes[0].axhline(0, color="#94A3B8", lw=0.8)
    axes[0].set(title=f"{title}: calendar-year net returns", ylabel="Return")
    axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].tick_params(axis="x", rotation=45)

    axes[1].plot(rolling_sharpe.index, rolling_sharpe,
                 color="#7C3AED", lw=1.5)
    axes[1].axhline(0, color="#94A3B8", lw=0.8)
    axes[1].set(title="Rolling 52-week Sharpe", ylabel="Sharpe")

    axes[2].step(counts.index, counts, where="post",
                 color=COLORS["Strategy net"], lw=1.7)
    axes[2].fill_between(counts.index, counts, step="post",
                         color=COLORS["Strategy net"], alpha=0.12)
    axes[2].set(title="Pairs selected per six-month window",
                ylabel="Pairs", xlabel="")
    fig.tight_layout()
    return fig, annual, rolling_sharpe


def plot_parameter_sensitivity(sharpe_grid: pd.DataFrame,
                               fee_table: pd.DataFrame, title: str):
    """Plot entry-exit Sharpe stability and transaction-cost sensitivity."""
    set_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.5), layout="constrained")

    values = sharpe_grid.to_numpy(dtype=float)
    limit = max(np.nanmax(np.abs(values)), 0.01)
    axes[0].imshow(
        values,
        cmap="RdYlGn",
        norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
        aspect="auto",
    )
    axes[0].set(
        title="Net Sharpe: entry vs exit",
        xlabel="Exit z-score",
        ylabel="Entry z-score",
        xticks=range(len(sharpe_grid.columns)),
        yticks=range(len(sharpe_grid.index)),
        xticklabels=sharpe_grid.columns,
        yticklabels=sharpe_grid.index,
    )
    for row, entry in enumerate(sharpe_grid.index):
        for column, exit_ in enumerate(sharpe_grid.columns):
            value = sharpe_grid.loc[entry, exit_]
            axes[0].text(column, row, f"{value:.2f}", ha="center", va="center",
                         color="white" if abs(value) > limit * 0.55 else "#0F172A",
                         fontweight="bold")
    axes[1].plot(fee_table.index, fee_table["Sharpe (rf=0)"], "o-",
                 color=COLORS["Strategy net"], lw=1.8)
    axes[1].axhline(0, color="#94A3B8", lw=0.8)
    axes[1].set(
        title="Impact of transaction costs",
        xlabel="Cost per unit turnover (bps)",
        ylabel="Sharpe (net)",
        xticks=fee_table.index,
    )
    fig.suptitle(title, fontsize=15, fontweight="bold")
    return fig
