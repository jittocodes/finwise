"""
market/fetcher.py
-----------------
Comprehensive market data fetcher — scans ALL Nifty50 stocks with
full fundamental + technical data for deep per-stock analysis.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import yfinance as yf
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import ALPHA_VANTAGE_KEY

# ── Full Nifty50 universe ─────────────────────────────────────────────────────
NIFTY50_UNIVERSE = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
    "HINDUNILVR.NS","SBIN.NS","BHARTIARTL.NS","ITC.NS","KOTAKBANK.NS",
    "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","BAJFINANCE.NS",
    "WIPRO.NS","HCLTECH.NS","ULTRACEMCO.NS","TITAN.NS","NESTLEIND.NS",
    "POWERGRID.NS","NTPC.NS","TECHM.NS","SUNPHARMA.NS","DRREDDY.NS",
    "DIVISLAB.NS","BAJAJFINSV.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS","ONGC.NS",
    "COALINDIA.NS","TATAMOTORS.NS","TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS",
    "INDUSINDBK.NS","M&M.NS","EICHERMOT.NS","BRITANNIA.NS","CIPLA.NS",
    "APOLLOHOSP.NS","ADANIPORTS.NS","ADANIENT.NS","BPCL.NS","GRASIM.NS",
    "SBILIFE.NS","HDFCLIFE.NS","UPL.NS","TATACONSUM.NS","VEDL.NS",
]

NIFTY_MIDCAP_PICKS = [
    "PERSISTENT.NS","MPHASIS.NS","IRFC.NS","POLICYBZR.NS","NAUKRI.NS",
    "DELHIVERY.NS","ZOMATO.NS","PAYTM.NS","MARICO.NS","PIDILITIND.NS",
]

INDICES = {
    "NIFTY_50": "^NSEI",
    "SENSEX": "^BSESN",
    "NIFTY_BANK": "^NSEBANK",
    "NIFTY_IT": "^CNXIT",
    "NIFTY_MIDCAP50": "^NSEMDCP50",
    "NIFTY_FMCG": "NIFTYFMCG.NS",
    "NIFTY_PHARMA": "^CNXPHARMA",
    "NIFTY_AUTO": "^CNXAUTO",
    "NIFTY_METAL": "^CNXMETAL",
    "NIFTY_REALTY": "^CNXREALTY",
}

COMMODITIES = {
    "GOLD_USD": "GC=F",
    "SILVER_USD": "SI=F",
    "CRUDE_OIL_WTI": "CL=F",
    "NATURAL_GAS": "NG=F",
}

GLOBAL_INDICES = {
    "S&P_500": "^GSPC",
    "NASDAQ_100": "^NDX",
    "DOW_JONES": "^DJI",
    "HANG_SENG": "^HSI",
    "NIKKEI_225": "^N225",
    "FTSE_100": "^FTSE",
    "VIX_FEAR_INDEX": "^VIX",
}

MUTUAL_FUND_PROXIES = {
    "NIFTY50_ETF": "NIFTYBEES.NS",
    "BANK_ETF": "BANKBEES.NS",
    "GOLD_ETF": "GOLDBEES.NS",
    "IT_ETF": "ITBEES.NS",
    "MIDCAP_ETF": "MIDCAPETF.NS",
}


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
def _fetch_single(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="3mo")
        if hist.empty:
            return None
        info = t.info or {}

        price_now = float(hist["Close"].iloc[-1])
        price_1d = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price_now
        price_1w = float(hist["Close"].iloc[-5]) if len(hist) > 5 else price_now
        price_1m = float(hist["Close"].iloc[-22]) if len(hist) > 22 else price_now
        price_3m = float(hist["Close"].iloc[0])

        volume_avg = float(hist["Volume"].tail(10).mean()) if "Volume" in hist else 0

        # Simple RSI (14-day)
        delta = hist["Close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-9)
        rsi = float((100 - 100 / (1 + rs)).iloc[-1]) if len(hist) >= 14 else 50.0

        def chg(old, new):
            return round((new - old) / old * 100, 2) if old > 0 else 0.0

        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector") or info.get("category") or "N/A",
            "industry": info.get("industry", "N/A"),
            "price": round(price_now, 2),
            "change_1d_pct": chg(price_1d, price_now),
            "change_1w_pct": chg(price_1w, price_now),
            "change_1m_pct": chg(price_1m, price_now),
            "change_3m_pct": chg(price_3m, price_now),
            "pe_ratio": round(info.get("trailingPE") or 0, 1),
            "forward_pe": round(info.get("forwardPE") or 0, 1),
            "pb_ratio": round(info.get("priceToBook") or 0, 2),
            "market_cap_cr": round((info.get("marketCap") or 0) / 1e7, 0),
            "52w_high": info.get("fiftyTwoWeekHigh") or price_now,
            "52w_low": info.get("fiftyTwoWeekLow") or price_now,
            "dividend_yield_pct": round((info.get("dividendYield") or 0) * 100, 2),
            "beta": round(info.get("beta") or 1.0, 2),
            "roe": round((info.get("returnOnEquity") or 0) * 100, 1),
            "debt_to_equity": round(info.get("debtToEquity") or 0, 2),
            "revenue_growth": round((info.get("revenueGrowth") or 0) * 100, 1),
            "earnings_growth": round((info.get("earningsGrowth") or 0) * 100, 1),
            "rsi_14": round(rsi, 1),
            "avg_volume_10d": int(volume_avg),
            "pct_from_52w_high": round((price_now - info.get("fiftyTwoWeekHigh", price_now))
                                       / (info.get("fiftyTwoWeekHigh", price_now) or 1) * 100, 1),
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.debug(f"Skip {symbol}: {e}")
        return None


def fetch_all_stocks(include_midcap: bool = True) -> List[Dict]:
    """Fetch full fundamental + technical data for entire Nifty50 universe."""
    universe = NIFTY50_UNIVERSE + (NIFTY_MIDCAP_PICKS if include_midcap else [])
    logger.info(f"Fetching {len(universe)} stocks...")
    results = []
    for i, sym in enumerate(universe):
        data = _fetch_single(sym)
        if data:
            results.append(data)
        if i % 10 == 9:
            logger.info(f"  {i+1}/{len(universe)} fetched...")
            time.sleep(0.5)   # polite rate limiting
    logger.success(f"Fetched {len(results)}/{len(universe)} stocks")
    return results


def fetch_indices() -> Dict[str, Any]:
    out = {}
    for name, sym in INDICES.items():
        d = _fetch_single(sym)
        if d:
            out[name] = d
    return out


def fetch_commodities() -> Dict[str, Any]:
    out = {}
    for name, sym in COMMODITIES.items():
        d = _fetch_single(sym)
        if d:
            out[name] = {"price": d["price"], "change_1d_pct": d["change_1d_pct"],
                         "change_1m_pct": d["change_1m_pct"], "rsi_14": d["rsi_14"]}
    return out


def fetch_global_indices() -> Dict[str, Any]:
    out = {}
    for name, sym in GLOBAL_INDICES.items():
        d = _fetch_single(sym)
        if d:
            out[name] = {"price": d["price"], "change_1d_pct": d["change_1d_pct"],
                         "change_1m_pct": d["change_1m_pct"]}
    return out


def fetch_etfs() -> Dict[str, Any]:
    out = {}
    for name, sym in MUTUAL_FUND_PROXIES.items():
        d = _fetch_single(sym)
        if d:
            out[name] = d
    return out


def fetch_market_overview() -> Dict[str, Any]:
    logger.info("Fetching comprehensive market overview...")
    return {
        "fetched_at": datetime.now().isoformat(),
        "stocks": fetch_all_stocks(include_midcap=True),
        "indices": fetch_indices(),
        "commodities": fetch_commodities(),
        "global_markets": fetch_global_indices(),
        "etfs": fetch_etfs(),
    }


def fetch_rbi_rates() -> Dict[str, str]:
    return {
        "repo_rate": "6.50%",
        "reverse_repo_rate": "3.35%",
        "crr": "4.50%",
        "note": "Source: RBI. Update from https://www.rbi.org.in if changed.",
    }


def fetch_alpha_vantage_news() -> List[Dict]:
    if ALPHA_VANTAGE_KEY in ("demo", ""):
        return []
    try:
        url = (f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT"
               f"&topics=economy_fiscal,earnings,financial_markets"
               f"&apikey={ALPHA_VANTAGE_KEY}")
        resp = requests.get(url, timeout=15)
        items = resp.json().get("feed", [])[:15]
        return [{"title": i.get("title",""), "summary": i.get("summary","")[:200],
                 "sentiment": i.get("overall_sentiment_label","Neutral"),
                 "source": i.get("source","")} for i in items]
    except Exception as e:
        logger.warning(f"News fetch failed: {e}")
        return []
