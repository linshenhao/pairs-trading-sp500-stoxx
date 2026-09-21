"""Small regression checks for the backtest engine."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parents[1]))

from pairs_trading import (
    MarketData,
    PairsBacktester,
    StrategyConfig,
    half_life,
    plot_equity_drawdown,
)


class BacktestChecks(unittest.TestCase):
    def test_equity_chart_has_three_panels(self):
        dates = pd.date_range("2020-01-03", periods=4, freq="W-FRI")
        returns = pd.DataFrame({
            "Strategy net": [0.0, 0.01, -0.005, 0.002],
            "Strategy gross": [0.0, 0.012, -0.004, 0.003],
            "Benchmark": [0.0, 0.02, -0.01, 0.01],
        }, index=dates)
        figure = plot_equity_drawdown(returns, "Test")
        self.assertEqual(len(figure.axes), 3)
        plt.close(figure)

    def test_extreme_spread_is_not_opened(self):
        dates = pd.date_range("2020-01-03", periods=5, freq="W-FRI")
        log_x = np.zeros(5)
        log_y = np.array([0.0, 0.40, 0.45, 0.50, 0.55])
        prices = pd.DataFrame({"Y": np.exp(log_y), "X": np.exp(log_x)}, index=dates)
        weights = pd.DataFrame({"Y": [1.0], "X": [1.0]}, index=[dates[0]])
        labels = pd.Series({"Y": "Sector", "X": "Sector"})
        data = MarketData(
            prices=prices,
            weights=weights,
            sectors=labels,
            names=labels,
            benchmark=pd.Series(100.0, index=dates),
            groups=pd.Series({"Y": "all", "X": "all"}),
        )
        pair = pd.Series({
            "y": "Y", "x": "X", "alpha": 0.0, "beta": 1.0,
            "mean": 0.0, "sigma": 0.1,
        })
        returns = PairsBacktester(data, StrategyConfig()).trade_pair(pair, 1, 5)
        self.assertTrue((returns == 0).all())

    def test_non_reverting_spread_has_infinite_half_life(self):
        self.assertEqual(half_life(np.arange(10.0)), np.inf)

    def test_seed_week_entry_cost_is_charged(self):
        dates = pd.date_range("2020-01-03", periods=5, freq="W-FRI")
        prices = pd.DataFrame({
            "Y": np.exp(np.full(5, -0.25)),
            "X": np.ones(5),
        }, index=dates)
        weights = pd.DataFrame({"Y": [1.0], "X": [1.0]}, index=[dates[0]])
        labels = pd.Series({"Y": "Sector", "X": "Sector"})
        data = MarketData(
            prices=prices,
            weights=weights,
            sectors=labels,
            names=labels,
            benchmark=pd.Series(100.0, index=dates),
            groups=pd.Series({"Y": "all", "X": "all"}),
        )
        pair = pd.Series({
            "y": "Y", "x": "X", "alpha": 0.0, "beta": 1.0,
            "mean": 0.0, "sigma": 0.1,
        })
        returns = PairsBacktester(data, StrategyConfig()).trade_pair(pair, 1, 5)
        self.assertAlmostEqual(returns.iloc[0], -StrategyConfig().fee)


if __name__ == "__main__":
    unittest.main()
