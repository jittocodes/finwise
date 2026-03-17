"""
rag/investment_rag.py
---------------------
LangChain retrieval chain for investment portfolio data.
"""
from __future__ import annotations
from typing import List
from langchain_core.documents import Document
from loguru import logger
from config.settings import CHROMA_DIR, INVESTMENT_COLLECTION
from rag.store import get_chroma_collection, get_langchain_vectorstore


def get_portfolio_summary() -> str:
    """Retrieve and summarise the investment portfolio for the LLM."""
    try:
        collection = get_chroma_collection(INVESTMENT_COLLECTION)
        count = collection.count()
        if count == 0:
            return "No investment data available yet. Please upload an investment portfolio file."

        results = collection.get(include=["documents", "metadatas"], limit=count)
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])

        type_totals: dict = {}
        sector_totals: dict = {}
        total_invested = 0.0
        total_current = 0.0

        for meta in metas:
            inv = float(meta.get("invested_value", 0) or 0)
            cur = float(meta.get("current_value", 0) or 0)
            atype = meta.get("type", "Other")
            sector = meta.get("sector", "N/A")
            type_totals[atype] = type_totals.get(atype, {"invested": 0, "current": 0})
            type_totals[atype]["invested"] += inv
            type_totals[atype]["current"] += cur
            sector_totals[sector] = sector_totals.get(sector, 0) + cur
            total_invested += inv
            total_current += cur

        total_pnl = total_current - total_invested
        pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

        lines = [
            f"=== Investment Portfolio Analysis ({count} holdings) ===",
            f"Total Invested: ₹{total_invested:,.2f}",
            f"Current Value: ₹{total_current:,.2f}",
            f"Overall P&L: ₹{total_pnl:,.2f} ({pnl_pct:.2f}%)",
            "",
            "By Asset Type:",
        ]
        for atype, vals in sorted(type_totals.items()):
            pnl = vals["current"] - vals["invested"]
            pct = (pnl / vals["invested"] * 100) if vals["invested"] > 0 else 0
            lines.append(
                f"  {atype.upper()}: Invested ₹{vals['invested']:,.2f} "
                f"→ Current ₹{vals['current']:,.2f} (P&L: {pct:+.2f}%)"
            )

        lines.append("\nSector Allocation (Current Value):")
        for sector, val in sorted(sector_totals.items(), key=lambda x: -x[1]):
            pct = (val / total_current * 100) if total_current > 0 else 0
            lines.append(f"  {sector}: ₹{val:,.2f} ({pct:.1f}%)")

        lines.append("\nIndividual Holdings:")
        for doc in docs:
            lines.append(f"  • {doc}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error reading investment RAG: {e}")
        return f"Error reading investment data: {e}"


def search_investments(query: str, k: int = 5) -> List[Document]:
    try:
        store = get_langchain_vectorstore(INVESTMENT_COLLECTION)
        return store.similarity_search(query, k=k)
    except Exception as e:
        logger.warning(f"Investment RAG search error: {e}")
        return []
