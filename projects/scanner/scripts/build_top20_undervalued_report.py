from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf


RISK_FREE_RATE = 0.043
BENCHMARKS = ["QQQ", "SPY"]


@dataclass
class BacktestResult:
    nav: pd.Series
    returns: pd.Series
    metrics: dict[str, float]


def compute_metrics(nav: pd.Series) -> dict[str, float]:
    returns = nav.pct_change().dropna()
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    total_return = nav.iloc[-1] / nav.iloc[0] - 1.0
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0
    vol = returns.std() * np.sqrt(252)
    sharpe = ((returns.mean() * 252) - RISK_FREE_RATE) / vol if vol else np.nan
    downside = returns[returns < 0].std() * np.sqrt(252)
    sortino = ((returns.mean() * 252) - RISK_FREE_RATE) / downside if downside and not np.isnan(downside) else np.nan
    drawdown = nav / nav.cummax() - 1.0
    max_drawdown = drawdown.min()
    calmar = cagr / abs(max_drawdown) if max_drawdown else np.nan
    return {
        "ending_value": float(nav.iloc[-1]),
        "total_return_pct": float(total_return * 100.0),
        "cagr_pct": float(cagr * 100.0),
        "vol_pct": float(vol * 100.0),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown_pct": float(max_drawdown * 100.0),
        "calmar": float(calmar),
    }


def format_pct(value: float) -> str:
    return f"{value:.2f}%"


def format_money(value: float) -> str:
    return f"${value:,.0f}"


def build_backtest(
    csv_path: Path,
    analysis_date: str,
    end_date: str,
    initial_capital: float,
    output_path: Path,
) -> tuple[pd.DataFrame, dict[str, BacktestResult], str, str]:
    screen = pd.read_csv(csv_path)
    ranked = (
        screen.sort_values("undervaluation_pct", ascending=False)
        .drop_duplicates(subset=["company_name"], keep="first")
        .head(20)
        .copy()
    )
    tickers = ranked["ticker"].tolist()
    download_start = (pd.Timestamp(analysis_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    download_end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    prices = yf.download(
        tickers + BENCHMARKS,
        start=download_start,
        end=download_end,
        auto_adjust=True,
        progress=False,
        group_by="column",
    )["Close"]
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()
    prices = prices.dropna(how="all")
    execution_date = prices.index.min().strftime("%Y-%m-%d")
    last_date = prices.index.max().strftime("%Y-%m-%d")

    portfolio_prices = prices[tickers].copy()
    valid_tickers = portfolio_prices.columns[portfolio_prices.notna().all()].tolist()
    portfolio_prices = portfolio_prices[valid_tickers]
    ranked = ranked[ranked["ticker"].isin(valid_tickers)].copy()

    portfolio_returns = portfolio_prices.pct_change().fillna(0.0).mean(axis=1)
    portfolio_nav = initial_capital * (1.0 + portfolio_returns).cumprod()
    benchmark_navs = {}
    for benchmark in BENCHMARKS:
        benchmark_returns = prices[benchmark].pct_change().fillna(0.0)
        benchmark_navs[benchmark] = initial_capital * (1.0 + benchmark_returns).cumprod()

    results = {
        "Top 20 Undervalued": BacktestResult(
            nav=portfolio_nav,
            returns=portfolio_returns,
            metrics=compute_metrics(portfolio_nav),
        )
    }
    for benchmark, nav in benchmark_navs.items():
        results[benchmark] = BacktestResult(
            nav=nav,
            returns=nav.pct_change().fillna(0.0),
            metrics=compute_metrics(nav),
        )

    start_prices = portfolio_prices.iloc[0]
    end_prices = portfolio_prices.iloc[-1]
    ranked["start_price"] = ranked["ticker"].map(start_prices)
    ranked["end_price"] = ranked["ticker"].map(end_prices)
    ranked["holding_return_pct"] = (ranked["end_price"] / ranked["start_price"] - 1.0) * 100.0
    ranked["portfolio_weight_pct"] = 100.0 / len(ranked)
    ranked["contribution_pct_points"] = ranked["holding_return_pct"] * (1.0 / len(ranked))
    ranked = ranked.sort_values("contribution_pct_points", ascending=False)

    build_report(
        ranked=ranked,
        results=results,
        analysis_date=analysis_date,
        execution_date=execution_date,
        end_date=last_date,
        initial_capital=initial_capital,
        output_path=output_path,
    )
    return ranked, results, execution_date, last_date


def build_report(
    ranked: pd.DataFrame,
    results: dict[str, BacktestResult],
    analysis_date: str,
    execution_date: str,
    end_date: str,
    initial_capital: float,
    output_path: Path,
) -> None:
    equity_df = pd.DataFrame(
        {
            "Date": results["Top 20 Undervalued"].nav.index,
            "Top 20 Undervalued": results["Top 20 Undervalued"].nav.values,
            "QQQ": results["QQQ"].nav.reindex(results["Top 20 Undervalued"].nav.index).values,
            "SPY": results["SPY"].nav.reindex(results["Top 20 Undervalued"].nav.index).values,
        }
    )
    drawdown_df = pd.DataFrame({"Date": equity_df["Date"]})
    for label in ["Top 20 Undervalued", "QQQ", "SPY"]:
        series = equity_df.set_index("Date")[label]
        drawdown_df[label] = (series / series.cummax() - 1.0) * 100.0

    equity_long = equity_df.melt(id_vars="Date", var_name="Series", value_name="Value")
    drawdown_long = drawdown_df.melt(id_vars="Date", var_name="Series", value_name="Drawdown")
    holdings_display = ranked[
        [
            "ticker",
            "company_name",
            "sector",
            "undervaluation_pct",
            "start_price",
            "end_price",
            "holding_return_pct",
            "contribution_pct_points",
        ]
    ].copy()

    metric_rows = []
    for label, result in results.items():
        row = {"Series": label}
        row.update(result.metrics)
        metric_rows.append(row)
    metrics_df = pd.DataFrame(metric_rows)

    line_fig = px.line(
        equity_long,
        x="Date",
        y="Value",
        color="Series",
        color_discrete_map={
            "Top 20 Undervalued": "#2563eb",
            "QQQ": "#dc2626",
            "SPY": "#059669",
        },
    )
    line_fig.update_layout(
        height=460,
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
        color_discrete_map={
            "Top 20 Undervalued": "#2563eb",
            "QQQ": "#dc2626",
            "SPY": "#059669",
        },
    )
    drawdown_fig.update_layout(
        height=360,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
        xaxis_title="Date",
        yaxis_title="Drawdown, %",
        legend_title_text="",
        hovermode="x unified",
    )

    contributors = ranked.copy()
    contributors["label"] = contributors["ticker"] + " | " + contributors["company_name"]
    contrib_fig = px.bar(
        contributors.head(10),
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

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Top 20 Undervalued Backtest</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --bg:#ffffff;
      --fg:#111111;
      --muted:#6b7280;
      --line:#d1d5db;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      background:var(--bg);
      color:var(--fg);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
      line-height:1.45;
    }}
    .page {{ max-width: 1240px; margin: 0 auto; padding: 44px 28px 72px; }}
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
    @media (max-width: 920px) {{
      .grid3, .grid2 {{ grid-template-columns:1fr; }}
      .page {{ padding:28px 18px 48px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <div class="meta">Point-in-time undervaluation portfolio test</div>
    <h1>Top 20 undervalued companies from 2024-04-18</h1>
    <div class="meta">Screen date: {analysis_date} | Execution date: {execution_date} | End date: {end_date} | Initial capital: {format_money(initial_capital)} | Universe source: S&P 100 export | Benchmarks: QQQ and SPY (S&P 500 proxy)</div>

    <section class="section grid3">
      <div class="metricbox">
        <div class="metriclabel">Portfolio ending value</div>
        <div class="metricvalue">{format_money(results["Top 20 Undervalued"].metrics["ending_value"])}</div>
        <div class="small">Total return {format_pct(results["Top 20 Undervalued"].metrics["total_return_pct"])}</div>
      </div>
      <div class="metricbox">
        <div class="metriclabel">Outperformance vs QQQ</div>
        <div class="metricvalue">{results["Top 20 Undervalued"].metrics["total_return_pct"] - results["QQQ"].metrics["total_return_pct"]:.2f}%</div>
        <div class="small">QQQ total return {format_pct(results["QQQ"].metrics["total_return_pct"])}</div>
      </div>
      <div class="metricbox">
        <div class="metriclabel">Outperformance vs SPY</div>
        <div class="metricvalue">{results["Top 20 Undervalued"].metrics["total_return_pct"] - results["SPY"].metrics["total_return_pct"]:.2f}%</div>
        <div class="small">SPY total return {format_pct(results["SPY"].metrics["total_return_pct"])}</div>
      </div>
    </section>

    <section class="section">
      <h2>Performance summary</h2>
      {metrics_df.to_html(index=False, float_format=lambda x: f"{x:.2f}", classes="metrics")}
    </section>

    <section class="section">
      <h2>Equity curve</h2>
      <div id="equityChart" class="chart"></div>
    </section>

    <section class="section grid2">
      <div>
        <h2>Drawdown</h2>
        <div id="drawdownChart" class="chart-sm"></div>
      </div>
      <div>
        <h2>Top contributors</h2>
        <div id="contribChart" class="chart-sm"></div>
      </div>
    </section>

    <section class="section">
      <h2>Holdings used at launch</h2>
      {holdings_display.to_html(index=False, float_format=lambda x: f"{x:.2f}")}
    </section>

    <section class="section">
      <h2>Methodology</h2>
      <div class="small">
        1. The source file is the exported S&P 100 undervaluation screen with analysis date 2024-04-18.<br/>
        2. One share class per company was kept; duplicate company names were removed before selecting the top 20 names by undervaluation percentage.<br/>
        3. Portfolio construction is equal-weight, 20 positions, no rebalance, buy-and-hold from the next completed trading session after the screen date.<br/>
        4. Returns use adjusted close, so dividends and splits are included in both the portfolio and the benchmarks.<br/>
        5. Benchmarks are QQQ and SPY, where SPY is used as the investable proxy for the S&P 500.<br/>
        6. Risk-free rate for Sharpe and Sortino is fixed at 4.30% for comparability with prior reports.
      </div>
    </section>
  </main>
  <script>
    const equityData = {line_fig.to_json()};
    const drawdownData = {drawdown_fig.to_json()};
    const contribData = {contrib_fig.to_json()};
    Plotly.newPlot('equityChart', equityData.data, equityData.layout, {{responsive:true, displaylogo:false, displayModeBar:true, scrollZoom:true}});
    Plotly.newPlot('drawdownChart', drawdownData.data, drawdownData.layout, {{responsive:true, displaylogo:false, displayModeBar:true, scrollZoom:true}});
    Plotly.newPlot('contribChart', contribData.data, contribData.layout, {{responsive:true, displaylogo:false, displayModeBar:true, scrollZoom:true}});
  </script>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--analysis-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--initial-capital", type=float, default=20000.0)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_backtest(
        csv_path=Path(args.csv),
        analysis_date=args.analysis_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()
