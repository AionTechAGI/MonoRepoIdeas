"""HTML chart generation for cached market data."""

from __future__ import annotations

from datetime import datetime
import math
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

    timestamps = [parse_ibkr_bar_timestamp(bar.timestamp) for bar in bars]
    x_values = list(range(len(bars)))
    volumes = [bar.volume or 0 for bar in bars]
    hover_text = [
        "<br>".join(
            [
                f"Time: {timestamp:%Y-%m-%d %H:%M}",
                f"Open: {bar.open:.2f}",
                f"High: {bar.high:.2f}",
                f"Low: {bar.low:.2f}",
                f"Close: {bar.close:.2f}",
                f"Volume: {bar.volume or 0:,.0f}",
            ]
        )
        for timestamp, bar in zip(timestamps, bars)
    ]
    tick_values, tick_text = market_time_ticks(timestamps)

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
            text=hover_text,
            hoverinfo="text",
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
            text=hover_text,
            hoverinfo="text",
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
    fig.update_xaxes(
        type="linear",
        tickmode="array",
        tickvals=tick_values,
        ticktext=tick_text,
        row=1,
        col=1,
    )
    fig.update_xaxes(
        type="linear",
        tickmode="array",
        tickvals=tick_values,
        ticktext=tick_text,
        title_text="Trading sessions",
        row=2,
        col=1,
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.write_html(output, include_plotlyjs="cdn", full_html=True)
    return output


def market_time_ticks(
    timestamps: list[datetime] | tuple[datetime, ...],
    max_ticks: int = 12,
) -> tuple[list[int], list[str]]:
    """Return axis ticks for a compressed market-time chart.

    The X axis uses bar sequence numbers instead of wall-clock datetimes, which
    removes weekends, holidays, and overnight gaps while preserving bar order.
    """

    if not timestamps:
        return [], []

    first_index_by_day: list[tuple[int, datetime]] = []
    seen_days: set[object] = set()
    for index, timestamp in enumerate(timestamps):
        day = timestamp.date()
        if day not in seen_days:
            seen_days.add(day)
            first_index_by_day.append((index, timestamp))

    stride = max(1, math.ceil(len(first_index_by_day) / max_ticks))
    selected = first_index_by_day[::stride]
    if selected[-1][0] != first_index_by_day[-1][0]:
        selected.append(first_index_by_day[-1])

    return (
        [index for index, _timestamp in selected],
        [timestamp.strftime("%b %d<br>%Y") for _index, timestamp in selected],
    )
