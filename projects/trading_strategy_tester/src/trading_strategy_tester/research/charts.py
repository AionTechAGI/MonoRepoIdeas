"""HTML chart generation for cached market data."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from trading_strategy_tester.data.historical_loader import HistoricalBar
from trading_strategy_tester.data.range_downloader import parse_ibkr_bar_timestamp


def write_candlestick_volume_chart(
    bars: list[HistoricalBar] | tuple[HistoricalBar, ...],
    output_path: str | Path,
    title: str,
) -> Path:
    if not bars:
        raise ValueError("Cannot chart an empty bar set")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    x_values = [parse_ibkr_bar_timestamp(bar.timestamp) for bar in bars]
    volumes = [bar.volume or 0 for bar in bars]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.76, 0.24],
        subplot_titles=(title, "Volume"),
    )
    fig.add_trace(
        go.Candlestick(
            x=x_values,
            open=[bar.open for bar in bars],
            high=[bar.high for bar in bars],
            low=[bar.low for bar in bars],
            close=[bar.close for bar in bars],
            name="OHLC",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=x_values,
            y=volumes,
            name="Volume",
            marker_color="#4c78a8",
        ),
        row=2,
        col=1,
    )
    fig.update_layout(
        template="plotly_white",
        height=850,
        xaxis_rangeslider_visible=False,
        legend_orientation="h",
        legend_yanchor="bottom",
        legend_y=1.02,
        legend_xanchor="right",
        legend_x=1,
        margin=dict(l=60, r=30, t=70, b=45),
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.write_html(output, include_plotlyjs="cdn", full_html=True)
    return output
