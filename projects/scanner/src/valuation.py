from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from src.core.config import BLEND_MODEL_VERSION, VALUATION_MODEL_VERSION
from src.data_sources import ExternalValuation, StockSnapshot


@dataclass
class HouseValuation:
    dcf_fair_value: float | None
    earnings_fair_value: float | None
    blended_fair_value: float | None
    fair_value_low: float | None
    fair_value_high: float | None
    undervaluation_pct: float | None
    quality_score: float
    confidence_score: float
    data_quality_score: int
    stability_score: float
    stage1_growth: float | None
    stage2_growth: float | None
    discount_rate: float | None
    terminal_growth: float | None
    normalized_fcf: float | None
    fair_pe: float | None
    model_version: str
    notes: list[str]


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _industry_text(snapshot: StockSnapshot) -> str:
    return (snapshot.industry or "").lower()


def _sector_text(snapshot: StockSnapshot) -> str:
    return (snapshot.sector or "").lower()


def _is_financial_like(snapshot: StockSnapshot) -> bool:
    industry = _industry_text(snapshot)
    sector = _sector_text(snapshot)
    return sector == "financial services" or any(
        token in industry
        for token in ["bank", "insurance", "credit", "asset management", "capital markets", "financial data"]
    )


def _is_telecom_like(snapshot: StockSnapshot) -> bool:
    industry = _industry_text(snapshot)
    sector = _sector_text(snapshot)
    return sector == "communication services" and any(
        token in industry for token in ["telecom", "cable", "broadcast", "wireless"]
    )


def _is_utility_like(snapshot: StockSnapshot) -> bool:
    return _sector_text(snapshot) == "utilities"


def _is_energy_like(snapshot: StockSnapshot) -> bool:
    return _sector_text(snapshot) == "energy"


def _is_healthcare_like(snapshot: StockSnapshot) -> bool:
    return _sector_text(snapshot) == "healthcare"


def _is_consumer_defensive_like(snapshot: StockSnapshot) -> bool:
    return _sector_text(snapshot) == "consumer defensive"


def _is_technology_like(snapshot: StockSnapshot) -> bool:
    sector = _sector_text(snapshot)
    industry = _industry_text(snapshot)
    return sector == "technology" or any(
        token in industry for token in ["software", "semiconductor", "internet content", "information technology"]
    )


def _cagr(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v)) and float(v) > 0]
    if len(clean) < 2:
        return None
    start = clean[-1]
    end = clean[0]
    periods = len(clean) - 1
    if start <= 0 or end <= 0 or periods <= 0:
        return None
    return (end / start) ** (1 / periods) - 1.0


def _median_growth(snapshot: StockSnapshot) -> float:
    candidates: list[float] = []
    if snapshot.revenue_growth is not None:
        candidates.append(float(snapshot.revenue_growth))
    if snapshot.earnings_growth is not None:
        candidates.append(_clip(float(snapshot.earnings_growth), -0.08, 0.20))
    revenue_cagr = _cagr(snapshot.annual_revenue)
    if revenue_cagr is not None:
        candidates.append(_clip(revenue_cagr, -0.05, 0.18))
    income_cagr = _cagr(snapshot.annual_net_income)
    if income_cagr is not None:
        candidates.append(_clip(income_cagr, -0.08, 0.20))
    fcf_cagr = _cagr(snapshot.annual_free_cash_flow)
    if fcf_cagr is not None:
        candidates.append(_clip(fcf_cagr, -0.08, 0.20))
    if not candidates:
        return 0.05
    median = float(np.median(candidates))
    if _is_financial_like(snapshot):
        return _clip(median, 0.01, 0.08)
    if _is_telecom_like(snapshot) or _is_utility_like(snapshot):
        return _clip(median, 0.01, 0.07)
    if _is_energy_like(snapshot):
        return _clip(median, 0.00, 0.08)
    if _is_consumer_defensive_like(snapshot):
        return _clip(median, 0.01, 0.08)
    if _is_technology_like(snapshot):
        return _clip(median, 0.03, 0.14)
    return _clip(median, 0.01, 0.11)


def _normalized_fcf(snapshot: StockSnapshot) -> float | None:
    positive_fcf = [float(v) for v in snapshot.annual_free_cash_flow if v is not None and float(v) > 0]
    fcf_base = None
    if positive_fcf:
        window = positive_fcf[: min(3, len(positive_fcf))]
        fcf_base = float(np.mean(window))

    earnings_power = None
    if snapshot.trailing_eps is not None and snapshot.shares_outstanding:
        earnings_power = snapshot.trailing_eps * snapshot.shares_outstanding
        if earnings_power <= 0:
            earnings_power = None

    if _is_financial_like(snapshot):
        return None
    if fcf_base is not None and earnings_power is not None:
        moderated_earnings = min(earnings_power, fcf_base * 1.25)
        return 0.65 * fcf_base + 0.35 * moderated_earnings
    if fcf_base is not None:
        return fcf_base
    if earnings_power is not None and not (_is_telecom_like(snapshot) or _is_utility_like(snapshot)):
        return 0.75 * earnings_power
    return None


def _quality_score(snapshot: StockSnapshot) -> float:
    score = 0.0
    if snapshot.profit_margin is not None:
        score += _clip(snapshot.profit_margin / 0.20, 0.0, 1.0)
    if snapshot.operating_margin is not None:
        score += _clip(snapshot.operating_margin / 0.25, 0.0, 1.0)
    if snapshot.return_on_equity is not None:
        score += _clip(snapshot.return_on_equity / 0.25, 0.0, 1.0)
    if snapshot.annual_free_cash_flow and snapshot.annual_free_cash_flow[0] > 0:
        score += 1.0
    return _clip(score / 4.0, 0.0, 1.0)


def _data_quality_score(snapshot: StockSnapshot) -> int:
    score = 100
    if snapshot.current_price is None:
        score -= 15
    if not snapshot.annual_dates:
        score -= 15
    if not snapshot.annual_revenue:
        score -= 15
    if not snapshot.annual_net_income:
        score -= 10
    if not snapshot.annual_free_cash_flow and not _is_financial_like(snapshot):
        score -= 10
    if snapshot.shares_outstanding is None:
        score -= 10
    if snapshot.sector is None:
        score -= 5
    if snapshot.currency is None:
        score -= 5
    if not snapshot.is_historical and snapshot.beta is None:
        score -= 5
    if snapshot.fundamentals_as_of:
        try:
            fundamentals_date = datetime.fromisoformat(snapshot.fundamentals_as_of).date()
            age_days = (snapshot.as_of.date() - fundamentals_date).days
            if age_days > 730:
                score -= 15
            elif age_days > 550:
                score -= 10
        except Exception:
            score -= 5
    return max(score, 0)


def _dcf_value_per_share(
    starting_fcf: float,
    shares_outstanding: float,
    net_cash: float,
    stage1_growth: float,
    stage2_growth: float,
    discount_rate: float,
    terminal_growth: float,
    years1: int = 5,
    years2: int = 5,
) -> float | None:
    if shares_outstanding <= 0 or starting_fcf <= 0 or discount_rate <= terminal_growth:
        return None
    cash_flow = starting_fcf
    pv = 0.0
    for year in range(1, years1 + 1):
        cash_flow *= 1.0 + stage1_growth
        pv += cash_flow / ((1.0 + discount_rate) ** year)
    for year in range(1, years2 + 1):
        cash_flow *= 1.0 + stage2_growth
        pv += cash_flow / ((1.0 + discount_rate) ** (years1 + year))
    terminal_value = cash_flow * (1.0 + terminal_growth) / (discount_rate - terminal_growth)
    pv += terminal_value / ((1.0 + discount_rate) ** (years1 + years2))
    equity_value = pv + net_cash
    return equity_value / shares_outstanding


def _fair_pe(snapshot: StockSnapshot, growth: float, quality: float) -> float | None:
    if snapshot.forward_eps is None and snapshot.trailing_eps is None:
        return None
    beta_penalty = max((snapshot.beta or 1.0) - 1.0, 0.0) * 1.25
    if _is_financial_like(snapshot):
        pe = 7.5 + (max(growth, 0.0) * 22.0) + (quality * 1.8) - beta_penalty
        return _clip(pe, 7.0, 12.5)
    if _is_telecom_like(snapshot):
        pe = 8.0 + (max(growth, 0.0) * 18.0) + (quality * 1.8) - beta_penalty
        return _clip(pe, 7.5, 12.5)
    if _is_utility_like(snapshot):
        pe = 10.0 + (max(growth, 0.0) * 18.0) + (quality * 2.0) - beta_penalty
        return _clip(pe, 9.0, 16.0)
    if _is_energy_like(snapshot):
        pe = 8.0 + (max(growth, 0.0) * 16.0) + (quality * 1.8) - beta_penalty
        return _clip(pe, 7.0, 13.5)
    if _is_consumer_defensive_like(snapshot):
        pe = 11.0 + (max(growth, 0.0) * 20.0) + (quality * 2.2) - beta_penalty
        return _clip(pe, 10.0, 18.0)
    if _is_healthcare_like(snapshot):
        pe = 12.0 + (max(growth, 0.0) * 24.0) + (quality * 2.5) - beta_penalty
        return _clip(pe, 10.0, 20.0)
    if _is_technology_like(snapshot):
        pe = 14.0 + (max(growth, 0.0) * 40.0) + (quality * 3.2) - beta_penalty
        return _clip(pe, 12.0, 24.0)
    pe = 11.0 + (max(growth, 0.0) * 26.0) + (quality * 2.4) - beta_penalty
    return _clip(pe, 9.0, 20.0)


def _financial_book_anchor(snapshot: StockSnapshot, quality: float) -> float | None:
    if snapshot.book_value_per_share is None or snapshot.book_value_per_share <= 0:
        return None
    roe = snapshot.return_on_equity or 0.10
    fair_pb = _clip(0.85 + max(roe, 0.0) * 2.2 + quality * 0.20, 0.80, 1.45)
    return fair_pb * snapshot.book_value_per_share


def _value_guardrails(snapshot: StockSnapshot, value: float | None) -> float | None:
    if value is None or snapshot.current_price is None or snapshot.current_price <= 0:
        return value
    if _is_financial_like(snapshot):
        min_ratio, max_ratio = 0.75, 1.45
    elif _is_telecom_like(snapshot):
        min_ratio, max_ratio = 0.70, 1.45
    elif _is_utility_like(snapshot):
        min_ratio, max_ratio = 0.80, 1.45
    elif _is_energy_like(snapshot):
        min_ratio, max_ratio = 0.70, 1.60
    elif _is_consumer_defensive_like(snapshot):
        min_ratio, max_ratio = 0.75, 1.55
    elif _is_healthcare_like(snapshot):
        min_ratio, max_ratio = 0.70, 1.65
    elif _is_technology_like(snapshot):
        min_ratio, max_ratio = 0.60, 1.80
    else:
        min_ratio, max_ratio = 0.65, 1.70
    low = snapshot.current_price * min_ratio
    high = snapshot.current_price * max_ratio
    return _clip(value, low, high)


def _stability_score(values: list[float]) -> float:
    clean = [float(v) for v in values if v is not None and float(v) > 0]
    if len(clean) < 2:
        return 0.65
    median = float(np.median(clean))
    if median <= 0:
        return 0.25
    dispersion = float(np.std(clean) / median)
    return _clip(1.0 - dispersion, 0.15, 1.0)


def compute_house_valuation(snapshot: StockSnapshot, risk_free_rate: float) -> HouseValuation:
    notes: list[str] = []
    if snapshot.is_historical:
        notes.append(
            "Point-in-time mode: price is taken as of the selected date, and fundamentals are limited to statements available on or before that date."
        )
        if snapshot.fundamentals_as_of:
            notes.append(f"Latest fundamentals used in model: {snapshot.fundamentals_as_of}.")

    quality = _quality_score(snapshot)
    data_quality = _data_quality_score(snapshot)
    growth = _median_growth(snapshot)
    stage1_growth = _clip(growth, 0.01, 0.14)
    stage2_growth = _clip(stage1_growth * 0.50, 0.015, 0.05)
    beta = snapshot.beta if snapshot.beta is not None else 1.0
    discount_rate = _clip(risk_free_rate + beta * 0.038, 0.075, 0.105)
    terminal_growth = 0.03

    normalized_fcf = _normalized_fcf(snapshot)
    if normalized_fcf is None:
        notes.append("Reported free cash flow is missing or not suitable for this business type; the DCF leg is reduced or skipped.")
    if snapshot.shares_outstanding is None:
        notes.append("Shares outstanding not available; per-share valuation is less reliable.")

    raw_dcf = None
    if normalized_fcf is not None and snapshot.shares_outstanding:
        raw_dcf = _dcf_value_per_share(
            starting_fcf=normalized_fcf,
            shares_outstanding=snapshot.shares_outstanding,
            net_cash=float(snapshot.net_cash or 0.0),
            stage1_growth=stage1_growth,
            stage2_growth=stage2_growth,
            discount_rate=discount_rate,
            terminal_growth=terminal_growth,
        )

    fair_pe = _fair_pe(snapshot, stage1_growth, quality)
    raw_earnings = None
    earnings_anchor = snapshot.forward_eps or snapshot.trailing_eps
    if fair_pe is not None and earnings_anchor is not None:
        raw_earnings = fair_pe * earnings_anchor

    raw_book = _financial_book_anchor(snapshot, quality) if _is_financial_like(snapshot) else None

    dcf_fair_value = _value_guardrails(snapshot, raw_dcf)
    earnings_fair_value = _value_guardrails(snapshot, raw_earnings)
    book_fair_value = _value_guardrails(snapshot, raw_book)

    if raw_dcf is not None and dcf_fair_value is not None and abs(raw_dcf - dcf_fair_value) > 1e-6:
        notes.append("DCF output was clipped by sector guardrails.")
    if raw_earnings is not None and earnings_fair_value is not None and abs(raw_earnings - earnings_fair_value) > 1e-6:
        notes.append("Earnings anchor was clipped by sector guardrails.")
    if raw_book is not None and book_fair_value is not None and abs(raw_book - book_fair_value) > 1e-6:
        notes.append("Book-value anchor was clipped by sector guardrails.")

    anchor_values = [value for value in [dcf_fair_value, earnings_fair_value, book_fair_value] if value is not None]
    stability = _stability_score(anchor_values)
    if len(anchor_values) >= 2 and stability < 0.45:
        notes.append("Model anchors disagree materially, so the blended fair value is shrunk toward the observed price.")

    raw_blended = None
    if _is_financial_like(snapshot):
        anchors = [value for value in [book_fair_value, earnings_fair_value] if value is not None]
        if len(anchors) == 2:
            raw_blended = 0.65 * book_fair_value + 0.35 * earnings_fair_value
        elif anchors:
            raw_blended = anchors[0]
        if raw_blended is not None:
            notes.append("Financial-sector model: book-value and earnings anchors dominate the house fair value.")
    elif _is_telecom_like(snapshot) or _is_utility_like(snapshot) or _is_energy_like(snapshot):
        if dcf_fair_value is not None and earnings_fair_value is not None:
            raw_blended = 0.20 * dcf_fair_value + 0.80 * earnings_fair_value
            notes.append("Capital-intensive sector model: the earnings anchor carries more weight than DCF.")
        else:
            raw_blended = earnings_fair_value if earnings_fair_value is not None else dcf_fair_value
    else:
        if dcf_fair_value is not None and earnings_fair_value is not None:
            raw_blended = 0.40 * dcf_fair_value + 0.60 * earnings_fair_value
        elif dcf_fair_value is not None:
            raw_blended = dcf_fair_value
        elif earnings_fair_value is not None:
            raw_blended = earnings_fair_value

    blended_fair_value = raw_blended
    if blended_fair_value is not None and snapshot.current_price is not None:
        shrink = _clip(0.35 + 0.35 * stability + 0.30 * (data_quality / 100.0), 0.35, 0.95)
        blended_fair_value = snapshot.current_price + shrink * (blended_fair_value - snapshot.current_price)
        blended_fair_value = _value_guardrails(snapshot, blended_fair_value)

    fair_value_low = None
    fair_value_high = None
    if anchor_values:
        fair_value_low = min(anchor_values)
        fair_value_high = max(anchor_values)
    if fair_value_low is None and blended_fair_value is not None:
        fair_value_low = blended_fair_value * 0.90
        fair_value_high = blended_fair_value * 1.10
    fair_value_low = _value_guardrails(snapshot, fair_value_low)
    fair_value_high = _value_guardrails(snapshot, fair_value_high)

    undervaluation_pct = None
    if blended_fair_value is not None and snapshot.current_price:
        undervaluation_pct = (blended_fair_value / snapshot.current_price - 1.0) * 100.0

    completeness = sum(
        value is not None
        for value in [
            snapshot.current_price,
            snapshot.shares_outstanding,
            snapshot.trailing_eps,
            snapshot.forward_eps,
            normalized_fcf,
            snapshot.book_value_per_share,
        ]
    ) / 6.0
    confidence = _clip(
        0.20 * completeness
        + 0.20 * quality
        + 0.30 * (data_quality / 100.0)
        + 0.30 * stability,
        0.0,
        1.0,
    )

    if data_quality < 70:
        notes.append("Data quality is limited for this ticker/date, so valuation confidence is reduced.")

    return HouseValuation(
        dcf_fair_value=dcf_fair_value,
        earnings_fair_value=earnings_fair_value,
        blended_fair_value=blended_fair_value,
        fair_value_low=fair_value_low,
        fair_value_high=fair_value_high,
        undervaluation_pct=undervaluation_pct,
        quality_score=quality,
        confidence_score=confidence,
        data_quality_score=data_quality,
        stability_score=stability,
        stage1_growth=stage1_growth,
        stage2_growth=stage2_growth,
        discount_rate=discount_rate,
        terminal_growth=terminal_growth,
        normalized_fcf=normalized_fcf,
        fair_pe=fair_pe,
        model_version=f"{VALUATION_MODEL_VERSION} / {BLEND_MODEL_VERSION}",
        notes=notes,
    )


def build_external_valuation_table(
    valuations: list[ExternalValuation],
):
    import pandas as pd

    rows: list[dict[str, Any]] = []
    for item in valuations:
        rows.append(
            {
                "Source": item.source,
                "Exact Label": item.exact_label,
                "Valuation Family": item.valuation_family,
                "Value": item.value,
                "Ratio": item.ratio,
                "Upside/Downside %": item.upside_downside_pct,
                "Method": item.method,
                "Updated": item.updated,
                "Status": item.status,
                "Note": item.note,
                "URL": item.url,
            }
        )
    return pd.DataFrame(rows)
