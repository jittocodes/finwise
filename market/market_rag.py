"""
market/market_rag.py
--------------------
Converts comprehensive live market data into rich RAG documents
and a detailed summary string for deep LLM analysis.
"""
from __future__ import annotations
from typing import Any, Dict, List
from loguru import logger
from config.settings import MARKET_COLLECTION, NEWS_COLLECTION
from market.fetcher import (fetch_alpha_vantage_news, fetch_market_overview, fetch_rbi_rates)
from rag.store import add_texts_to_store


def _stock_to_text(s: Dict) -> str:
    momentum = "bullish" if s["change_1m_pct"] > 2 else ("bearish" if s["change_1m_pct"] < -2 else "neutral")
    rsi_signal = "overbought" if s["rsi_14"] > 70 else ("oversold" if s["rsi_14"] < 30 else "neutral RSI")
    near_high = s.get("pct_from_52w_high", 0)
    return (
        f"Stock {s['name']} ({s['symbol']}) in {s['sector']} / {s['industry']}: "
        f"Price ₹{s['price']}, 1D {s['change_1d_pct']:+.1f}%, 1W {s['change_1w_pct']:+.1f}%, "
        f"1M {s['change_1m_pct']:+.1f}%, 3M {s['change_3m_pct']:+.1f}%. "
        f"PE={s['pe_ratio']}, Forward PE={s['forward_pe']}, PB={s['pb_ratio']}, "
        f"Beta={s['beta']}, ROE={s['roe']}%, D/E={s['debt_to_equity']}, "
        f"Revenue growth={s['revenue_growth']}%, Earnings growth={s['earnings_growth']}%. "
        f"Dividend yield={s['dividend_yield_pct']}%. "
        f"RSI(14)={s['rsi_14']} ({rsi_signal}). Momentum: {momentum}. "
        f"Market cap ₹{s['market_cap_cr']:,.0f} Cr. "
        f"{near_high:.1f}% from 52W high. 52W range: ₹{s['52w_low']}–₹{s['52w_high']}."
    )


def refresh_market_rag() -> str:
    logger.info("Refreshing comprehensive market RAG...")
    data = fetch_market_overview()
    rbi = fetch_rbi_rates()
    news = fetch_alpha_vantage_news()

    # Push stocks
    stock_texts = [_stock_to_text(s) for s in data.get("stocks", [])]
    if stock_texts:
        add_texts_to_store(MARKET_COLLECTION, stock_texts,
                           [{"source": "yfinance", "type": "stock"}] * len(stock_texts))
        logger.success(f"Indexed {len(stock_texts)} stocks into RAG")

    # Push indices
    idx_texts = []
    for name, d in data.get("indices", {}).items():
        idx_texts.append(
            f"Index {name}: level {d['price']}, 1D {d['change_1d_pct']:+.1f}%, "
            f"1M {d.get('change_1m_pct',0):+.1f}%, RSI {d.get('rsi_14',50):.0f}."
        )
    if idx_texts:
        add_texts_to_store(MARKET_COLLECTION, idx_texts,
                           [{"type": "index"}] * len(idx_texts))

    # Push news
    if news:
        news_texts = [f"[{n['sentiment']}] {n['title']}. {n['summary']}" for n in news]
        add_texts_to_store(NEWS_COLLECTION, news_texts,
                           [{"sentiment": n["sentiment"]} for n in news])

    return build_market_summary(data, rbi, news)


def build_market_summary(data: Dict, rbi: Dict, news: List) -> str:
    lines = [f"=== COMPREHENSIVE MARKET DATA ({data['fetched_at'][:19]}) ===", ""]

    # Indices
    lines.append("── INDIAN INDICES ──")
    for name, d in data.get("indices", {}).items():
        arrow = "▲" if d["change_1d_pct"] >= 0 else "▼"
        lines.append(f"  {name}: {d['price']:,} {arrow}{abs(d['change_1d_pct']):.2f}%  "
                     f"1M:{d.get('change_1m_pct',0):+.1f}%  RSI:{d.get('rsi_14',0):.0f}")

    # ALL Stocks — full detail for LLM
    lines.append("\n── NIFTY50 + MIDCAP STOCKS (Full Analysis) ──")
    for s in data.get("stocks", []):
        rsi_tag = "🔴OVERBOUGHT" if s["rsi_14"] > 70 else ("🟢OVERSOLD" if s["rsi_14"] < 30 else "⚪NEUTRAL")
        trend = "📈" if s["change_1m_pct"] > 2 else ("📉" if s["change_1m_pct"] < -2 else "➡️")
        lines.append(
            f"  {trend} {s['symbol']:18s} ₹{s['price']:>8.2f} | "
            f"1D:{s['change_1d_pct']:+5.1f}% 1M:{s['change_1m_pct']:+5.1f}% 3M:{s['change_3m_pct']:+6.1f}% | "
            f"PE:{s['pe_ratio']:5.1f} PB:{s['pb_ratio']:4.1f} Beta:{s['beta']:4.2f} "
            f"ROE:{s['roe']:5.1f}% Div:{s['dividend_yield_pct']:4.2f}% | "
            f"RSI:{s['rsi_14']:4.1f} {rsi_tag} | Mktcap:₹{s['market_cap_cr']:,.0f}Cr | "
            f"{s['sector']}"
        )

    # ETFs
    lines.append("\n── INDEX ETFs / MUTUAL FUND PROXIES ──")
    for name, d in data.get("etfs", {}).items():
        lines.append(f"  {name}: ₹{d['price']} | 1M:{d.get('change_1m_pct',0):+.1f}% | RSI:{d.get('rsi_14',0):.0f}")

    # Commodities
    lines.append("\n── COMMODITIES ──")
    for name, d in data.get("commodities", {}).items():
        lines.append(f"  {name}: {d['price']} | 1D:{d['change_1d_pct']:+.2f}% 1M:{d['change_1m_pct']:+.2f}%")

    # Global
    lines.append("\n── GLOBAL MARKETS ──")
    for name, d in data.get("global_markets", {}).items():
        lines.append(f"  {name}: {d['price']:,} | 1D:{d['change_1d_pct']:+.2f}% 1M:{d.get('change_1m_pct',0):+.2f}%")

    lines.append(f"\n── RBI POLICY RATES ──")
    lines.append(f"  Repo: {rbi['repo_rate']} | Rev Repo: {rbi['reverse_repo_rate']} | CRR: {rbi['crr']}")

    if news:
        lines.append("\n── FINANCIAL NEWS ──")
        for n in news[:8]:
            lines.append(f"  [{n['sentiment']:8s}] {n['title'][:90]}")

    return "\n".join(lines)
