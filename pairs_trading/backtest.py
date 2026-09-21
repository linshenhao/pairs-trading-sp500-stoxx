"""Reusable walk-forward pairs-trading backtest for the project datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import coint

ANN = 52


@dataclass(frozen=True)
class StrategyConfig:
    selection_method: str = "cointegration"
    formation_weeks: int = 156
    validation_weeks: int = 52
    trading_weeks: int = 26
    n_pairs: int = 20
    fdr_alpha: float = 0.10
    min_return_corr: float = 0.40
    entry_z: float = 2.0
    exit_z: float = 0.5
    stop_z: float = 3.5
    max_holding_weeks: int = 12
    fee: float = 0.001
    min_price: float = 5.0
    max_weekly_return: float = 0.50
    beta_min: float = 0.1
    beta_max: float = 10.0
    half_life_min: float = 1.0
    half_life_max: float = 26.0
    max_validation_mean_z: float = 1.5
    max_validation_std_ratio: float = 2.0
    max_validation_z: float = 5.0
    min_validation_crossings: int = 1


@dataclass
class MarketData:
    prices: pd.DataFrame
    weights: pd.DataFrame
    sectors: pd.Series
    names: pd.Series
    benchmark: pd.Series
    groups: pd.Series

    @property
    def log_prices(self) -> pd.DataFrame:
        return np.log(self.prices)


def load_market(cache: str | Path, prefix: str) -> MarketData:
    """Load one extracted market from the shared cache directory."""
    cache = Path(cache)
    prices = pd.read_parquet(cache / f"{prefix}_prices_weekly.parquet")
    weights = pd.read_parquet(cache / f"{prefix}_weights_monthly.parquet")
    sectors = pd.read_csv(cache / f"{prefix}_sectors.csv", index_col=0)["sector"]
    names = pd.read_csv(cache / f"{prefix}_names.csv", index_col=0)["name"]
    benchmark = pd.read_parquet(cache / f"{prefix}_index_weekly.parquet").iloc[:, 0]
    groups_path = cache / f"{prefix}_groups.csv"
    if groups_path.exists():
        groups = pd.read_csv(groups_path, index_col=0)["group"]
    else:
        groups = pd.Series("all", index=prices.columns, name="group")
    return MarketData(prices, weights, sectors, names, benchmark, groups)


def half_life(spread: np.ndarray | pd.Series) -> float:
    """Estimate spread half-life in weeks with a simple AR(1) regression."""
    values = np.asarray(spread, dtype=float)
    delta = np.diff(values)
    lag = values[:-1] - values[:-1].mean()
    denominator = np.dot(lag, lag)
    if denominator == 0:
        return np.inf
    phi = np.dot(lag, delta) / denominator
    return np.log(2) / -phi if phi < 0 else np.inf


def performance_stats(returns: pd.Series, benchmark: pd.Series | None = None) -> pd.Series:
    """Return standard annualized performance and risk statistics."""
    returns = returns.dropna()
    equity = (1 + returns).cumprod()
    years = len(returns) / ANN
    drawdown = equity / equity.cummax() - 1
    downside = returns[returns < 0].std()
    volatility = returns.std()
    stats = {
        "Total return": equity.iloc[-1] - 1,
        "CAGR": equity.iloc[-1] ** (1 / years) - 1,
        "Annual volatility": np.sqrt(ANN) * volatility,
        "Sharpe (rf=0)": np.sqrt(ANN) * returns.mean() / volatility,
        "Sortino": np.sqrt(ANN) * returns.mean() / downside if downside > 0 else np.nan,
        "Max drawdown": drawdown.min(),
        "Positive weeks": (returns > 0).mean(),
        "Worst week": returns.min(),
    }
    if benchmark is not None:
        aligned = benchmark.reindex(returns.index)
        stats["Market correlation"] = returns.corr(aligned)
        stats["Market beta"] = returns.cov(aligned) / aligned.var()
    return pd.Series(stats)


class PairsBacktester:
    """Select stable pairs and trade them in non-overlapping future windows."""

    def __init__(self, data: MarketData, config: StrategyConfig):
        self.data = data
        self.config = config
        self.dates = data.prices.index
        self.log_prices = data.log_prices

    def members_at(self, date: pd.Timestamp) -> pd.Index:
        snapshots = self.data.weights.index[self.data.weights.index <= date]
        if len(snapshots) == 0:
            return pd.Index([])
        weights = self.data.weights.loc[snapshots[-1]].fillna(0)
        return weights.index[weights > 0]

    def eligible(self, start: int, end: int) -> pd.Index:
        """Return tradable constituents with clean formation data."""
        prices = self.data.prices.iloc[start:end]
        ok = prices.notna().all()
        ok &= prices.min() >= self.config.min_price
        ok &= prices.pct_change(fill_method=None).abs().max() <= self.config.max_weekly_return
        ok &= ok.index.isin(self.members_at(self.dates[end - 1]))
        ok &= ok.index.isin(self.data.sectors.dropna().index)
        ok &= ok.index.isin(self.data.groups.dropna().index)
        return ok.index[ok]

    @staticmethod
    def _fit(y: np.ndarray, x: np.ndarray) -> tuple[float, float, np.ndarray]:
        design = np.column_stack((np.ones(len(x)), x))
        alpha, beta = np.linalg.lstsq(design, y, rcond=None)[0]
        return float(alpha), float(beta), y - (alpha + beta * x)

    @staticmethod
    def _crossings(values: np.ndarray, center: float) -> int:
        centered = values - center
        return int(np.sum(centered[1:] * centered[:-1] < 0))

    def scan_pairs(self, start: int, end: int) -> pd.DataFrame:
        """Run the configured pair-selection method."""
        if self.config.selection_method == "distance":
            return self._scan_distance_pairs(start, end)
        if self.config.selection_method != "cointegration":
            raise ValueError(f"Unknown selection method: {self.config.selection_method}")
        return self._scan_cointegration_pairs(start, end)

    def _scan_cointegration_pairs(self, start: int, end: int) -> pd.DataFrame:
        """Select pairs with train/validation stability and FDR control."""
        cfg = self.config
        split = end - cfg.validation_weeks
        if split <= start:
            raise ValueError("Validation window must be shorter than the formation window")

        tickers = self.eligible(start, end)
        train = self.log_prices.iloc[start:split][tickers]
        validation = self.log_prices.iloc[split:end][tickers]
        labels = pd.DataFrame({
            "sector": self.data.sectors.reindex(tickers),
            "group": self.data.groups.reindex(tickers),
        })
        accepted = []

        for (sector, group), members in labels.groupby(["sector", "group"]):
            names = list(members.index)
            if len(names) < 2:
                continue
            values = train[names].to_numpy()
            correlations = train[names].diff().corr().to_numpy()
            candidates = []
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    if correlations[i, j] < cfg.min_return_corr:
                        continue
                    first, second = values[:, i], values[:, j]
                    try:
                        _, p_first, _ = coint(
                            first, second, trend="c", maxlag=1, autolag=None
                        )
                        _, p_second, _ = coint(
                            second, first, trend="c", maxlag=1, autolag=None
                        )
                    except ValueError:
                        continue
                    if p_first <= p_second:
                        y, x, y_name, x_name = first, second, names[i], names[j]
                        raw_p = p_first
                    else:
                        y, x, y_name, x_name = second, first, names[j], names[i]
                        raw_p = p_second
                    if not np.isfinite(raw_p):
                        continue
                    alpha, beta, spread = self._fit(y, x)
                    if not cfg.beta_min <= beta <= cfg.beta_max:
                        continue
                    sigma = spread.std(ddof=1)
                    if not np.isfinite(sigma) or sigma == 0:
                        continue
                    candidates.append({
                        "y": y_name,
                        "x": x_name,
                        "sector": sector,
                        "group": group,
                        "p_value": min(1.0, 2 * raw_p),
                        "train_alpha": alpha,
                        "train_beta": beta,
                        "train_mean": spread.mean(),
                        "train_sigma": sigma,
                    })
            if candidates:
                family = pd.DataFrame(candidates)
                reject, q_values, _, _ = multipletests(
                    family["p_value"], alpha=cfg.fdr_alpha, method="fdr_bh"
                )
                family["q_value"] = q_values
                accepted.extend(family.loc[reject].to_dict("records"))

        if not accepted:
            return pd.DataFrame()

        frame = pd.DataFrame(accepted)
        stable = []

        for row in frame.itertuples(index=False):
            val_spread = (
                validation[row.y].to_numpy()
                - (row.train_alpha + row.train_beta * validation[row.x].to_numpy())
            )
            mean_z = (val_spread.mean() - row.train_mean) / row.train_sigma
            std_ratio = val_spread.std(ddof=1) / row.train_sigma
            crossings = self._crossings(val_spread, row.train_mean)
            max_z = np.max(np.abs((val_spread - row.train_mean) / row.train_sigma))
            if abs(mean_z) > cfg.max_validation_mean_z:
                continue
            if not 0 < std_ratio <= cfg.max_validation_std_ratio:
                continue
            if crossings < cfg.min_validation_crossings or max_z >= cfg.max_validation_z:
                continue

            full_y = self.log_prices[row.y].iloc[start:end].to_numpy()
            full_x = self.log_prices[row.x].iloc[start:end].to_numpy()
            alpha, beta, spread = self._fit(full_y, full_x)
            spread_half_life = half_life(spread)
            if not cfg.beta_min <= beta <= cfg.beta_max:
                continue
            if not cfg.half_life_min <= spread_half_life <= cfg.half_life_max:
                continue
            stable.append({
                "y": row.y,
                "x": row.x,
                "sector": row.sector,
                "group": row.group,
                "p_value": row.p_value,
                "q_value": row.q_value,
                "alpha": alpha,
                "beta": beta,
                "mean": spread.mean(),
                "sigma": spread.std(ddof=1),
                "half_life": spread_half_life,
                "validation_mean_z": mean_z,
                "validation_std_ratio": std_ratio,
                "validation_crossings": crossings,
                "stability_score": abs(mean_z) + abs(np.log(std_ratio)) - 0.05 * crossings,
            })

        if not stable:
            return pd.DataFrame()

        ranked = pd.DataFrame(stable).sort_values(["stability_score", "q_value"])
        selected, used = [], set()
        for row in ranked.itertuples(index=False):
            if row.y in used or row.x in used:
                continue
            selected.append(row._asdict())
            used.update((row.y, row.x))
            if len(selected) == cfg.n_pairs:
                break
        return pd.DataFrame(selected)

    def _scan_distance_pairs(self, start: int, end: int) -> pd.DataFrame:
        """Select stable pairs by normalized-path distance."""
        cfg = self.config
        split = end - cfg.validation_weeks
        tickers = self.eligible(start, end)
        train = self.log_prices.iloc[start:split][tickers]
        validation = self.log_prices.iloc[split:end][tickers]
        labels = pd.DataFrame({
            "sector": self.data.sectors.reindex(tickers),
            "group": self.data.groups.reindex(tickers),
        })
        stable = []

        for (sector, group), members in labels.groupby(["sector", "group"]):
            names = list(members.index)
            if len(names) < 2:
                continue
            values = train[names].to_numpy()
            normalized = values - values[0]
            correlations = train[names].diff().corr().to_numpy()
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    if correlations[i, j] < cfg.min_return_corr:
                        continue
                    if np.std(values[:, i]) >= np.std(values[:, j]):
                        y_name, x_name = names[i], names[j]
                        y, x = values[:, i], values[:, j]
                    else:
                        y_name, x_name = names[j], names[i]
                        y, x = values[:, j], values[:, i]
                    alpha, beta, spread = self._fit(y, x)
                    if not cfg.beta_min <= beta <= cfg.beta_max:
                        continue
                    sigma = spread.std(ddof=1)
                    if not np.isfinite(sigma) or sigma == 0:
                        continue
                    val_spread = (
                        validation[y_name].to_numpy()
                        - (alpha + beta * validation[x_name].to_numpy())
                    )
                    mean_z = (val_spread.mean() - spread.mean()) / sigma
                    std_ratio = val_spread.std(ddof=1) / sigma
                    crossings = self._crossings(val_spread, spread.mean())
                    max_z = np.max(np.abs((val_spread - spread.mean()) / sigma))
                    if abs(mean_z) > cfg.max_validation_mean_z:
                        continue
                    if not 0 < std_ratio <= cfg.max_validation_std_ratio:
                        continue
                    if crossings < cfg.min_validation_crossings or max_z >= cfg.max_validation_z:
                        continue

                    full_y = self.log_prices[y_name].iloc[start:end].to_numpy()
                    full_x = self.log_prices[x_name].iloc[start:end].to_numpy()
                    full_alpha, full_beta, full_spread = self._fit(full_y, full_x)
                    spread_half_life = half_life(full_spread)
                    if not cfg.beta_min <= full_beta <= cfg.beta_max:
                        continue
                    if not cfg.half_life_min <= spread_half_life <= cfg.half_life_max:
                        continue
                    distance = np.mean((normalized[:, i] - normalized[:, j]) ** 2)
                    stability = abs(mean_z) + abs(np.log(std_ratio)) - 0.05 * crossings
                    stable.append({
                        "y": y_name,
                        "x": x_name,
                        "sector": sector,
                        "group": group,
                        "distance": distance,
                        "alpha": full_alpha,
                        "beta": full_beta,
                        "mean": full_spread.mean(),
                        "sigma": full_spread.std(ddof=1),
                        "half_life": spread_half_life,
                        "validation_mean_z": mean_z,
                        "validation_std_ratio": std_ratio,
                        "validation_crossings": crossings,
                        "stability_score": stability,
                    })

        if not stable:
            return pd.DataFrame()
        ranked = pd.DataFrame(stable).sort_values(["distance", "stability_score"])
        selected, used = [], set()
        for row in ranked.itertuples(index=False):
            if row.y in used or row.x in used:
                continue
            selected.append(row._asdict())
            used.update((row.y, row.x))
            if len(selected) == cfg.n_pairs:
                break
        return pd.DataFrame(selected)

    def trade_pair(self, pair: pd.Series, start: int, end: int) -> pd.Series:
        """Trade one frozen spread and return weekly net returns."""
        cfg = self.config
        y = self.log_prices[pair["y"]].iloc[start - 1:end]
        x = self.log_prices[pair["x"]].iloc[start - 1:end]
        valid = y.notna() & x.notna()
        output_index = self.dates[start:end]
        if valid.sum() < 3:
            return pd.Series(0.0, index=output_index)

        last_valid = valid[valid].index[-1]
        y, x = y.ffill(), x.ffill()
        z_score = (y - (pair["alpha"] + pair["beta"] * x) - pair["mean"]) / pair["sigma"]
        beta = pair["beta"]
        y_weight, x_weight = 1 / (1 + beta), beta / (1 + beta)
        positions = np.zeros(len(z_score))
        position = 0
        held = 0
        stopped = False

        for index, z_value in enumerate(z_score):
            if stopped or z_score.index[index] > last_valid:
                position, held = 0, 0
            elif position == 0:
                if abs(z_value) >= cfg.stop_z:
                    stopped = True
                elif z_value <= -cfg.entry_z:
                    position, held = 1, 0
                elif z_value >= cfg.entry_z:
                    position, held = -1, 0
            else:
                held += 1
                take_profit = abs(z_value) <= cfg.exit_z
                stop_loss = abs(z_value) >= cfg.stop_z
                timed_out = held >= cfg.max_holding_weeks
                if take_profit or stop_loss or timed_out:
                    position, held = 0, 0
                    stopped = stop_loss
            positions[index] = position

        positions = pd.Series(positions, index=z_score.index)
        gross = positions.shift(1) * (y_weight * y.diff() - x_weight * x.diff())
        costs = cfg.fee * positions.diff().abs()
        costs.iloc[1] += cfg.fee * abs(positions.iloc[0])
        costs.iloc[-1] += cfg.fee * abs(positions.iloc[-1])
        return (gross - costs).fillna(0.0).iloc[1:]

    def run(self, progress: bool = False) -> tuple[pd.Series, dict[int, pd.DataFrame]]:
        """Run all non-overlapping out-of-sample trading windows."""
        cfg = self.config
        selections = {}
        starts = range(cfg.formation_weeks, len(self.dates) - 1, cfg.trading_weeks)
        for number, start in enumerate(starts, 1):
            pairs = self.scan_pairs(start - cfg.formation_weeks, start)
            selections[start] = pairs
            if progress:
                print(f"Window {number}: {self.dates[start].date()} - {len(pairs)} pairs")
        return self.trade_selections(selections), selections

    def trade_selections(self, selections: dict[int, pd.DataFrame]) -> pd.Series:
        """Trade precomputed selections, for example under a different fee."""
        returns = []
        for start, pairs in selections.items():
            end = min(start + self.config.trading_weeks, len(self.dates))
            if pairs.empty:
                window = pd.Series(0.0, index=self.dates[start:end])
            else:
                pair_returns = pd.concat(
                    [self.trade_pair(pair, start, end) for _, pair in pairs.iterrows()],
                    axis=1,
                )
                window = pair_returns.sum(axis=1) / self.config.n_pairs
            returns.append(window)
        return pd.concat(returns)


def benchmark_returns(data: MarketData, index: pd.Index) -> pd.Series:
    """Align benchmark percentage returns with a strategy return index."""
    return data.benchmark.pct_change(fill_method=None).reindex(index).fillna(0.0)
