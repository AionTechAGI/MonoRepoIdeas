from __future__ import annotations

import io
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from yfinance.exceptions import YFRateLimitError

from src.core import get_source_rule


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HTTP_TIMEOUT = 20
SP100_WIKI_URL = "https://en.wikipedia.org/wiki/S%26P_100"
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_USER_AGENT = "ValuationLab/1.0 valuation-lab@example.com"


@dataclass
class ExternalValuation:
    source: str
    exact_label: str
    valuation_family: str
    value: float | None
    ratio: float | None
    upside_downside_pct: float | None
    method: str
    updated: str | None
    url: str
    status: str = "visible"
    note: str | None = None


@dataclass
class FinvizSnapshot:
    ticker: str
    company_name: str | None
    last_close_label: str | None
    price: float | None
    sector: str | None
    industry: str | None
    country: str | None
    exchange: str | None
    metrics: dict[str, str]
    chart_url: str
    page_url: str
    status: str = "visible"
    note: str | None = None


@dataclass
class SecFiling:
    ticker: str
    cik: str
    form: str
    filing_date: str
    accession_number: str
    primary_document: str
    description: str | None
    filing_url: str
    interactive_url: str


@dataclass
class SourceStatusRecord:
    source: str
    status: str
    retrieved_at: str
    as_of_date: str | None
    access: str | None
    note: str | None
    url: str | None


@dataclass
class StockSnapshot:
    ticker: str
    company_name: str | None
    sector: str | None
    industry: str | None
    exchange: str | None
    website: str | None
    currency: str | None
    current_price: float | None
    market_cap: float | None
    shares_outstanding: float | None
    book_value_per_share: float | None
    beta: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    trailing_eps: float | None
    forward_eps: float | None
    total_cash: float | None
    total_debt: float | None
    profit_margin: float | None
    operating_margin: float | None
    return_on_equity: float | None
    annual_free_cash_flow: list[float]
    annual_revenue: list[float]
    annual_net_income: list[float]
    annual_dates: list[str]
    price_history: pd.DataFrame
    as_of: datetime
    fundamentals_as_of: str | None
    is_historical: bool

    @property
    def net_cash(self) -> float | None:
        if self.total_cash is None and self.total_debt is None:
            return None
        return float(self.total_cash or 0.0) - float(self.total_debt or 0.0)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _sec_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json,text/html,*/*",
        }
    )
    return session


def _classify_fetch_error(exc: Exception) -> tuple[str, str]:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()
    if isinstance(exc, YFRateLimitError) or "too many requests" in lowered or "rate limit" in lowered:
        return "rate_limited", message
    if "unauthorized" in lowered or "forbidden" in lowered:
        return "failed", message
    return "failed", message


def _safe_info(stock: yf.Ticker, skip_info: bool = False) -> tuple[dict[str, Any], str | None]:
    if skip_info:
        return {}, None
    try:
        payload = stock.info
        return payload if isinstance(payload, dict) else {}, None
    except Exception as exc:
        _, message = _classify_fetch_error(exc)
        return {}, message


def _clean_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, np.number)):
        if pd.isna(value):
            return None
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "n/a", "not visible"}:
        return None
    text = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def _series_to_list(frame: pd.DataFrame | pd.Series | None, row_name: str) -> list[float]:
    if frame is None or frame.empty:
        return []
    if isinstance(frame, pd.Series):
        values = frame.dropna().astype(float).tolist()
        return values
    if row_name not in frame.index:
        return []
    row = frame.loc[row_name]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    return [float(v) for v in row.dropna().tolist()]


def _frame_dates(frame: pd.DataFrame | None) -> list[str]:
    if frame is None or frame.empty:
        return []
    dates: list[str] = []
    for col in frame.columns:
        try:
            dates.append(pd.Timestamp(col).strftime("%Y-%m-%d"))
        except Exception:
            dates.append(str(col))
    return dates


def _normalize_as_of_date(as_of_date: date | datetime | None) -> datetime:
    if as_of_date is None:
        return datetime.now(UTC)
    if isinstance(as_of_date, datetime):
        if as_of_date.tzinfo is None:
            return as_of_date.replace(tzinfo=UTC)
        return as_of_date.astimezone(UTC)
    return datetime.combine(as_of_date, datetime.min.time(), tzinfo=UTC)


def _statement_as_of(frame: pd.DataFrame | None, as_of_dt: datetime) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep_columns = []
    for col in frame.columns:
        try:
            col_ts = pd.Timestamp(col)
        except Exception:
            continue
        if col_ts.tzinfo is None:
            col_ts = col_ts.tz_localize(UTC)
        else:
            col_ts = col_ts.tz_convert(UTC)
        if col_ts <= pd.Timestamp(as_of_dt):
            keep_columns.append(col)
    if not keep_columns:
        return pd.DataFrame(index=frame.index)
    return frame.loc[:, keep_columns]


def _safe_statement(stock: yf.Ticker, attribute: str) -> pd.DataFrame:
    try:
        frame = getattr(stock, attribute)
        if isinstance(frame, pd.DataFrame):
            return frame
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def _statement_value(frame: pd.DataFrame | None, row_names: list[str]) -> float | None:
    if frame is None or frame.empty:
        return None
    for row_name in row_names:
        if row_name in frame.index:
            row = frame.loc[row_name]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            non_na = row.dropna()
            if non_na.empty:
                continue
            return float(non_na.iloc[0])
    return None


def _history_as_of(stock: yf.Ticker, as_of_dt: datetime, years: int = 5) -> pd.DataFrame:
    end = (pd.Timestamp(as_of_dt) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    start = (pd.Timestamp(as_of_dt) - pd.Timedelta(days=365 * years + 30)).strftime("%Y-%m-%d")
    history = stock.history(start=start, end=end, auto_adjust=False)
    if history.empty:
        history = stock.history(period=f"{years}y", auto_adjust=False)
    return history


def fetch_sp100_constituents() -> pd.DataFrame:
    response = _session().get(SP100_WIKI_URL, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    for table in tables:
        columns = [str(col) for col in table.columns]
        if "Symbol" in columns and "Sector" in columns:
            output = table[["Symbol", "Name", "Sector"]].copy()
            output["Symbol"] = output["Symbol"].str.replace(".", "-", regex=False)
            output = output.dropna(subset=["Symbol"])
            return output.reset_index(drop=True)
    raise ValueError("Could not parse S&P 100 constituents from Wikipedia.")


def fetch_sp500_constituents() -> pd.DataFrame:
    response = _session().get(SP500_WIKI_URL, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    for table in tables:
        columns = [str(col) for col in table.columns]
        if "Symbol" in columns and "Security" in columns:
            output = table[["Symbol", "Security", "GICS Sector"]].copy()
            output.columns = ["Symbol", "Name", "Sector"]
            output["Symbol"] = output["Symbol"].str.replace(".", "-", regex=False)
            output = output.dropna(subset=["Symbol"])
            return output.reset_index(drop=True)
    raise ValueError("Could not parse S&P 500 constituents from Wikipedia.")


def fetch_risk_free_rate(as_of_date: date | datetime | None = None) -> float:
    treasury = yf.Ticker("^TNX")
    as_of_dt = _normalize_as_of_date(as_of_date)
    end = (pd.Timestamp(as_of_dt) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    start = (pd.Timestamp(as_of_dt) - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
    history = treasury.history(start=start, end=end, auto_adjust=False)
    if history.empty:
        history = treasury.history(period="1mo", auto_adjust=False)
    if history.empty:
        return 0.043
    latest = float(history["Close"].dropna().iloc[-1]) / 100.0
    return latest


def fetch_stock_snapshot(
    ticker: str,
    history_period: str = "5y",
    as_of_date: date | datetime | None = None,
    company_name_hint: str | None = None,
    sector_hint: str | None = None,
    skip_info: bool = False,
) -> StockSnapshot:
    normalized = ticker.strip().upper()
    as_of_dt = _normalize_as_of_date(as_of_date)
    stock = yf.Ticker(normalized)
    info, _ = _safe_info(stock, skip_info=skip_info)
    history = _history_as_of(stock, as_of_dt, years=5 if history_period == "5y" else 3)
    if not history.empty:
        price_series = history["Close"].dropna()
        current_price = float(price_series.iloc[-1]) if not price_series.empty else None
    else:
        current_price = _clean_numeric(info.get("currentPrice"))

    income_stmt_raw = _safe_statement(stock, "income_stmt")
    cashflow_raw = _safe_statement(stock, "cashflow")
    balance_sheet_raw = _safe_statement(stock, "balance_sheet")

    income_stmt = _statement_as_of(income_stmt_raw, as_of_dt)
    cashflow = _statement_as_of(cashflow_raw, as_of_dt)
    balance_sheet = _statement_as_of(balance_sheet_raw, as_of_dt)

    annual_fcf = _series_to_list(cashflow, "Free Cash Flow")
    annual_revenue = _series_to_list(income_stmt, "Total Revenue")
    annual_net_income = _series_to_list(
        income_stmt,
        "Net Income From Continuing Operation Net Minority Interest",
    )
    annual_dates = _frame_dates(income_stmt) or _frame_dates(cashflow)

    shares_outstanding = _statement_value(income_stmt, ["Diluted Average Shares", "Basic Average Shares"])
    if shares_outstanding is None:
        shares_outstanding = _clean_numeric(info.get("sharesOutstanding"))

    trailing_eps = _statement_value(income_stmt, ["Diluted EPS", "Basic EPS"])
    if trailing_eps is None:
        trailing_eps = _clean_numeric(info.get("trailingEps"))

    total_cash = _statement_value(
        balance_sheet,
        ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"],
    )
    if total_cash is None:
        total_cash = _clean_numeric(info.get("totalCash"))

    total_debt = _statement_value(balance_sheet, ["Total Debt", "Net Debt"])
    if total_debt is None:
        total_debt = _clean_numeric(info.get("totalDebt"))

    latest_revenue = _statement_value(income_stmt, ["Total Revenue"])
    latest_net_income = _statement_value(
        income_stmt,
        ["Net Income From Continuing Operation Net Minority Interest", "Net Income Common Stockholders"],
    )
    latest_operating_income = _statement_value(income_stmt, ["Operating Income", "EBIT", "Total Operating Income As Reported"])
    total_equity = _statement_value(balance_sheet, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"])

    profit_margin = None
    operating_margin = None
    return_on_equity = None
    if latest_revenue and latest_net_income is not None:
        profit_margin = latest_net_income / latest_revenue
    if latest_revenue and latest_operating_income is not None:
        operating_margin = latest_operating_income / latest_revenue
    if total_equity and latest_net_income is not None and total_equity != 0:
        return_on_equity = latest_net_income / total_equity

    market_cap = None
    if current_price is not None and shares_outstanding is not None:
        market_cap = current_price * shares_outstanding
    book_value_per_share = None
    if total_equity is not None and shares_outstanding and shares_outstanding != 0:
        book_value_per_share = total_equity / shares_outstanding

    fundamentals_as_of = annual_dates[0] if annual_dates else None
    today_utc = datetime.now(UTC).date()
    is_historical = as_of_dt.date() < today_utc

    return StockSnapshot(
        ticker=normalized,
        company_name=info.get("longName") or info.get("shortName") or company_name_hint,
        sector=info.get("sector") or sector_hint,
        industry=info.get("industry"),
        exchange=info.get("exchange"),
        website=info.get("website"),
        currency=info.get("currency"),
        current_price=current_price,
        market_cap=market_cap if market_cap is not None else _clean_numeric(info.get("marketCap")),
        shares_outstanding=shares_outstanding,
        book_value_per_share=book_value_per_share,
        beta=_clean_numeric(info.get("beta")),
        revenue_growth=None if is_historical else _clean_numeric(info.get("revenueGrowth")),
        earnings_growth=None if is_historical else _clean_numeric(info.get("earningsGrowth")),
        trailing_eps=trailing_eps,
        forward_eps=None if is_historical else _clean_numeric(info.get("forwardEps")),
        total_cash=total_cash,
        total_debt=total_debt,
        profit_margin=profit_margin if profit_margin is not None else _clean_numeric(info.get("profitMargins")),
        operating_margin=operating_margin if operating_margin is not None else _clean_numeric(info.get("operatingMargins")),
        return_on_equity=return_on_equity if return_on_equity is not None else _clean_numeric(info.get("returnOnEquity")),
        annual_free_cash_flow=annual_fcf,
        annual_revenue=annual_revenue,
        annual_net_income=annual_net_income,
        annual_dates=annual_dates,
        price_history=history,
        as_of=as_of_dt,
        fundamentals_as_of=fundamentals_as_of,
        is_historical=is_historical,
    )


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(" ", strip=True)


def fetch_finviz_snapshot(
    ticker: str,
    as_of_date: date | datetime | None = None,
) -> FinvizSnapshot:
    normalized = ticker.strip().upper()
    as_of_dt = _normalize_as_of_date(as_of_date)
    page_url = f"https://finviz.com/quote.ashx?t={normalized}&p=d"
    chart_url = f"https://finviz.com/chart.ashx?t={normalized}&p=d"

    if as_of_dt.date() < datetime.now(UTC).date():
        return FinvizSnapshot(
            ticker=normalized,
            company_name=None,
            last_close_label=None,
            price=None,
            sector=None,
            industry=None,
            country=None,
            exchange=None,
            metrics={},
            chart_url=chart_url,
            page_url=page_url,
            status="not_visible",
            note="Finviz snapshot is current-only in this app and is not reconstructed historically.",
        )

    response = _session().get(page_url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    page_text = soup.get_text(" ", strip=True)

    company_name = None
    title_tag = soup.find("title")
    if title_tag and " - " in title_tag.get_text():
        title_text = title_tag.get_text(" ", strip=True)
        parts = title_text.split(" - ")
        if len(parts) >= 2:
            company_name = parts[1].replace("Stock Price and Quote", "").strip()

    header_match = re.search(
        r"Last Close\s+([A-Za-z]{3}\s+\d{1,2}\s+•\s+\d{2}:\d{2}[AP]M ET)\s+([0-9]+(?:\.[0-9]+)?)",
        page_text,
        re.IGNORECASE,
    )
    classification_match = re.search(
        r"([A-Za-z][A-Za-z &/\-]+)\s+•\s+([A-Za-z][A-Za-z &/\-]+)\s+•\s+([A-Za-z .&\-]+)\s+•\s+([A-Z]+)",
        page_text,
    )

    metrics: dict[str, str] = {}
    for label_div in soup.select(".snapshot-td-label"):
        label = label_div.get_text(" ", strip=True)
        parent = label_div.find_parent("td")
        value_cell = parent.find_next_sibling("td") if parent else None
        value = value_cell.get_text(" ", strip=True) if value_cell else ""
        if label and value:
            metrics[label] = value

    sector = industry = country = exchange = None
    if classification_match:
        sector = classification_match.group(1).strip()
        industry = classification_match.group(2).strip()
        country = classification_match.group(3).strip()
        exchange = classification_match.group(4).strip()

    return FinvizSnapshot(
        ticker=normalized,
        company_name=company_name,
        last_close_label=header_match.group(1) if header_match else None,
        price=_clean_numeric(header_match.group(2) if header_match else metrics.get("Price")),
        sector=sector,
        industry=industry,
        country=country,
        exchange=exchange,
        metrics=metrics,
        chart_url=chart_url,
        page_url=page_url,
        status="visible",
        note=None,
    )


@lru_cache(maxsize=1)
def _fetch_sec_ticker_mapping() -> dict[str, str]:
    response = _sec_session().get(SEC_TICKERS_URL, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    mapping: dict[str, str] = {}
    for item in payload.values():
        ticker = str(item.get("ticker", "")).upper().replace(".", "-")
        cik = str(item.get("cik_str", "")).zfill(10)
        if ticker and cik:
            mapping[ticker] = cik
    return mapping


def lookup_sec_cik(ticker: str) -> str | None:
    normalized = ticker.strip().upper().replace(".", "-")
    try:
        return _fetch_sec_ticker_mapping().get(normalized)
    except Exception:
        return None


def fetch_sec_filings(
    ticker: str,
    as_of_date: date | datetime | None = None,
    forms: tuple[str, ...] = ("10-K", "10-Q", "8-K"),
    limit: int = 12,
) -> list[SecFiling]:
    as_of_dt = _normalize_as_of_date(as_of_date)
    normalized = ticker.strip().upper().replace(".", "-")
    cik = lookup_sec_cik(normalized)
    if not cik:
        return []
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = _sec_session().get(submissions_url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    recent = payload.get("filings", {}).get("recent", {})
    forms_list = recent.get("form", [])
    dates_list = recent.get("filingDate", [])
    accession_list = recent.get("accessionNumber", [])
    docs_list = recent.get("primaryDocument", [])
    desc_list = recent.get("primaryDocDescription", [])

    rows: list[SecFiling] = []
    for form, filing_date, accession, primary_doc, description in zip(
        forms_list,
        dates_list,
        accession_list,
        docs_list,
        desc_list,
        strict=False,
    ):
        if form not in forms:
            continue
        if filing_date > as_of_dt.date().isoformat():
            continue
        accession_nodash = accession.replace("-", "")
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{primary_doc}"
        interactive_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/index.json"
        rows.append(
            SecFiling(
                ticker=normalized,
                cik=cik,
                form=form,
                filing_date=filing_date,
                accession_number=accession,
                primary_document=primary_doc,
                description=description,
                filing_url=filing_url,
                interactive_url=interactive_url,
            )
        )
        if len(rows) >= limit:
            break
    return rows


def build_source_status_records(
    snapshot: StockSnapshot,
    external_rows: list[ExternalValuation],
    finviz_snapshot: FinvizSnapshot,
    sec_filings: list[SecFiling],
) -> list[SourceStatusRecord]:
    retrieved_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    as_of_label = snapshot.as_of.date().isoformat() if snapshot.as_of else None
    rows: list[SourceStatusRecord] = []

    yfinance_rule = get_source_rule("yfinance")
    yfinance_status = "ok"
    yfinance_note = None
    if snapshot.current_price is None:
        yfinance_status = "partial"
        yfinance_note = "Price missing from yfinance snapshot."
    elif not snapshot.annual_dates:
        yfinance_status = "partial"
        yfinance_note = "Financial statements missing from yfinance snapshot."
    rows.append(
        SourceStatusRecord(
            source="yfinance",
            status=yfinance_status,
            retrieved_at=retrieved_at,
            as_of_date=as_of_label,
            access=yfinance_rule.access_mode if yfinance_rule else None,
            note=yfinance_note,
            url=f"https://finance.yahoo.com/quote/{snapshot.ticker}",
        )
    )

    sec_rule = get_source_rule("SEC EDGAR")
    sec_status = "ok" if sec_filings else "partial"
    sec_note = None if sec_filings else "No filings found for current SEC lookup and selected as-of date."
    cik = lookup_sec_cik(snapshot.ticker)
    sec_company_url = (
        f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&owner=exclude&count=40"
        if cik
        else None
    )
    rows.append(
        SourceStatusRecord(
            source="SEC EDGAR",
            status=sec_status,
            retrieved_at=retrieved_at,
            as_of_date=as_of_label,
            access=sec_rule.access_mode if sec_rule else None,
            note=sec_note,
            url=sec_company_url,
        )
    )

    finviz_rule = get_source_rule("Finviz")
    rows.append(
        SourceStatusRecord(
            source="Finviz",
            status="ok" if finviz_snapshot.status == "visible" else finviz_snapshot.status,
            retrieved_at=retrieved_at,
            as_of_date=as_of_label,
            access=finviz_rule.access_mode if finviz_rule else None,
            note=finviz_snapshot.note,
            url=finviz_snapshot.page_url,
        )
    )

    by_source: dict[str, list[ExternalValuation]] = {}
    for item in external_rows:
        by_source.setdefault(item.source, []).append(item)
    for source, items in by_source.items():
        statuses = {item.status for item in items}
        status = "ok" if statuses == {"visible"} else "partial" if "visible" in statuses else "not_visible"
        note = "; ".join(sorted({item.note for item in items if item.note}))
        url = next((item.url for item in items if item.url), None)
        rows.append(
            SourceStatusRecord(
                source=source,
                status=status,
                retrieved_at=retrieved_at,
                as_of_date=as_of_label,
                access=(get_source_rule(source).access_mode if get_source_rule(source) else None),
                note=note or (get_source_rule(source).note if get_source_rule(source) else None),
                url=url,
            )
        )

    seen_sources = {row.source for row in rows}
    for source_name in ["Morningstar", "GuruFocus", "FAST Graphs", "SimFin", "Alpha Vantage", "Financial Modeling Prep"]:
        if source_name in seen_sources:
            continue
        rule = get_source_rule(source_name)
        if rule is None:
            continue
        rows.append(
            SourceStatusRecord(
                source=source_name,
                status=rule.app_status,
                retrieved_at=retrieved_at,
                as_of_date=as_of_label,
                access=rule.access_mode,
                note=rule.note,
                url=rule.official_reference,
            )
        )

    return rows


def _parse_alpha_spread(ticker: str) -> list[ExternalValuation]:
    url = f"https://www.alphaspread.com/security/nasdaq/{ticker.lower()}/summary"
    response = _session().get(url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    text = _extract_text(response.text)

    price_match = re.search(r"Price:\s*([0-9]+(?:\.[0-9]+)?)\s*USD", text)
    current_price = _clean_numeric(price_match.group(1) if price_match else None)

    intrinsic_match = re.search(
        r"Intrinsic Value .*?Base Case is\s*([0-9]+(?:\.[0-9]+)?)\s*USD",
        text,
        re.IGNORECASE,
    )
    dcf_match = re.search(
        r"DCF Value .*?stock is\s*([0-9]+(?:\.[0-9]+)?)\s*USD",
        text,
        re.IGNORECASE,
    )
    multiples_match = re.search(
        r"Multiples-Based Value\s*\$([0-9]+(?:\.[0-9]+)?)",
        text,
        re.IGNORECASE,
    )
    updated_match = re.search(
        r"DCF valuation model was created by .*? last updated on ([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        text,
        re.IGNORECASE,
    )
    dcf_updated = updated_match.group(1) if updated_match else None

    rows = [
        ExternalValuation(
            source="Alpha Spread",
            exact_label="Intrinsic Value",
            valuation_family="Hybrid",
            value=_clean_numeric(intrinsic_match.group(1) if intrinsic_match else None),
            ratio=None,
            upside_downside_pct=None,
            method="Blended DCF + multiples",
            updated=None,
            url=url,
        ),
        ExternalValuation(
            source="Alpha Spread",
            exact_label="DCF Value",
            valuation_family="DCF",
            value=_clean_numeric(dcf_match.group(1) if dcf_match else None),
            ratio=None,
            upside_downside_pct=None,
            method="FCFF-based DCF",
            updated=dcf_updated,
            url=f"https://www.alphaspread.com/security/nasdaq/{ticker.lower()}/dcf-valuation",
        ),
        ExternalValuation(
            source="Alpha Spread",
            exact_label="Multiples-Based Value",
            valuation_family="Historical-Multiples",
            value=_clean_numeric(multiples_match.group(1) if multiples_match else None),
            ratio=None,
            upside_downside_pct=None,
            method="Relative valuation multiples",
            updated=None,
            url=url,
        ),
    ]
    for row in rows:
        if row.value is not None and current_price:
            row.upside_downside_pct = (row.value / current_price - 1.0) * 100.0
    return rows


def _parse_simply_wall_st(ticker: str) -> list[ExternalValuation]:
    url = f"https://simplywall.st/stocks/us/software/nasdaq-{ticker.lower()}/{ticker.lower()}/valuation"
    fallback_url = f"https://simplywall.st/stocks/us/software/nasdaq-{ticker.lower()}/microsoft/valuation"
    response = _session().get(fallback_url if ticker.upper() == "MSFT" else url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    text = _extract_text(response.text)

    price_match = re.search(r"MSFT \(\$([0-9]+(?:\.[0-9]+)?)\) is trading", text)
    if not price_match:
        price_match = re.search(r"\(([A-Z]{1,5})\) \(\$([0-9]+(?:\.[0-9]+)?)\) is trading", text)
    current_price = _clean_numeric(price_match.group(price_match.lastindex) if price_match else None)

    fcf_value_match = re.search(
        r"future cash flow value \(\$([0-9]+(?:\.[0-9]+)?)\)",
        text,
        re.IGNORECASE,
    )
    current_pe_match = re.search(r"Current PE Ratio\s*([0-9]+(?:\.[0-9]+)?)x", text)
    fair_pe_match = re.search(r"Fair PE Ratio\s*([0-9]+(?:\.[0-9]+)?)x", text)

    value = _clean_numeric(fcf_value_match.group(1) if fcf_value_match else None)
    ratio = None
    current_pe = _clean_numeric(current_pe_match.group(1) if current_pe_match else None)
    fair_pe = _clean_numeric(fair_pe_match.group(1) if fair_pe_match else None)
    if current_pe is not None and fair_pe:
        ratio = current_pe / fair_pe

    row = ExternalValuation(
        source="Simply Wall St",
        exact_label="Future Cash Flow Value",
        valuation_family="DCF",
        value=value,
        ratio=ratio,
        upside_downside_pct=((value / current_price - 1.0) * 100.0) if value and current_price else None,
        method="Discounted cash flow",
        updated=None,
        url=response.url,
    )
    return [row]


def _unavailable_source_rows(ticker: str) -> list[ExternalValuation]:
    morningstar_rule = get_source_rule("Morningstar")
    gurufocus_rule = get_source_rule("GuruFocus")
    fastgraphs_rule = get_source_rule("FAST Graphs")
    return [
        ExternalValuation(
            source="Morningstar",
            exact_label="Fair Value Estimate",
            valuation_family="Fair Value",
            value=None,
            ratio=None,
            upside_downside_pct=None,
            method="Analyst fair value model",
            updated=None,
            url=f"https://www.morningstar.com/stocks/xnas/{ticker.upper()}/valuation",
            status=morningstar_rule.app_status if morningstar_rule else "requires_license",
            note=morningstar_rule.note if morningstar_rule else "Official access requires licensed Morningstar credentials or manual export.",
        ),
        ExternalValuation(
            source="GuruFocus",
            exact_label="GF Value",
            valuation_family="Fair Value",
            value=None,
            ratio=None,
            upside_downside_pct=None,
            method="GF Value",
            updated=None,
            url=f"https://www.gurufocus.com/term/gf-value/{ticker.upper()}",
            status=gurufocus_rule.app_status if gurufocus_rule else "requires_api_key",
            note=gurufocus_rule.note if gurufocus_rule else "Official access is via GuruFocus Data API or your own account export.",
        ),
        ExternalValuation(
            source="FAST Graphs",
            exact_label="Fair Value / Normal P/E",
            valuation_family="Earnings-Based",
            value=None,
            ratio=None,
            upside_downside_pct=None,
            method="Normal P/E historical valuation",
            updated=None,
            url="https://www.fastgraphs.com/",
            status=fastgraphs_rule.app_status if fastgraphs_rule else "requires_subscription",
            note=fastgraphs_rule.note if fastgraphs_rule else "Official access requires a FAST Graphs subscription or trial session.",
        ),
    ]


def fetch_external_valuations(
    ticker: str,
    as_of_date: date | datetime | None = None,
) -> list[ExternalValuation]:
    as_of_dt = _normalize_as_of_date(as_of_date)
    if as_of_dt.date() < datetime.now(UTC).date():
        historical_note = (
            "Historical external valuation snapshots are not available in this app. "
            "Use the house valuation model for point-in-time analysis."
        )
        rows = _unavailable_source_rows(ticker)
        for row in rows:
            row.status = "not_visible"
            row.note = historical_note
        rows.insert(
            0,
            ExternalValuation(
                source="Point-in-time mode",
                exact_label="Historical external valuations",
                valuation_family="n/a",
                value=None,
                ratio=None,
                upside_downside_pct=None,
                method="n/a",
                updated=as_of_dt.strftime("%Y-%m-%d"),
                url="",
                status="not_visible",
                note=historical_note,
            )
        )
        return rows
    rows: list[ExternalValuation] = []
    try:
        rows.extend(_parse_alpha_spread(ticker))
    except Exception as exc:
        rows.append(
            ExternalValuation(
                source="Alpha Spread",
                exact_label="Intrinsic Value",
                valuation_family="Hybrid",
                value=None,
                ratio=None,
                upside_downside_pct=None,
                  method="Blended DCF + multiples",
                  updated=None,
                  url=f"https://www.alphaspread.com/security/nasdaq/{ticker.lower()}/summary",
                  status="not_visible",
                  note=str(exc),
              )
        )
    try:
        rows.extend(_parse_simply_wall_st(ticker))
    except Exception as exc:
        rows.append(
            ExternalValuation(
                source="Simply Wall St",
                exact_label="Future Cash Flow Value",
                valuation_family="DCF",
                value=None,
                ratio=None,
                upside_downside_pct=None,
                  method="Discounted cash flow",
                  updated=None,
                  url=f"https://simplywall.st/stocks/us/software/nasdaq-{ticker.lower()}/{ticker.lower()}/valuation",
                  status="not_visible",
                  note=str(exc),
              )
        )
    rows.extend(_unavailable_source_rows(ticker))
    return rows


def screen_sp100(
    tickers: list[Any],
    fetcher,
    max_workers: int = 8,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(fetcher, ticker): ticker for ticker in tickers}
        for future in as_completed(future_map):
            ticker = future_map[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                status, message = _classify_fetch_error(exc)
                ticker_label = ticker.get("ticker") if isinstance(ticker, dict) else ticker
                company_name = ticker.get("company_name") if isinstance(ticker, dict) else None
                sector_name = ticker.get("sector") if isinstance(ticker, dict) else None
                rows.append(
                    {
                        "ticker": ticker_label,
                        "company_name": company_name,
                        "sector": sector_name,
                        "current_price": None,
                        "fair_value": None,
                        "undervaluation_pct": None,
                        "confidence": None,
                        "status": status,
                        "note": message,
                    }
                )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    sort_key = "undervaluation_pct" if "undervaluation_pct" in frame.columns else "ticker"
    return frame.sort_values(sort_key, ascending=False, na_position="last").reset_index(drop=True)
