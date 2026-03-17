"""
rag/bank_rag.py
---------------
LangChain retrieval chain for bank transaction data.
Provides spending analysis summaries from ChromaDB.
"""
from __future__ import annotations
from typing import List
import chromadb
from langchain_core.documents import Document
from loguru import logger
from config.settings import BANK_COLLECTION, CHROMA_DIR
from rag.store import get_chroma_collection, get_langchain_vectorstore


def get_spending_summary(top_k: int = 30) -> str:
    """Retrieve top transactions and summarise into a text block for the LLM."""
    try:
        collection = get_chroma_collection(BANK_COLLECTION)
        count = collection.count()
        if count == 0:
            return "No bank transaction data available yet. Please upload a bank statement."

        results = collection.get(include=["documents", "metadatas"], limit=min(top_k, count))
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])

        # Aggregate by category
        category_totals: dict = {}
        monthly_totals: dict = {}
        total_debit = 0.0
        total_credit = 0.0

        for doc, meta in zip(docs, metas):
            cat = meta.get("category", "Other")
            month = meta.get("month", "Unknown")
            debit = float(meta.get("debit", 0) or 0)
            credit = float(meta.get("credit", 0) or 0)
            category_totals[cat] = category_totals.get(cat, 0.0) + debit
            monthly_totals[month] = monthly_totals.get(month, {})
            monthly_totals[month]["debit"] = monthly_totals[month].get("debit", 0) + debit
            monthly_totals[month]["credit"] = monthly_totals[month].get("credit", 0) + credit
            total_debit += debit
            total_credit += credit

        lines = [
            f"=== Bank Statement Analysis ({count} transactions) ===",
            f"Total Credits (Income): ₹{total_credit:,.2f}",
            f"Total Debits (Spending): ₹{total_debit:,.2f}",
            "",
            "Spending by Category:",
        ]
        for cat, amt in sorted(category_totals.items(), key=lambda x: -x[1]):
            pct = (amt / total_debit * 100) if total_debit > 0 else 0
            lines.append(f"  {cat}: ₹{amt:,.2f} ({pct:.1f}%)")

        lines.append("\nMonthly Summary:")
        for month, totals in sorted(monthly_totals.items()):
            lines.append(
                f"  {month} — Credit: ₹{totals['credit']:,.2f} | Debit: ₹{totals['debit']:,.2f}"
            )

        lines.append("\nSample Transactions:")
        for doc in docs[:10]:
            lines.append(f"  • {doc}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error reading bank RAG: {e}")
        return f"Error reading bank data: {e}"


def search_transactions(query: str, k: int = 5) -> List[Document]:
    """Semantic search over bank transactions."""
    try:
        store = get_langchain_vectorstore(BANK_COLLECTION)
        return store.similarity_search(query, k=k)
    except Exception as e:
        logger.warning(f"Bank RAG search error: {e}")
        return []
