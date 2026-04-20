from __future__ import annotations

import pandas as pd

from .schemas import SourceAccessRule


SOURCE_REGISTRY: dict[str, SourceAccessRule] = {
    "yfinance": SourceAccessRule(
        source="yfinance",
        access_mode="public_library_fallback",
        app_status="ok",
        legal_path="Use as an unofficial convenience layer for public market data; do not treat it as the primary source of record.",
        app_support="Integrated",
        official_reference="https://ranaroussi.github.io/yfinance/",
        note="Best-effort fallback for prices and basic fundamentals. Subject to layout and rate-limit instability.",
    ),
    "SEC EDGAR": SourceAccessRule(
        source="SEC EDGAR",
        access_mode="public_api",
        app_status="ok",
        legal_path="Use the official SEC APIs and filings with a declared user agent and fair-access limits.",
        app_support="Integrated",
        official_reference="https://www.sec.gov/edgar/sec-api-documentation",
        note="Best official source for US filings, company facts, and filing history.",
    ),
    "Finviz": SourceAccessRule(
        source="Finviz",
        access_mode="public_web_current_only",
        app_status="ok",
        legal_path="Use only the currently visible public snapshot and chart; do not reconstruct historical snapshots unless you have your own archive.",
        app_support="Integrated",
        official_reference="https://finviz.com/",
        note="Current snapshot only in this app.",
    ),
    "Alpha Spread": SourceAccessRule(
        source="Alpha Spread",
        access_mode="public_page_visible_fields",
        app_status="ok",
        legal_path="Use only visible public valuation fields and clearly label them as third-party model outputs.",
        app_support="Integrated",
        official_reference="https://www.alphaspread.com/intrinsic-value-calculator",
        note="Public valuation rows can be parsed when visible.",
    ),
    "Simply Wall St": SourceAccessRule(
        source="Simply Wall St",
        access_mode="public_page_visible_fields",
        app_status="ok",
        legal_path="Use only the visible public valuation fields and do not infer hidden values.",
        app_support="Integrated",
        official_reference="https://support.simplywall.st/hc/en-us/articles/4751563581071-Understanding-the-Valuation-section-in-the-company-report",
        note="Public teaser valuation fields can be used when visible.",
    ),
    "Morningstar": SourceAccessRule(
        source="Morningstar",
        access_mode="licensed_api_or_product_login",
        app_status="requires_license",
        legal_path="Use visible public terminology pages or obtain access via Morningstar products, Direct, Essentials, or API Center credentials. Manual export from a licensed session is acceptable.",
        app_support="Manual import or licensed integration later",
        official_reference="https://advisor.morningstar.com/Enterprise/VTC/MorningstarRemoteAccessInstructions.pdf",
        note="Per-ticker research and API access depend on a product subscription or licensed credentials.",
    ),
    "GuruFocus": SourceAccessRule(
        source="GuruFocus",
        access_mode="account_or_data_api",
        app_status="requires_api_key",
        legal_path="Use the public site where visible in a normal browser or enable the official GuruFocus Data API. Manual export from your own account is acceptable.",
        app_support="Manual import or API-key integration later",
        official_reference="https://www.gurufocus.com/data-api",
        note="App requests may hit anti-bot protection even when the site is readable in a browser.",
    ),
    "FAST Graphs": SourceAccessRule(
        source="FAST Graphs",
        access_mode="subscription_or_trial_session",
        app_status="requires_subscription",
        legal_path="Use an active subscription or trial session and import your own exported values rather than scraping restricted pages.",
        app_support="Manual import later",
        official_reference="https://www.fastgraphs.com/pricing",
        note="Current valuation outputs depend on an authenticated subscription session.",
    ),
    "SimFin": SourceAccessRule(
        source="SimFin",
        access_mode="free_account_or_paid_api",
        app_status="requires_api_key",
        legal_path="Use the SimFin Python/Web API or bulk CSV download under its published plans and terms.",
        app_support="Planned",
        official_reference="https://www.simfin.com/en/fundamental-data-download/",
        note="Good legal source for normalized historical fundamentals and metrics.",
    ),
    "Alpha Vantage": SourceAccessRule(
        source="Alpha Vantage",
        access_mode="api_key",
        app_status="requires_api_key",
        legal_path="Use the official API with your own key and observe usage limits or premium entitlements.",
        app_support="Planned",
        official_reference="https://www.alphavantage.co/documentation/",
        note="Useful for company overview, fundamentals, estimates, and market data.",
    ),
    "Financial Modeling Prep": SourceAccessRule(
        source="Financial Modeling Prep",
        access_mode="api_key",
        app_status="requires_api_key",
        legal_path="Use the official API and licensed plan appropriate to personal or commercial use.",
        app_support="Planned",
        official_reference="https://site.financialmodelingprep.com/developer/docs/stable/enterprise-values",
        note="Useful for financial statements, analyst targets, DCF, and enterprise value endpoints.",
    ),
}


def get_source_rule(source: str) -> SourceAccessRule | None:
    return SOURCE_REGISTRY.get(source)


def source_access_frame() -> pd.DataFrame:
    rows = []
    for rule in SOURCE_REGISTRY.values():
        rows.append(
            {
                "Source": rule.source,
                "Access": rule.access_mode,
                "Default status": rule.app_status,
                "App support": rule.app_support,
                "Legal acquisition path": rule.legal_path,
                "Official reference": rule.official_reference,
                "Note": rule.note,
            }
        )
    return pd.DataFrame(rows)
