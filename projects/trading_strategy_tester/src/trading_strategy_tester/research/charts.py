"""Fast HTML chart generation for cached market data."""

from __future__ import annotations

from datetime import datetime
from html import escape
import json
import math
from pathlib import Path

from trading_strategy_tester.data.historical_loader import HistoricalBar
from trading_strategy_tester.data.range_downloader import parse_ibkr_bar_timestamp


LIGHTWEIGHT_CHARTS_CDN = (
    "https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"
)


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
    chart_data = [
        {
            "time": index,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M"),
            "open": round(bar.open, 4),
            "high": round(bar.high, 4),
            "low": round(bar.low, 4),
            "close": round(bar.close, 4),
            "volume": bar.volume or 0,
        }
        for index, (timestamp, bar) in enumerate(zip(timestamps, bars))
    ]
    tick_values, tick_text = market_time_ticks(timestamps)
    tick_map = {str(value): text.replace("<br>", " ") for value, text in zip(tick_values, tick_text)}

    html = _render_lightweight_chart_html(
        title=title,
        data=chart_data,
        tick_map=tick_map,
        first_timestamp=timestamps[0].strftime("%Y-%m-%d %H:%M"),
        last_timestamp=timestamps[-1].strftime("%Y-%m-%d %H:%M"),
    )
    output.write_text(html, encoding="utf-8", newline="\n")
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


def _render_lightweight_chart_html(
    title: str,
    data: list[dict[str, object]],
    tick_map: dict[str, str],
    first_timestamp: str,
    last_timestamp: str,
) -> str:
    data_json = json.dumps(data, separators=(",", ":"))
    tick_map_json = json.dumps(tick_map, separators=(",", ":"))
    escaped_title = escape(title)
    escaped_first = escape(first_timestamp)
    escaped_last = escape(last_timestamp)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <script src="{LIGHTWEIGHT_CHARTS_CDN}"></script>
  <style>
    :root {{
      --text: #17233c;
      --muted: #5f6f89;
      --grid: #e8edf5;
      --up: #1f8f5f;
      --down: #d64b3a;
      --volume: rgba(76, 120, 168, 0.28);
      --bg: #ffffff;
    }}
    html, body {{
      height: 100%;
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, Segoe UI, Arial, sans-serif;
    }}
    body {{
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }}
    header {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 18px 8px;
      border-bottom: 1px solid var(--grid);
    }}
    h1 {{
      margin: 0;
      font-size: 17px;
      font-weight: 650;
      letter-spacing: 0;
    }}
    .meta {{
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}
    #chart {{
      position: relative;
      flex: 1 1 auto;
      min-height: 620px;
    }}
    #tooltip {{
      position: absolute;
      display: none;
      pointer-events: none;
      z-index: 10;
      min-width: 190px;
      padding: 8px 10px;
      border: 1px solid #cdd7e5;
      border-radius: 6px;
      background: rgba(255,255,255,0.96);
      box-shadow: 0 8px 22px rgba(20, 35, 65, 0.14);
      font-size: 12px;
      line-height: 1.45;
      color: var(--text);
    }}
    #tooltip .time {{
      font-weight: 650;
      margin-bottom: 4px;
    }}
    #tooltip .row {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
    }}
    .warning {{
      padding: 6px 18px 10px;
      color: var(--muted);
      font-size: 12px;
      border-top: 1px solid var(--grid);
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escaped_title}</h1>
    <div class="meta">Compressed market time | {len(data):,} bars | {escaped_first} -> {escaped_last}</div>
  </header>
  <main id="chart">
    <div id="tooltip"></div>
  </main>
  <div class="warning">Rendered with canvas using compressed market time. Closed-market gaps are removed; hover shows exact bar timestamps.</div>
  <script>
    const rawData = {data_json};
    const tickMap = {tick_map_json};
    const timestampByTime = new Map(rawData.map((bar) => [bar.time, bar.timestamp]));
    const container = document.getElementById('chart');
    const tooltip = document.getElementById('tooltip');

    const chart = LightweightCharts.createChart(container, {{
      autoSize: true,
      localization: {{
        timeFormatter: (time) => timestampByTime.get(time) || String(time),
      }},
      layout: {{
        background: {{ type: 'solid', color: '#ffffff' }},
        textColor: '#17233c',
        fontFamily: 'Inter, Segoe UI, Arial, sans-serif',
      }},
      grid: {{
        vertLines: {{ color: '#e8edf5' }},
        horzLines: {{ color: '#e8edf5' }},
      }},
      rightPriceScale: {{
        borderVisible: false,
        scaleMargins: {{ top: 0.08, bottom: 0.28 }},
      }},
      timeScale: {{
        borderVisible: false,
        timeVisible: false,
        secondsVisible: false,
        tickMarkFormatter: (time) => tickMap[String(time)] || '',
      }},
      crosshair: {{
        mode: LightweightCharts.CrosshairMode.Normal,
      }},
      handleScale: {{
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      }},
      handleScroll: {{
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      }},
    }});

    const candles = rawData.map((bar) => ({{
      time: bar.time,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }}));
    const volumes = rawData.map((bar) => ({{
      time: bar.time,
      value: bar.volume,
      color: bar.close >= bar.open ? 'rgba(31, 143, 95, 0.28)' : 'rgba(214, 75, 58, 0.28)',
    }}));

    const candleSeries = chart.addCandlestickSeries({{
      upColor: '#1f8f5f',
      downColor: '#d64b3a',
      borderUpColor: '#1f8f5f',
      borderDownColor: '#d64b3a',
      wickUpColor: '#1f8f5f',
      wickDownColor: '#d64b3a',
    }});
    candleSeries.setData(candles);

    const volumeSeries = chart.addHistogramSeries({{
      priceFormat: {{ type: 'volume' }},
      priceScaleId: '',
    }});
    volumeSeries.priceScale().applyOptions({{
      scaleMargins: {{ top: 0.82, bottom: 0 }},
    }});
    volumeSeries.setData(volumes);

    const dataByTime = new Map(rawData.map((bar) => [bar.time, bar]));

    chart.subscribeCrosshairMove((param) => {{
      if (!param || param.time === undefined || !param.point || param.point.x < 0 || param.point.y < 0) {{
        tooltip.style.display = 'none';
        return;
      }}
      const bar = dataByTime.get(param.time);
      if (!bar) {{
        tooltip.style.display = 'none';
        return;
      }}
      tooltip.style.display = 'block';
      tooltip.innerHTML = `
        <div class="time">${{bar.timestamp}}</div>
        <div class="row"><span>Open</span><b>${{bar.open.toFixed(2)}}</b></div>
        <div class="row"><span>High</span><b>${{bar.high.toFixed(2)}}</b></div>
        <div class="row"><span>Low</span><b>${{bar.low.toFixed(2)}}</b></div>
        <div class="row"><span>Close</span><b>${{bar.close.toFixed(2)}}</b></div>
        <div class="row"><span>Volume</span><b>${{Math.round(bar.volume).toLocaleString()}}</b></div>
      `;
      const left = Math.min(param.point.x + 16, container.clientWidth - 230);
      const top = Math.max(8, Math.min(param.point.y + 16, container.clientHeight - 150));
      tooltip.style.left = `${{left}}px`;
      tooltip.style.top = `${{top}}px`;
    }});

    chart.timeScale().fitContent();
  </script>
</body>
</html>
"""
