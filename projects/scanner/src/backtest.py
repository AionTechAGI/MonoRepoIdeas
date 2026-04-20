from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import yfinance as yf

from src.core.config import (
    BACKTEST_ENGINE_VERSION,
    DEFAULT_BORROW_COST_PCT,
    DEFAULT_COMMISSION_PER_ORDER,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_SLIPPAGE_BPS,
)
from src.core.schemas import BacktestAssumptions


RISK_FREE_RATE = 0.043
BENCHMARKS = ["QQQ", "SPY"]


@dataclass
class BacktestSeries:
    nav: pd.Series
    returns: pd.Series
    metrics: dict[str, float]


@dataclass
class BacktestOutcome:
    analysis_date: str
    requested_end_date: str
    execution_date: str
    actual_end_date: str
    initial_capital: float
    portfolio_label: str
    selected_holdings: pd.DataFrame
    sector_exposure: pd.DataFrame
    equity_df: pd.DataFrame
    drawdown_df: pd.DataFrame
    assumptions: BacktestAssumptions
    engine_version: str
    results: dict[str, BacktestSeries]


def _safe_float(value: float | np.floating | None) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return float("nan")
    return float(value)


def _relative_metrics(returns: pd.Series, benchmark_returns: pd.Series) -> dict[str, float]:
    aligned = pd.concat([returns, benchmark_returns], axis=1, join="inner").dropna()
    if aligned.empty or aligned.iloc[:, 1].var() == 0:
        return {"beta_vs_spy": float("nan"), "alpha_vs_spy_pct": float("nan")}
    portfolio = aligned.iloc[:, 0]
    benchmark = aligned.iloc[:, 1]
    beta = portfolio.cov(benchmark) / benchmark.var()
    daily_rf = RISK_FREE_RATE / 252.0
    alpha_daily = (portfolio.mean() - daily_rf) - beta * (benchmark.mean() - daily_rf)
    alpha_annual = alpha_daily * 252.0
    return {"beta_vs_spy": float(beta), "alpha_vs_spy_pct": float(alpha_annual * 100.0)}


def compute_metrics(nav: pd.Series, benchmark_returns: pd.Series | None = None) -> dict[str, float]:
    returns = nav.pct_change().dropna()
    if nav.empty:
        return {
            "ending_value": float("nan"),
            "total_return_pct": float("nan"),
            "cagr_pct": float("nan"),
            "vol_pct": float("nan"),
            "sharpe": float("nan"),
            "sortino": float("nan"),
            "max_drawdown_pct": float("nan"),
            "calmar": float("nan"),
            "beta_vs_spy": float("nan"),
            "alpha_vs_spy_pct": float("nan"),
        }

    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1 / 365.25)
    total_return = nav.iloc[-1] / nav.iloc[0] - 1.0
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0 if nav.iloc[0] > 0 else np.nan
    vol = returns.std() * np.sqrt(252) if not returns.empty else np.nan
    excess_return = (returns.mean() * 252) - RISK_FREE_RATE if not returns.empty else np.nan
    sharpe = excess_return / vol if vol and not np.isnan(vol) else np.nan
    downside = returns[returns < 0].std() * np.sqrt(252) if not returns.empty else np.nan
    sortino = excess_return / downside if downside and not np.isnan(downside) else np.nan
    drawdown = nav / nav.cummax() - 1.0
    max_drawdown = drawdown.min() if not drawdown.empty else np.nan
    calmar = cagr / abs(max_drawdown) if max_drawdown and not np.isnan(max_drawdown) else np.nan

    metrics = {
        "ending_value": float(nav.iloc[-1]),
        "total_return_pct": float(total_return * 100.0),
        "cagr_pct": float(cagr * 100.0),
        "vol_pct": float(vol * 100.0) if not np.isnan(vol) else float("nan"),
        "sharpe": float(sharpe) if not np.isnan(sharpe) else float("nan"),
        "sortino": float(sortino) if not np.isnan(sortino) else float("nan"),
        "max_drawdown_pct": float(max_drawdown * 100.0) if not np.isnan(max_drawdown) else float("nan"),
        "calmar": float(calmar) if not np.isnan(calmar) else float("nan"),
    }
    metrics.update(_relative_metrics(returns, benchmark_returns if benchmark_returns is not None else returns.iloc[0:0]))
    return metrics


def resolve_end_date(start_date: date, mode: str, custom_date: date | None = None) -> date:
    today = datetime.now(UTC).date()
    if mode == "1 year":
        return min(start_date + timedelta(days=365), today)
    if mode == "2 years":
        return min(start_date + timedelta(days=730), today)
    if mode == "3 years":
        return min(start_date + timedelta(days=1095), today)
    if mode == "To today":
        return today
    if custom_date is not None:
        return min(custom_date, today)
    return today


def _benchmark_nav(
    price_series: pd.Series,
    initial_capital: float,
    commission_per_order: float,
    slippage_bps: float,
    liquidate_at_end: bool,
) -> tuple[pd.Series, float]:
    returns = price_series.pct_change().fillna(0.0)
    gross_exposure = 1.0
    entry_cost = (initial_capital * gross_exposure * slippage_bps / 10_000.0) + commission_per_order
    nav = max(initial_capital - entry_cost, 0.0) * (1.0 + returns).cumprod()
    exit_cost = 0.0
    if liquidate_at_end and not nav.empty:
        exit_cost = (nav.iloc[-1] * gross_exposure * slippage_bps / 10_000.0) + commission_per_order
        nav.iloc[-1] = max(nav.iloc[-1] - exit_cost, 0.0)
    return nav, float(entry_cost + exit_cost)


def run_undervaluation_backtest(
    screen_df: pd.DataFrame,
    analysis_date: str,
    end_date: str,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    portfolio_size: int = 20,
    strategy_mode: str = "long_only",
    benchmarks: list[str] | None = None,
    commission_per_order: float = DEFAULT_COMMISSION_PER_ORDER,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    borrow_cost_pct: float = DEFAULT_BORROW_COST_PCT,
    liquidate_at_end: bool = True,
) -> BacktestOutcome:
    benchmark_list = benchmarks or BENCHMARKS
    clean = screen_df.copy()
    clean = clean[clean["status"] == "ok"] if "status" in clean.columns else clean
    clean = clean.sort_values("undervaluation_pct", ascending=False)
    clean = clean.drop_duplicates(subset=["company_name"], keep="first").reset_index(drop=True)

    if strategy_mode == "short_only":
        short_leg = clean.sort_values("undervaluation_pct", ascending=True).head(portfolio_size).copy()
        short_leg["position"] = "Short"
        selected = short_leg.copy()
        tickers = short_leg["ticker"].tolist()
        portfolio_label = f"Short {len(tickers)} Overvalued"
        long_weight = 0.0
        short_weight = 1.0
    elif strategy_mode == "long_short":
        long_leg = clean.head(portfolio_size).copy()
        short_leg = clean.sort_values("undervaluation_pct", ascending=True).head(portfolio_size).copy()
        long_leg["position"] = "Long"
        short_leg["position"] = "Short"
        selected = pd.concat([long_leg, short_leg], ignore_index=True)
        tickers = pd.unique(selected["ticker"]).tolist()
        portfolio_label = f"Long {len(long_leg)} / Short {len(short_leg)}"
        long_weight = 0.5
        short_weight = 0.5
    else:
        long_leg = clean.head(portfolio_size).copy()
        long_leg["position"] = "Long"
        selected = long_leg.copy()
        tickers = long_leg["ticker"].tolist()
        portfolio_label = f"Top {len(tickers)} Undervalued"
        long_weight = 1.0
        short_weight = 0.0

    if not tickers:
        raise ValueError("No holdings available for backtest.")

    download_start = (pd.Timestamp(analysis_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    download_end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    prices = yf.download(
        tickers + benchmark_list,
        start=download_start,
        end=download_end,
        auto_adjust=True,
        progress=False,
        group_by="column",
    )["Close"]
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()
    prices = prices.dropna(how="all")
    if prices.empty:
        raise ValueError("No price history returned for the requested backtest window.")

    execution_date = prices.index.min().strftime("%Y-%m-%d")
    actual_end_date = prices.index.max().strftime("%Y-%m-%d")

    all_portfolio_prices = prices[tickers].copy()
    valid_tickers = all_portfolio_prices.columns[all_portfolio_prices.notna().all()].tolist()
    portfolio_prices = all_portfolio_prices[valid_tickers]
    if portfolio_prices.empty:
        raise ValueError("No complete price series for selected holdings.")
    selected = selected[selected["ticker"].isin(valid_tickers)].copy()

    long_tickers = selected.loc[selected["position"] == "Long", "ticker"].tolist()
    short_tickers = selected.loc[selected["position"] == "Short", "ticker"].tolist()
    long_returns = portfolio_prices[long_tickers].pct_change().fillna(0.0).mean(axis=1) if long_tickers else pd.Series(0.0, index=portfolio_prices.index)
    short_returns = portfolio_prices[short_tickers].pct_change().fillna(0.0).mean(axis=1) if short_tickers else pd.Series(0.0, index=portfolio_prices.index)
    portfolio_returns = (long_weight * long_returns) - (short_weight * short_returns)

    daily_borrow_cost = short_weight * (borrow_cost_pct / 100.0) / 252.0
    if daily_borrow_cost:
        portfolio_returns = portfolio_returns - daily_borrow_cost

    gross_exposure = long_weight + short_weight
    entry_cost = (initial_capital * gross_exposure * slippage_bps / 10_000.0) + (commission_per_order * len(selected))
    start_capital = max(initial_capital - entry_cost, 0.0)
    portfolio_nav = start_capital * (1.0 + portfolio_returns).cumprod()
    exit_cost = 0.0
    if liquidate_at_end and not portfolio_nav.empty:
        exit_cost = (portfolio_nav.iloc[-1] * gross_exposure * slippage_bps / 10_000.0) + (commission_per_order * len(selected))
        portfolio_nav.iloc[-1] = max(portfolio_nav.iloc[-1] - exit_cost, 0.0)

    spy_series = prices["SPY"].reindex(portfolio_nav.index).ffill()
    spy_returns = spy_series.pct_change().fillna(0.0)
    turnover_pct = gross_exposure * (200.0 if liquidate_at_end else 100.0)
    results: dict[str, BacktestSeries] = {
        portfolio_label: BacktestSeries(
            nav=portfolio_nav,
            returns=portfolio_returns,
            metrics=compute_metrics(portfolio_nav, spy_returns),
        )
    }
    results[portfolio_label].metrics["turnover_pct"] = float(turnover_pct)
    results[portfolio_label].metrics["costs_usd"] = float(entry_cost + exit_cost)
    results[portfolio_label].metrics["borrow_cost_pct_assumption"] = float(borrow_cost_pct)

    aligned_index = portfolio_nav.index
    for benchmark in benchmark_list:
        benchmark_nav, benchmark_costs = _benchmark_nav(
            prices[benchmark].reindex(aligned_index).ffill(),
            initial_capital=initial_capital,
            commission_per_order=commission_per_order,
            slippage_bps=slippage_bps,
            liquidate_at_end=liquidate_at_end,
        )
        benchmark_returns = benchmark_nav.pct_change().fillna(0.0)
        results[benchmark] = BacktestSeries(
            nav=benchmark_nav,
            returns=benchmark_returns,
            metrics=compute_metrics(benchmark_nav, spy_returns),
        )
        results[benchmark].metrics["turnover_pct"] = float(200.0 if liquidate_at_end else 100.0)
        results[benchmark].metrics["costs_usd"] = float(benchmark_costs)
        results[benchmark].metrics["borrow_cost_pct_assumption"] = 0.0

    start_prices = portfolio_prices.iloc[0]
    end_prices = portfolio_prices.iloc[-1]
    selected["start_price"] = selected["ticker"].map(start_prices)
    selected["end_price"] = selected["ticker"].map(end_prices)
    selected["holding_return_pct"] = (selected["end_price"] / selected["start_price"] - 1.0) * 100.0
    if strategy_mode == "long_short":
        long_count = max((selected["position"] == "Long").sum(), 1)
        short_count = max((selected["position"] == "Short").sum(), 1)
        selected["portfolio_weight_pct"] = np.where(
            selected["position"] == "Long",
            100.0 * long_weight / long_count,
            -100.0 * short_weight / short_count,
        )
        selected["contribution_pct_points"] = np.where(
            selected["position"] == "Long",
            selected["holding_return_pct"] * long_weight / long_count,
            -selected["holding_return_pct"] * short_weight / short_count,
        )
    elif strategy_mode == "short_only":
        selected["portfolio_weight_pct"] = -100.0 / len(selected)
        selected["contribution_pct_points"] = -selected["holding_return_pct"] * (1.0 / len(selected))
    else:
        selected["portfolio_weight_pct"] = 100.0 / len(selected)
        selected["contribution_pct_points"] = selected["holding_return_pct"] * (1.0 / len(selected))
    selected = selected.sort_values("contribution_pct_points", ascending=False).reset_index(drop=True)

    sector_exposure = (
        selected.groupby("sector", dropna=False)["portfolio_weight_pct"]
        .sum()
        .reset_index()
        .rename(columns={"portfolio_weight_pct": "weight_pct"})
        .sort_values("weight_pct", ascending=False)
        .reset_index(drop=True)
    )

    equity_df = pd.DataFrame({"Date": aligned_index})
    for label, series in results.items():
        equity_df[label] = series.nav.reindex(aligned_index).values

    drawdown_df = pd.DataFrame({"Date": aligned_index})
    for label, series in results.items():
        drawdown_df[label] = (series.nav.reindex(aligned_index) / series.nav.reindex(aligned_index).cummax() - 1.0) * 100.0

    assumptions = BacktestAssumptions(
        strategy_mode=strategy_mode,
        portfolio_size=portfolio_size,
        initial_capital=float(initial_capital),
        commission_per_order=float(commission_per_order),
        slippage_bps=float(slippage_bps),
        borrow_cost_pct=float(borrow_cost_pct),
        liquidate_at_end=liquidate_at_end,
        benchmark="SPY",
    )

    return BacktestOutcome(
        analysis_date=analysis_date,
        requested_end_date=end_date,
        execution_date=execution_date,
        actual_end_date=actual_end_date,
        initial_capital=initial_capital,
        portfolio_label=portfolio_label,
        selected_holdings=selected,
        sector_exposure=sector_exposure,
        equity_df=equity_df,
        drawdown_df=drawdown_df,
        assumptions=assumptions,
        engine_version=BACKTEST_ENGINE_VERSION,
        results=results,
    )


def metrics_dataframe(outcome: BacktestOutcome) -> pd.DataFrame:
    rows = []
    for label, result in outcome.results.items():
        row = {"Series": label}
        row.update(result.metrics)
        rows.append(row)
    return pd.DataFrame(rows)


def build_backtest_figures(outcome: BacktestOutcome):
    color_map = {
        outcome.portfolio_label: "#2563eb",
        "QQQ": "#dc2626",
        "SPY": "#059669",
    }
    equity_long = outcome.equity_df.melt(id_vars="Date", var_name="Series", value_name="Value")
    drawdown_long = outcome.drawdown_df.melt(id_vars="Date", var_name="Series", value_name="Drawdown")

    equity_fig = px.line(
        equity_long,
        x="Date",
        y="Value",
        color="Series",
        color_discrete_map=color_map,
    )
    equity_fig.update_layout(
        height=440,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
        xaxis_title="Date",
        yaxis_title="Portfolio value, USD",
        legend_title_text="",
        hovermode="x unified",
    )

    drawdown_fig = px.line(
        drawdown_long,
        x="Date",
        y="Drawdown",
        color="Series",
        color_discrete_map=color_map,
    )
    drawdown_fig.update_layout(
        height=360,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
        xaxis_title="Date",
        yaxis_title="Drawdown, %",
        legend_title_text="",
        hovermode="x unified",
    )

    contrib_fig = px.bar(
        outcome.selected_holdings.head(12),
        x="ticker",
        y="contribution_pct_points",
        color="sector",
        hover_data={
            "company_name": True,
            "undervaluation_pct": ":.2f",
            "holding_return_pct": ":.2f",
            "contribution_pct_points": ":.2f",
        },
    )
    contrib_fig.update_layout(
        height=360,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
        xaxis_title="Ticker",
        yaxis_title="Contribution to portfolio return, pct points",
        legend_title_text="Sector",
    )

    sector_fig = px.bar(
        outcome.sector_exposure,
        x="sector",
        y="weight_pct",
        color="weight_pct",
        color_continuous_scale="RdBu",
    )
    sector_fig.update_layout(
        height=320,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
        xaxis_title="Sector",
        yaxis_title="Weight, %",
        coloraxis_showscale=False,
    )
    return equity_fig, drawdown_fig, contrib_fig, sector_fig


def build_backtest_report_html(outcome: BacktestOutcome) -> str:
    metrics_df = metrics_dataframe(outcome)
    holdings_display = outcome.selected_holdings[
        [
            "position",
            "ticker",
            "company_name",
            "sector",
            "portfolio_weight_pct",
            "undervaluation_pct",
            "start_price",
            "end_price",
            "holding_return_pct",
            "contribution_pct_points",
        ]
    ].copy()
    equity_fig, drawdown_fig, contrib_fig, sector_fig = build_backtest_figures(outcome)
    portfolio_metrics = outcome.results[outcome.portfolio_label].metrics
    qqq_metrics = outcome.results["QQQ"].metrics
    spy_metrics = outcome.results["SPY"].metrics
    assumptions = outcome.assumptions
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{outcome.portfolio_label} Backtest</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --bg:#ffffff; --fg:#111111; --muted:#6b7280; --line:#d1d5db;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--fg); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace; line-height:1.45; }}
    .page {{ max-width:1240px; margin:0 auto; padding:44px 28px 72px; }}
    h1, h2 {{ font-size:15px; margin:0 0 14px; font-weight:600; }}
    .meta, .small {{ color:var(--muted); font-size:12px; }}
    .section {{ margin-top:32px; padding-top:18px; border-top:1px solid var(--line); }}
    .grid3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:24px; }}
    .grid2 {{ display:grid; grid-template-columns:1.2fr .8fr; gap:24px; }}
    .metricbox {{ border:1px solid var(--line); padding:14px 16px; }}
    .metriclabel {{ font-size:12px; color:var(--muted); }}
    .metricvalue {{ font-size:22px; margin-top:6px; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; }}
    th, td {{ padding:8px 0; border-bottom:1px solid var(--line); text-align:right; vertical-align:top; }}
    th:first-child, td:first-child {{ text-align:left; }}
    th:nth-child(2), td:nth-child(2) {{ text-align:left; padding-left:14px; }}
    .chart {{ height:460px; }}
    .chart-sm {{ height:360px; }}
  </style>
</head>
<body>
  <main class="page">
    <div class="meta">Point-in-time undervaluation portfolio test</div>
    <h1>{outcome.portfolio_label} from {outcome.analysis_date}</h1>
    <div class="meta">Screen date: {outcome.analysis_date} | Execution date: {outcome.execution_date} | Requested end date: {outcome.requested_end_date} | Actual end date: {outcome.actual_end_date} | Initial capital: ${outcome.initial_capital:,.0f} | Engine: {outcome.engine_version}</div>
    <section class="section grid3">
      <div class="metricbox"><div class="metriclabel">Portfolio ending value</div><div class="metricvalue">${portfolio_metrics["ending_value"]:,.0f}</div><div class="small">Total return {portfolio_metrics["total_return_pct"]:.2f}%</div></div>
      <div class="metricbox"><div class="metriclabel">Outperformance vs QQQ</div><div class="metricvalue">{portfolio_metrics["total_return_pct"] - qqq_metrics["total_return_pct"]:.2f}%</div><div class="small">QQQ total return {qqq_metrics["total_return_pct"]:.2f}%</div></div>
      <div class="metricbox"><div class="metriclabel">Outperformance vs SPY</div><div class="metricvalue">{portfolio_metrics["total_return_pct"] - spy_metrics["total_return_pct"]:.2f}%</div><div class="small">SPY total return {spy_metrics["total_return_pct"]:.2f}%</div></div>
    </section>
    <section class="section">
      <h2>Assumptions</h2>
      <div class="small">Strategy: {assumptions.strategy_mode} | Portfolio size: {assumptions.portfolio_size} | Commission/order: ${assumptions.commission_per_order:.2f} | Slippage: {assumptions.slippage_bps:.2f} bps | Borrow cost: {assumptions.borrow_cost_pct:.2f}% | Liquidate at end: {assumptions.liquidate_at_end}</div>
    </section>
    <section class="section"><h2>Performance summary</h2>{metrics_df.to_html(index=False, float_format=lambda x: f"{x:.2f}")}</section>
    <section class="section"><h2>Equity curve</h2><div id="equityChart" class="chart"></div></section>
    <section class="section grid2"><div><h2>Drawdown</h2><div id="drawdownChart" class="chart-sm"></div></div><div><h2>Top contributors</h2><div id="contribChart" class="chart-sm"></div></div></section>
    <section class="section"><h2>Sector exposure</h2><div id="sectorChart" class="chart-sm"></div></section>
    <section class="section"><h2>Holdings used at launch</h2>{holdings_display.to_html(index=False, float_format=lambda x: f"{x:.2f}")}</section>
  </main>
  <script>
    const equityData = {equity_fig.to_json()};
    const drawdownData = {drawdown_fig.to_json()};
    const contribData = {contrib_fig.to_json()};
    const sectorData = {sector_fig.to_json()};
    Plotly.newPlot('equityChart', equityData.data, equityData.layout, {{responsive:true, displaylogo:false, displayModeBar:true, scrollZoom:true}});
    Plotly.newPlot('drawdownChart', drawdownData.data, drawdownData.layout, {{responsive:true, displaylogo:false, displayModeBar:true, scrollZoom:true}});
    Plotly.newPlot('contribChart', contribData.data, contribData.layout, {{responsive:true, displaylogo:false, displayModeBar:true, scrollZoom:true}});
    Plotly.newPlot('sectorChart', sectorData.data, sectorData.layout, {{responsive:true, displaylogo:false, displayModeBar:true, scrollZoom:true}});
  </script>
</body>
</html>"""
    return html
