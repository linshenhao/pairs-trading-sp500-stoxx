"""Run the robust pairs strategy and save reproducible project results."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .backtest import (
    PairsBacktester,
    StrategyConfig,
    benchmark_returns,
    load_market,
    performance_stats,
)
from .plots import plot_equity_drawdown

ROOT = Path(__file__).resolve().parents[1]


def save_equity_figure(returns: pd.DataFrame, market: str, method: str,
                       path: Path) -> None:
    """Save the shared equity and drawdown chart."""
    returns = returns.rename(columns={
        "strategy_net": "Strategy net",
        "strategy_gross": "Strategy gross",
        "benchmark": "Benchmark",
    })
    fig = plot_equity_drawdown(
        returns, f"{market.upper()} {method.title()} out-of-sample performance"
    )
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_market_results(market: str, method: str, output: Path) -> pd.DataFrame:
    """Run one market and save its metrics, returns, selections, and chart."""
    data = load_market(ROOT / "data" / "cache", market)
    config = StrategyConfig(
        selection_method=method,
        min_price=5.0 if market == "spx" else 1.0,
    )
    backtester = PairsBacktester(data, config)
    net, selections = backtester.run(progress=True)
    gross = PairsBacktester(data, replace(config, fee=0.0)).trade_selections(selections)
    benchmark = benchmark_returns(data, net.index)

    market_output = output / f"{market}_{method}"
    market_output.mkdir(parents=True, exist_ok=True)
    weekly_returns = pd.DataFrame({"strategy_net": net, "strategy_gross": gross,
                                   "benchmark": benchmark})
    weekly_returns.to_csv(market_output / "weekly_returns.csv")

    selected = []
    for start, pairs in selections.items():
        if pairs.empty:
            continue
        frame = pairs.copy()
        frame.insert(0, "trading_start", data.prices.index[start])
        selected.append(frame)
    if selected:
        pd.concat(selected, ignore_index=True).to_csv(
            market_output / "selected_pairs.csv", index=False
        )

    metrics = pd.DataFrame({
        "Strategy net": performance_stats(net, benchmark),
        "Strategy gross": performance_stats(gross, benchmark),
        "Benchmark": performance_stats(benchmark),
    })
    metrics.to_csv(market_output / "metrics.csv")

    save_equity_figure(weekly_returns, market, method,
                       market_output / "equity_curve.png")

    counts = pd.Series({data.prices.index[start]: len(pairs)
                        for start, pairs in selections.items()})
    print(f"{market.upper()} {method}: {net.index[0].date()} to {net.index[-1].date()}, "
          f"average {counts.mean():.1f} pairs per window")
    print(metrics.round(4))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["spx", "stoxx", "all"], default="all")
    parser.add_argument(
        "--method", choices=["cointegration", "distance", "both"], default="both"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    markets = ["spx", "stoxx"] if args.market == "all" else [args.market]
    methods = ["cointegration", "distance"] if args.method == "both" else [args.method]
    summaries = []
    for market in markets:
        for method in methods:
            metrics = save_market_results(market, method, args.output)
            summary = metrics.loc[["CAGR", "Annual volatility", "Sharpe (rf=0)",
                                   "Max drawdown"]].T
            summary.insert(0, "market", market.upper())
            summary.insert(1, "method", method)
            summary.insert(2, "series", summary.index)
            summaries.append(summary.reset_index(drop=True))
    args.output.mkdir(parents=True, exist_ok=True)
    pd.concat(summaries, ignore_index=True).to_csv(args.output / "summary.csv", index=False)


if __name__ == "__main__":
    main()
