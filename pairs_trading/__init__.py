"""Public API for the pairs-trading project."""

from .backtest import (
    MarketData,
    PairsBacktester,
    StrategyConfig,
    benchmark_returns,
    half_life,
    load_market,
    performance_stats,
)
from .plots import (
    plot_diagnostics,
    plot_equity_drawdown,
    plot_parameter_sensitivity,
    plot_spread,
    set_plot_style,
)

__all__ = [
    "MarketData",
    "PairsBacktester",
    "StrategyConfig",
    "benchmark_returns",
    "half_life",
    "load_market",
    "performance_stats",
    "plot_diagnostics",
    "plot_equity_drawdown",
    "plot_parameter_sensitivity",
    "plot_spread",
    "set_plot_style",
]
