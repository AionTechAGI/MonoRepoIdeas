from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.core import (
    DEFAULT_BORROW_COST_PCT,
    DEFAULT_COMMISSION_PER_ORDER,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_SLIPPAGE_BPS,
    source_access_frame,
)
from src.backtest import (
    build_backtest_figures,
    build_backtest_report_html,
    metrics_dataframe,
    resolve_end_date,
    run_undervaluation_backtest,
)
from src.data_sources import (
    build_source_status_records,
    fetch_external_valuations,
    fetch_finviz_snapshot,
    fetch_risk_free_rate,
    fetch_sec_filings,
    fetch_sp100_constituents,
    fetch_sp500_constituents,
    fetch_stock_snapshot,
    lookup_sec_cik,
    screen_sp100,
)
from src.valuation import build_external_valuation_table, compute_house_valuation


st.set_page_config(
    page_title="Valuation Lab",
    page_icon=":bar_chart:",
    layout="wide",
)


def fmt_money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"${value:,.2f}"


def fmt_big(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000_000:
        return f"${value/1_000_000_000_000:,.2f}T"
    if abs_value >= 1_000_000_000:
        return f"${value/1_000_000_000:,.2f}B"
    if abs_value >= 1_000_000:
        return f"${value/1_000_000:,.2f}M"
    return f"${value:,.0f}"


def fmt_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.2f}%"


def load_uploaded_valuation_rows(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()
    if uploaded_file.name.lower().endswith(".csv"):
        frame = pd.read_csv(uploaded_file)
    else:
        frame = pd.read_excel(uploaded_file)
    rename_map = {
        "source": "Source",
        "exact_label": "Exact Label",
        "valuation_family": "Valuation Family",
        "value": "Value",
        "ratio": "Ratio",
        "upside_downside_pct": "Upside/Downside %",
        "method": "Method",
        "updated": "Updated",
        "url": "URL",
        "status": "Status",
        "note": "Note",
    }
    frame = frame.rename(columns={key: value for key, value in rename_map.items() if key in frame.columns})
    required = ["Source", "Exact Label", "Valuation Family", "Value"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    for optional in ["Ratio", "Upside/Downside %", "Method", "Updated", "URL", "Status", "Note"]:
        if optional not in frame.columns:
            frame[optional] = None
    return frame[
        ["Source", "Exact Label", "Valuation Family", "Value", "Ratio", "Upside/Downside %", "Method", "Updated", "Status", "Note", "URL"]
    ].copy()


@st.cache_data(ttl=3600, show_spinner=False)
def get_risk_free_rate(as_of_key: str) -> float:
    return fetch_risk_free_rate(datetime.fromisoformat(as_of_key))


@st.cache_data(ttl=1800, show_spinner=False)
def get_snapshot(ticker: str, as_of_key: str):
    return fetch_stock_snapshot(ticker, as_of_date=datetime.fromisoformat(as_of_key))


@st.cache_data(ttl=1800, show_spinner=False)
def get_external_rows(ticker: str, as_of_key: str):
    return fetch_external_valuations(ticker, as_of_date=datetime.fromisoformat(as_of_key))


@st.cache_data(ttl=1800, show_spinner=False)
def get_finviz_snapshot(ticker: str, as_of_key: str):
    return fetch_finviz_snapshot(ticker, as_of_date=datetime.fromisoformat(as_of_key))


@st.cache_data(ttl=1800, show_spinner=False)
def get_sec_filings(ticker: str, as_of_key: str):
    return fetch_sec_filings(ticker, as_of_date=datetime.fromisoformat(as_of_key))


@st.cache_data(ttl=3600, show_spinner=False)
def get_universe_table(universe_name: str) -> pd.DataFrame:
    if universe_name == "S&P 500":
        return fetch_sp500_constituents()
    return fetch_sp100_constituents()


@st.cache_data(ttl=3600, show_spinner=False)
def get_screen(universe_name: str, as_of_key: str) -> pd.DataFrame:
    universe = get_universe_table(universe_name)
    as_of_dt = datetime.fromisoformat(as_of_key)
    risk_free_rate = get_risk_free_rate(as_of_key)

    def _screen_one(item: dict[str, str]) -> dict:
        ticker = item["ticker"]
        snapshot = fetch_stock_snapshot(
            ticker,
            as_of_date=datetime.fromisoformat(as_of_key),
            company_name_hint=item.get("company_name"),
            sector_hint=item.get("sector"),
            skip_info=True,
        )
        valuation = compute_house_valuation(snapshot, risk_free_rate)
        return {
            "ticker": snapshot.ticker,
            "company_name": snapshot.company_name or item.get("company_name"),
            "sector": snapshot.sector or item.get("sector"),
            "current_price": snapshot.current_price,
            "fair_value": valuation.blended_fair_value,
            "fair_value_low": valuation.fair_value_low,
            "fair_value_high": valuation.fair_value_high,
            "dcf_value": valuation.dcf_fair_value,
            "earnings_value": valuation.earnings_fair_value,
            "undervaluation_pct": valuation.undervaluation_pct,
            "quality": valuation.quality_score,
            "confidence": valuation.confidence_score,
            "data_quality_score": valuation.data_quality_score,
            "stability_score": valuation.stability_score,
            "stage1_growth": valuation.stage1_growth,
            "discount_rate": valuation.discount_rate,
            "market_cap": snapshot.market_cap,
            "analysis_date": as_of_dt.date().isoformat(),
            "fundamentals_as_of": snapshot.fundamentals_as_of,
            "model_version": valuation.model_version,
            "status": "ok",
        }

    items = [
        {"ticker": row.Symbol, "company_name": row.Name, "sector": row.Sector}
        for row in universe.itertuples(index=False)
    ]
    return screen_sp100(items, _screen_one, max_workers=4 if universe_name == "S&P 500" else 3)


@st.cache_data(ttl=3600, show_spinner=False)
def get_backtest_result(
    universe_name: str,
    as_of_key: str,
    end_key: str,
    portfolio_size: int,
    initial_capital: float,
    strategy_mode: str,
    commission_per_order: float,
    slippage_bps: float,
    borrow_cost_pct: float,
    liquidate_at_end: bool,
):
    screen = get_screen(universe_name, as_of_key)
    return run_undervaluation_backtest(
        screen_df=screen,
        analysis_date=datetime.fromisoformat(as_of_key).date().isoformat(),
        end_date=datetime.fromisoformat(end_key).date().isoformat(),
        initial_capital=initial_capital,
        portfolio_size=portfolio_size,
        strategy_mode=strategy_mode,
        commission_per_order=commission_per_order,
        slippage_bps=slippage_bps,
        borrow_cost_pct=borrow_cost_pct,
        liquidate_at_end=liquidate_at_end,
    )


def resolve_analysis_date() -> date:
    today = datetime.now(UTC).date()
    mode = st.sidebar.radio(
        "Analysis date",
        ["Today", "1 year ago", "2 years ago", "Custom date"],
        index=0,
    )
    if mode == "Today":
        return today
    if mode == "1 year ago":
        return today - timedelta(days=365)
    if mode == "2 years ago":
        return today - timedelta(days=730)
    return st.sidebar.date_input(
        "Choose analysis date",
        value=today,
        min_value=today - timedelta(days=365 * 5),
        max_value=today,
    )


def render_header(analysis_date: date, as_of_key: str, universe_name: str) -> None:
    st.title("Valuation Lab")
    st.caption(
        "Single-stock valuation workbench plus point-in-time universe screening and forward backtesting. "
        "External source rows keep the source label intact; the screener uses one normalized house model for comparability."
    )
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Current UTC timestamp", datetime.now(UTC).strftime("%Y-%m-%d %H:%M"))
    with col2:
        st.metric("Risk-free rate proxy", fmt_pct(get_risk_free_rate(as_of_key) * 100.0))
    with col3:
        st.metric("Analysis as-of date", analysis_date.isoformat())
    with col4:
        st.metric("Universe", universe_name)


def render_single_stock(analysis_date: date, as_of_key: str) -> None:
    st.subheader("Single Stock Valuation")
    ticker = st.text_input("Ticker", value="MSFT").strip().upper()
    if not ticker:
        st.stop()

    with st.spinner(f"Loading {ticker} snapshot and valuation sources..."):
        snapshot = get_snapshot(ticker, as_of_key)
        valuation = compute_house_valuation(snapshot, get_risk_free_rate(as_of_key))
        external_rows = get_external_rows(ticker, as_of_key)
        finviz_snapshot = get_finviz_snapshot(ticker, as_of_key)
        sec_filings = get_sec_filings(ticker, as_of_key)
        source_statuses = build_source_status_records(snapshot, external_rows, finviz_snapshot, sec_filings)
        external_frame = build_external_valuation_table(external_rows)

    manual_frame = pd.DataFrame()
    with st.expander("Add licensed or manual valuation rows", expanded=False):
        st.caption(
            "Upload your own CSV or Excel extract from licensed tools such as Morningstar, GuruFocus, or FAST Graphs. "
            "Required columns: `Source`, `Exact Label`, `Valuation Family`, `Value`."
        )
        uploaded_file = st.file_uploader(
            "Manual valuation file",
            type=["csv", "xlsx"],
            key=f"manual_valuation_{ticker}_{analysis_date.isoformat()}",
        )
        if uploaded_file is not None:
            try:
                manual_frame = load_uploaded_valuation_rows(uploaded_file)
                st.dataframe(manual_frame, hide_index=True, use_container_width=True)
            except Exception as exc:
                st.error(f"Could not parse manual valuation file: {exc}")

    if not manual_frame.empty:
        external_frame = pd.concat([external_frame, manual_frame], ignore_index=True)

    top_cols = st.columns(6)
    top_cols[0].metric("Price", fmt_money(snapshot.current_price))
    top_cols[1].metric("Market cap", fmt_big(snapshot.market_cap))
    top_cols[2].metric("House fair value", fmt_money(valuation.blended_fair_value))
    range_label = (
        f"{fmt_money(valuation.fair_value_low)} - {fmt_money(valuation.fair_value_high)}"
        if valuation.fair_value_low is not None and valuation.fair_value_high is not None
        else "n/a"
    )
    top_cols[3].metric("Fair value range", range_label)
    top_cols[4].metric("Undervaluation", fmt_pct(valuation.undervaluation_pct))
    top_cols[5].metric("Data quality", f"{valuation.data_quality_score}/100")

    st.caption(
        f"As-of date: `{analysis_date.isoformat()}`. "
        + (
            f"Latest fundamentals used: `{snapshot.fundamentals_as_of}`."
            if snapshot.fundamentals_as_of
            else "Fundamentals date is not available."
        )
    )

    details_left, details_right = st.columns([1.05, 0.95])
    with details_left:
        st.markdown("**Company identity**")
        cik = lookup_sec_cik(snapshot.ticker)
        sec_company_url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&owner=exclude&count=40"
            if cik
            else None
        )
        identity_frame = pd.DataFrame(
            [
                ("Ticker", snapshot.ticker),
                ("Company", snapshot.company_name or "n/a"),
                ("Exchange", snapshot.exchange or "n/a"),
                ("CIK", cik or "n/a"),
                ("Sector", snapshot.sector or "n/a"),
                ("Industry", snapshot.industry or "n/a"),
                ("Website", snapshot.website or "n/a"),
                ("Yahoo", f"https://finance.yahoo.com/quote/{snapshot.ticker}"),
                ("Finviz", finviz_snapshot.page_url),
                ("SEC", sec_company_url or "n/a"),
            ],
            columns=["Field", "Value"],
        )
        st.dataframe(identity_frame, hide_index=True, use_container_width=True)

        st.markdown("**Company snapshot**")
        snapshot_frame = pd.DataFrame(
            [
                ("Company", snapshot.company_name or "n/a"),
                ("Sector", snapshot.sector or "n/a"),
                ("Currency", snapshot.currency or "n/a"),
                ("Shares outstanding", f"{snapshot.shares_outstanding:,.0f}" if snapshot.shares_outstanding else "n/a"),
                ("Net cash", fmt_big(snapshot.net_cash)),
                ("Price as of", analysis_date.isoformat()),
                ("Fundamentals as of", snapshot.fundamentals_as_of or "n/a"),
                ("Revenue growth", fmt_pct((snapshot.revenue_growth or 0.0) * 100.0) if snapshot.revenue_growth is not None else "n/a"),
                ("Earnings growth", fmt_pct((snapshot.earnings_growth or 0.0) * 100.0) if snapshot.earnings_growth is not None else "n/a"),
                ("Trailing EPS", fmt_money(snapshot.trailing_eps)),
                ("Forward EPS", fmt_money(snapshot.forward_eps)),
            ],
            columns=["Field", "Value"],
        )
        st.dataframe(snapshot_frame, hide_index=True, use_container_width=True)

        st.markdown("**House valuation assumptions**")
        assumptions = pd.DataFrame(
            [
                ("Model version", valuation.model_version),
                ("Normalized FCF", fmt_big(valuation.normalized_fcf)),
                ("Stage 1 growth", fmt_pct((valuation.stage1_growth or 0.0) * 100.0) if valuation.stage1_growth is not None else "n/a"),
                ("Stage 2 growth", fmt_pct((valuation.stage2_growth or 0.0) * 100.0) if valuation.stage2_growth is not None else "n/a"),
                ("Discount rate", fmt_pct((valuation.discount_rate or 0.0) * 100.0) if valuation.discount_rate is not None else "n/a"),
                ("Terminal growth", fmt_pct((valuation.terminal_growth or 0.0) * 100.0) if valuation.terminal_growth is not None else "n/a"),
                ("Fair P/E", f"{valuation.fair_pe:.1f}x" if valuation.fair_pe is not None else "n/a"),
                ("DCF anchor", fmt_money(valuation.dcf_fair_value)),
                ("Earnings anchor", fmt_money(valuation.earnings_fair_value)),
                ("Fair value low", fmt_money(valuation.fair_value_low)),
                ("Fair value high", fmt_money(valuation.fair_value_high)),
                ("Quality score", f"{valuation.quality_score:.2f}"),
                ("Confidence score", f"{valuation.confidence_score:.2f}"),
                ("Stability score", f"{valuation.stability_score:.2f}"),
                ("Data quality score", f"{valuation.data_quality_score}/100"),
            ],
            columns=["Assumption", "Value"],
        )
        st.dataframe(assumptions, hide_index=True, use_container_width=True)

        if valuation.notes:
            st.markdown("**Model notes**")
            for note in valuation.notes:
                st.write(f"- {note}")

        st.markdown("**Official filings**")
        if sec_filings:
            filings_frame = pd.DataFrame(
                [
                    {
                        "Form": filing.form,
                        "Filing date": filing.filing_date,
                        "Description": filing.description or filing.primary_document,
                        "Document URL": filing.filing_url,
                    }
                    for filing in sec_filings[:10]
                ]
            )
            st.dataframe(filings_frame, hide_index=True, use_container_width=True)
        else:
            st.caption("No SEC filings were returned for this ticker and selected as-of date.")

    with details_right:
        st.markdown("**Source status**")
        status_frame = pd.DataFrame(
            [
                {
                    "Source": item.source,
                    "Status": item.status,
                    "Access": item.access or "",
                    "Retrieved": item.retrieved_at,
                    "As-of": item.as_of_date,
                    "Note": item.note or "",
                    "URL": item.url or "",
                }
                for item in source_statuses
            ]
        )
        st.dataframe(status_frame, hide_index=True, use_container_width=True)

        st.markdown("**External valuation sources**")
        display_frame = external_frame.copy()
        for column in ["Value", "Ratio", "Upside/Downside %"]:
            display_frame[column] = pd.to_numeric(display_frame[column], errors="coerce")
        st.dataframe(display_frame, hide_index=True, use_container_width=True)

        st.markdown("**Finviz snapshot**")
        if finviz_snapshot.status != "visible":
            st.caption(finviz_snapshot.note or "Finviz data is not available for this mode.")
        else:
            finviz_primary = pd.DataFrame(
                [
                    ("Company", finviz_snapshot.company_name or "n/a"),
                    ("Last close", finviz_snapshot.last_close_label or "n/a"),
                    ("Price", fmt_money(finviz_snapshot.price)),
                    ("Sector", finviz_snapshot.sector or "n/a"),
                    ("Industry", finviz_snapshot.industry or "n/a"),
                    ("Exchange", finviz_snapshot.exchange or "n/a"),
                    ("Target Price", finviz_snapshot.metrics.get("Target Price", "n/a")),
                    ("Recom", finviz_snapshot.metrics.get("Recom", "n/a")),
                    ("P/E", finviz_snapshot.metrics.get("P/E", "n/a")),
                    ("Forward P/E", finviz_snapshot.metrics.get("Forward P/E", "n/a")),
                    ("PEG", finviz_snapshot.metrics.get("PEG", "n/a")),
                    ("P/FCF", finviz_snapshot.metrics.get("P/FCF", "n/a")),
                ],
                columns=["Field", "Value"],
            )
            finviz_secondary = pd.DataFrame(
                [
                    ("Perf Week", finviz_snapshot.metrics.get("Perf Week", "n/a")),
                    ("Perf Month", finviz_snapshot.metrics.get("Perf Month", "n/a")),
                    ("Perf Quarter", finviz_snapshot.metrics.get("Perf Quarter", "n/a")),
                    ("Perf YTD", finviz_snapshot.metrics.get("Perf YTD", "n/a")),
                    ("SMA20", finviz_snapshot.metrics.get("SMA20", "n/a")),
                    ("SMA50", finviz_snapshot.metrics.get("SMA50", "n/a")),
                    ("SMA200", finviz_snapshot.metrics.get("SMA200", "n/a")),
                    ("RSI (14)", finviz_snapshot.metrics.get("RSI (14)", "n/a")),
                    ("Rel Volume", finviz_snapshot.metrics.get("Rel Volume", "n/a")),
                    ("Beta", finviz_snapshot.metrics.get("Beta", "n/a")),
                    ("Avg Volume", finviz_snapshot.metrics.get("Avg Volume", "n/a")),
                    ("Short Ratio", finviz_snapshot.metrics.get("Short Ratio", "n/a")),
                ],
                columns=["Field", "Value"],
            )
            st.dataframe(finviz_primary, hide_index=True, use_container_width=True)
            st.dataframe(finviz_secondary, hide_index=True, use_container_width=True)
            st.caption(f"Source: [Finviz]({finviz_snapshot.page_url})")

    if not snapshot.price_history.empty and snapshot.current_price and valuation.blended_fair_value:
        history = snapshot.price_history.copy().reset_index()
        history["Close"] = history["Close"].astype(float)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=history["Date"],
                y=history["Close"],
                mode="lines",
                name="Price",
                line={"color": "#1f77b4", "width": 2.5},
            )
        )
        fig.add_hline(
            y=valuation.blended_fair_value,
            line_dash="dash",
            line_color="#d62728",
            annotation_text="House fair value",
            annotation_position="top left",
        )
        if valuation.fair_value_low is not None and valuation.fair_value_high is not None:
            fig.add_hrect(
                y0=valuation.fair_value_low,
                y1=valuation.fair_value_high,
                fillcolor="rgba(220, 38, 38, 0.08)",
                line_width=0,
                annotation_text="Fair value range",
                annotation_position="top right",
            )
        fig.add_hline(
            y=snapshot.current_price,
            line_dash="dot",
            line_color="#111111",
            annotation_text="As-of price",
            annotation_position="bottom left",
        )
        fig.add_vline(
            x=history["Date"].iloc[-1],
            line_dash="dot",
            line_color="#6b7280",
        )
        fig.update_layout(
            height=420,
            margin={"l": 40, "r": 20, "t": 20, "b": 40},
            xaxis_title="Date",
            yaxis_title=f"Price ({snapshot.currency or 'USD'})",
            legend={"orientation": "h", "y": 1.02, "x": 0},
        )
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.markdown("**Price history**")
            st.plotly_chart(fig, use_container_width=True)
        with chart_right:
            st.markdown("**Finviz chart**")
            if finviz_snapshot.status == "visible":
                st.image(finviz_snapshot.chart_url, use_container_width=True)
                st.caption("Daily chart from Finviz.")
            else:
                st.caption(finviz_snapshot.note or "Finviz chart is not available for this mode.")


def render_sp100_screen(analysis_date: date, as_of_key: str, universe_name: str) -> None:
    st.subheader(f"{universe_name} Undervaluation Screener")
    st.caption(
        "This screen uses one internal blended valuation model across the full universe. "
        "That makes the undervaluation percentages comparable across names, but they are not third-party fair values."
    )
    st.caption(
        f"As-of date: `{analysis_date.isoformat()}`. "
        "Historical mode uses price on that date and the latest annual statements available on or before that date."
    )
    with st.spinner(f"Running {universe_name} valuation screen..."):
        frame = get_screen(universe_name, as_of_key)

    clean = frame[frame["status"] == "ok"].copy()
    if clean.empty:
        st.error("No screen results were produced.")
        return

    top_cols = st.columns(4)
    top_cols[0].metric("Names screened", f"{len(clean):,}")
    top_cols[1].metric("Median undervaluation", fmt_pct(clean["undervaluation_pct"].median()))
    top_cols[2].metric("Positive undervaluation count", f"{(clean['undervaluation_pct'] > 0).sum():,}")
    top_cols[3].metric("Median data quality", f"{int(clean['data_quality_score'].median())}/100")

    filters = st.columns(4)
    min_upside = filters[0].slider("Minimum undervaluation %", min_value=-80, max_value=100, value=0, step=5)
    min_confidence = filters[1].slider("Minimum confidence", min_value=0.0, max_value=1.0, value=0.4, step=0.05)
    sector_options = ["All"] + sorted(x for x in clean["sector"].dropna().unique())
    selected_sector = filters[2].selectbox("Sector", sector_options)
    min_data_quality = filters[3].slider("Minimum data quality", min_value=0, max_value=100, value=60, step=5)

    filtered = clean[
        (clean["undervaluation_pct"] >= min_upside)
        & (clean["confidence"] >= min_confidence)
        & (clean["data_quality_score"] >= min_data_quality)
    ].copy()
    if selected_sector != "All":
        filtered = filtered[filtered["sector"] == selected_sector]

    show_columns = [
        "ticker",
        "company_name",
        "sector",
        "current_price",
        "fair_value",
        "fair_value_low",
        "fair_value_high",
        "undervaluation_pct",
        "dcf_value",
        "earnings_value",
        "quality",
        "confidence",
        "data_quality_score",
        "stability_score",
        "discount_rate",
        "fundamentals_as_of",
        "market_cap",
        "model_version",
    ]
    st.dataframe(filtered[show_columns], hide_index=True, use_container_width=True)

    csv_bytes = filtered[show_columns].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download screened results as CSV",
        data=csv_bytes,
        file_name=f"{universe_name.lower().replace(' ', '_')}_undervaluation_screen_{analysis_date.isoformat()}.csv",
        mime="text/csv",
    )

    left, right = st.columns(2)
    with left:
        scatter = px.scatter(
            filtered,
            x="confidence",
            y="undervaluation_pct",
            color="sector",
            hover_name="ticker",
            hover_data={"company_name": True, "fair_value": ":.2f", "current_price": ":.2f"},
            title="Undervaluation vs confidence",
        )
        scatter.update_layout(height=420, margin={"l": 40, "r": 20, "t": 40, "b": 40})
        st.plotly_chart(scatter, use_container_width=True)

    with right:
        top10 = filtered.sort_values("undervaluation_pct", ascending=False).head(10)
        bars = px.bar(
            top10,
            x="ticker",
            y="undervaluation_pct",
            color="sector",
            hover_data={"fair_value": ":.2f", "current_price": ":.2f"},
            title="Top 10 by undervaluation",
        )
        bars.update_layout(height=420, margin={"l": 40, "r": 20, "t": 40, "b": 40}, yaxis_title="%")
        st.plotly_chart(bars, use_container_width=True)


def render_portfolio_backtest(analysis_date: date, as_of_key: str, universe_name: str) -> None:
    st.subheader("Undervaluation Portfolio Backtest")
    st.caption(
        "Build a portfolio from the point-in-time screen on the selected analysis date, "
        "then test it forward for one year, multiple years, or through today."
    )
    st.caption(
        f"Current limitation: the universe is the current {universe_name} membership. "
        "Prices and fundamentals are point-in-time, but index membership is not historically reconstituted."
    )
    st.caption(
        "This version supports entry/exit commission, slippage, and borrow-cost assumptions. "
        "Historical index membership is still approximate unless you provide your own historical universe offline."
    )

    controls = st.columns(5)
    strategy_mode_ui = controls[0].selectbox(
        "Strategy",
        ["Long undervalued", "Short overvalued", "Long / Short"],
        index=0,
    )
    horizon_mode = controls[1].selectbox(
        "Backtest horizon",
        ["1 year", "2 years", "3 years", "To today", "Custom end date"],
        index=3,
    )
    custom_end = None
    if horizon_mode == "Custom end date":
        custom_end = controls[2].date_input(
            "End date",
            value=min(datetime.now(UTC).date(), analysis_date + timedelta(days=365)),
            min_value=analysis_date,
            max_value=datetime.now(UTC).date(),
        )
    leg_label = "Names per side" if strategy_mode_ui == "Long / Short" else "Portfolio size"
    portfolio_size = controls[2 if horizon_mode != "Custom end date" else 3].slider(
        leg_label,
        min_value=5,
        max_value=30,
        value=20,
        step=1,
    )
    initial_capital = controls[4].number_input(
        "Initial capital, USD",
        min_value=1000,
        max_value=1000000,
        value=int(DEFAULT_INITIAL_CAPITAL),
        step=1000,
    )
    cost_controls = st.columns(4)
    commission_per_order = cost_controls[0].number_input(
        "Commission per order, USD",
        min_value=0.0,
        max_value=50.0,
        value=float(DEFAULT_COMMISSION_PER_ORDER),
        step=0.5,
    )
    slippage_bps = cost_controls[1].number_input(
        "Slippage, bps",
        min_value=0.0,
        max_value=100.0,
        value=float(DEFAULT_SLIPPAGE_BPS),
        step=1.0,
    )
    borrow_cost_pct = cost_controls[2].number_input(
        "Borrow cost, % annual",
        min_value=0.0,
        max_value=50.0,
        value=float(DEFAULT_BORROW_COST_PCT),
        step=0.5,
        disabled=strategy_mode_ui == "Long undervalued",
    )
    liquidate_at_end = cost_controls[3].checkbox("Liquidate at end", value=True)

    resolved_end = resolve_end_date(analysis_date, horizon_mode, custom_end)
    if resolved_end <= analysis_date:
        st.error("End date must be later than the analysis date.")
        return
    end_key = datetime.combine(resolved_end, datetime.min.time(), tzinfo=UTC).isoformat()
    strategy_mode = {
        "Long undervalued": "long_only",
        "Short overvalued": "short_only",
        "Long / Short": "long_short",
    }[strategy_mode_ui]

    with st.spinner("Running point-in-time portfolio backtest..."):
        outcome = get_backtest_result(
            universe_name,
            as_of_key,
            end_key,
            portfolio_size,
            float(initial_capital),
            strategy_mode,
            float(commission_per_order),
            float(slippage_bps),
            float(borrow_cost_pct if strategy_mode_ui != "Long undervalued" else 0.0),
            bool(liquidate_at_end),
        )

    metrics_df = metrics_dataframe(outcome)
    portfolio_metrics = outcome.results[outcome.portfolio_label].metrics
    qqq_metrics = outcome.results["QQQ"].metrics
    spy_metrics = outcome.results["SPY"].metrics

    top_cols = st.columns(4)
    top_cols[0].metric("Portfolio return", fmt_pct(portfolio_metrics["total_return_pct"]))
    top_cols[1].metric("Vs QQQ", fmt_pct(portfolio_metrics["total_return_pct"] - qqq_metrics["total_return_pct"]))
    top_cols[2].metric("Vs SPY", fmt_pct(portfolio_metrics["total_return_pct"] - spy_metrics["total_return_pct"]))
    top_cols[3].metric("Max drawdown", fmt_pct(portfolio_metrics["max_drawdown_pct"]))
    st.caption(
        f"Assumptions: commission/order `${outcome.assumptions.commission_per_order:.2f}`, "
        f"slippage `{outcome.assumptions.slippage_bps:.2f}` bps, "
        f"borrow cost `{outcome.assumptions.borrow_cost_pct:.2f}%`, "
        f"liquidate at end `{outcome.assumptions.liquidate_at_end}`."
    )

    st.caption(
        f"Screen date: `{outcome.analysis_date}` | Execution date: `{outcome.execution_date}` | "
        f"Requested end date: `{outcome.requested_end_date}` | Actual end date: `{outcome.actual_end_date}`"
    )

    st.dataframe(metrics_df, hide_index=True, use_container_width=True)

    equity_fig, drawdown_fig, contrib_fig, sector_fig = build_backtest_figures(outcome)
    top_chart, right_chart = st.columns([1.25, 0.75])
    with top_chart:
        st.plotly_chart(equity_fig, use_container_width=True)
    with right_chart:
        st.plotly_chart(drawdown_fig, use_container_width=True)
    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.plotly_chart(contrib_fig, use_container_width=True)
    with chart_right:
        st.plotly_chart(sector_fig, use_container_width=True)

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
    st.markdown("**Launch holdings**")
    st.dataframe(holdings_display, hide_index=True, use_container_width=True)

    csv_bytes = holdings_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download holdings and contributions CSV",
        data=csv_bytes,
        file_name=f"undervaluation_backtest_holdings_{outcome.analysis_date}_to_{outcome.actual_end_date}.csv",
        mime="text/csv",
    )

    html_report = build_backtest_report_html(outcome)
    st.download_button(
        "Download HTML report",
        data=html_report.encode("utf-8"),
        file_name=f"undervaluation_backtest_{outcome.analysis_date}_to_{outcome.actual_end_date}.html",
        mime="text/html",
    )


def render_methodology() -> None:
    st.subheader("Methodology")
    st.caption(
        "Project docs: "
        "`docs/methods.md`, `docs/limitations.md`, `docs/data_sources.md`."
    )
    st.markdown(
        """
        - `External valuation rows` keep the original source label and do not merge unlike models into one number.
        - `House fair value` blends two internal anchors:
          - a two-stage DCF on normalized free cash flow,
          - a forward earnings valuation based on growth, quality, and risk.
        - `Universe Screener` uses the same internal model for every stock, so the ranking is comparable across the chosen universe.
        - `House fair value` now includes a range, a data-quality score, and a stability score to reduce extreme outliers.
        - `Undervaluation Portfolio Backtest` supports long-only undervalued, short-only overvalued, and long/short tests with optional entry/exit commission, slippage, and borrow-cost assumptions, then compares the result with `QQQ` and `SPY`.
        - `Morningstar`, `GuruFocus`, and `FAST Graphs` are not faked. They are shown with explicit access conditions such as `requires_license`, `requires_api_key`, or `requires_subscription`.
        - Historical analysis uses point-in-time prices and the latest annual fundamentals available on or before the chosen analysis date.
        - Historical universe membership is not reconstituted; the app currently uses the current S&P 100 or S&P 500 list as the research universe for all dates.
        - Sector and industry guardrails plus anchor-consensus shrinkage are applied to reduce unrealistic fair value outliers, especially in financials, telecom, utilities, energy, and some high-multiple technology names.
        - This is a research tool, not personalized investment advice.
        """
    )


def render_source_access() -> None:
    st.subheader("Source Access and Data Health")
    st.caption(
        "This page explains which sources the app can use directly, which ones require an API key or license, and the legal path for adding more data without scraping around restrictions."
    )
    frame = source_access_frame()
    st.dataframe(frame, hide_index=True, use_container_width=True)
    st.markdown(
        """
        **Practical rules**

        - `Morningstar`: use public methodology pages, licensed Morningstar products, or your own exported values from a licensed session.
        - `GuruFocus`: use the official Data API or your own account export. Browser rendering and app scraping are not the same thing.
        - `FAST Graphs`: use an active subscription or trial and import your own exported values instead of scraping authenticated pages.
        - `SEC EDGAR`: use the public APIs and filing pages with a declared user agent and fair-access limits.
        - `SimFin`, `Alpha Vantage`, `Financial Modeling Prep`: good legal expansion paths for fundamentals and model inputs once you enable your own keys or account access.
        """
    )


def main() -> None:
    analysis_date = resolve_analysis_date()
    as_of_key = datetime.combine(analysis_date, datetime.min.time(), tzinfo=UTC).isoformat()
    universe_name = st.sidebar.selectbox("Universe", ["S&P 500", "S&P 100"], index=0)
    render_header(analysis_date, as_of_key, universe_name)
    page = st.sidebar.radio(
        "View",
        ["Single Stock Valuation", "Universe Screener", "Undervaluation Portfolio Backtest", "Source Access", "Methodology"],
    )
    if page == "Single Stock Valuation":
        render_single_stock(analysis_date, as_of_key)
    elif page == "Universe Screener":
        render_sp100_screen(analysis_date, as_of_key, universe_name)
    elif page == "Undervaluation Portfolio Backtest":
        render_portfolio_backtest(analysis_date, as_of_key, universe_name)
    elif page == "Source Access":
        render_source_access()
    else:
        render_methodology()


if __name__ == "__main__":
    main()
