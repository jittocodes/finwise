"""
etl/bank_pipeline.py
--------------------
Apache Beam pipeline that reads bank-statement CSV/Excel files,
cleans and enriches each transaction, then writes documents to
ChromaDB for RAG retrieval.

Expected CSV columns (flexible – mapped via COLUMN_MAP):
    Date | Description | Debit | Credit | Balance
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import apache_beam as beam
import pandas as pd
from apache_beam.options.pipeline_options import PipelineOptions
from loguru import logger

from config.settings import BANK_COLLECTION, CHROMA_DIR, CHUNK_SIZE
from rag.store import get_chroma_collection, upsert_documents


# ── Column name aliases ───────────────────────────────────────────────────────
COLUMN_MAP = {
    "date": ["date", "transaction date", "txn date", "value date"],
    "description": ["description", "narration", "particulars", "details", "remarks"],
    "debit": ["debit", "withdrawal", "dr", "amount (dr)"],
    "credit": ["credit", "deposit", "cr", "amount (cr)"],
    "balance": ["balance", "closing balance", "running balance"],
}

# Spending categories (keyword → category)
CATEGORY_RULES: List[tuple] = [
    (r"swiggy|zomato|uber eats|food|restaurant|cafe|pizza|burger", "Food & Dining"),
    (r"amazon|flipkart|myntra|meesho|shopping|mart|store", "Shopping"),
    (r"ola|uber|rapido|petrol|fuel|parking|metro|irctc|bus", "Transport"),
    (r"netflix|prime|spotify|hotstar|youtube|game|entertainment", "Entertainment"),
    (r"salary|payroll|stipend|wages", "Salary Income"),
    (r"emi|loan|mortgage|equitas|hdfc loan|icici loan", "Loan / EMI"),
    (r"rent|pg|accommodation|housing", "Rent / Housing"),
    (r"hospital|pharmacy|medicine|health|apollo|max|medplus", "Healthcare"),
    (r"electricity|water|gas|internet|broadband|jio|airtel|bsnl", "Utilities"),
    (r"zerodha|groww|upstox|mutual fund|mf|sip|nse|bse|stock", "Investments"),
    (r"atm|cash withdrawal|cash deposit", "Cash"),
    (r"transfer|neft|rtgs|imps|upi", "Transfers"),
    (r"insurance|lic|term plan|health cover", "Insurance"),
]


# ── Beam DoFns ────────────────────────────────────────────────────────────────

class NormaliseColumns(beam.DoFn):
    """Rename columns to canonical names regardless of source bank format."""

    def process(self, row: Dict[str, Any]):
        normalised: Dict[str, Any] = {}
        row_lower = {k.lower().strip(): v for k, v in row.items()}

        for canonical, aliases in COLUMN_MAP.items():
            for alias in aliases:
                if alias in row_lower:
                    normalised[canonical] = row_lower[alias]
                    break
            else:
                normalised[canonical] = None

        # Carry through any extra columns
        for k, v in row_lower.items():
            if k not in {a for aliases in COLUMN_MAP.values() for a in aliases}:
                normalised[k] = v

        yield normalised


class CleanAndEnrich(beam.DoFn):
    """Parse types, derive amount, categorise, build text summary."""

    @staticmethod
    def _parse_amount(value) -> float:
        if value is None or str(value).strip() in ("", "-", "nan"):
            return 0.0
        cleaned = re.sub(r"[^\d.]", "", str(value))
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    @staticmethod
    def _categorise(description: str) -> str:
        desc_lower = (description or "").lower()
        for pattern, category in CATEGORY_RULES:
            if re.search(pattern, desc_lower):
                return category
        return "Other"

    def process(self, row: Dict[str, Any]):
        debit = self._parse_amount(row.get("debit"))
        credit = self._parse_amount(row.get("credit"))
        balance = self._parse_amount(row.get("balance"))
        description = str(row.get("description") or "")
        category = self._categorise(description)
        txn_type = "credit" if credit > 0 else "debit"
        amount = credit if credit > 0 else debit

        # Parse date
        raw_date = str(row.get("date") or "")
        try:
            date_obj = pd.to_datetime(raw_date, dayfirst=True)
            date_str = date_obj.strftime("%Y-%m-%d")
            month = date_obj.strftime("%B %Y")
        except Exception:
            date_str = raw_date
            month = "Unknown"

        enriched = {
            "id": str(uuid.uuid4()),
            "date": date_str,
            "month": month,
            "description": description,
            "category": category,
            "type": txn_type,
            "amount": amount,
            "debit": debit,
            "credit": credit,
            "balance": balance,
        }

        # Build human-readable text for embedding
        enriched["text"] = (
            f"On {date_str}, {txn_type} of ₹{amount:,.2f} "
            f"for '{description}' categorised as '{category}'. "
            f"Balance after transaction: ₹{balance:,.2f}."
        )
        yield enriched


class WriteToChroma(beam.DoFn):
    """Batch-write enriched transactions to ChromaDB."""

    def __init__(self, collection_name: str, chroma_dir: str):
        self.collection_name = collection_name
        self.chroma_dir = chroma_dir
        self._buffer: List[Dict] = []
        self._batch_size = 100

    def setup(self):
        self._collection = get_chroma_collection(
            self.collection_name, self.chroma_dir
        )

    def process(self, row: Dict[str, Any]):
        self._buffer.append(row)
        if len(self._buffer) >= self._batch_size:
            self._flush()

    def finish_bundle(self):
        if self._buffer:
            self._flush()

    def _flush(self):
        upsert_documents(
            collection=self._collection,
            documents=[r["text"] for r in self._buffer],
            ids=[r["id"] for r in self._buffer],
            metadatas=[
                {k: str(v) for k, v in r.items() if k not in ("text", "id")}
                for r in self._buffer
            ],
        )
        logger.info(f"Flushed {len(self._buffer)} bank transactions to ChromaDB")
        self._buffer.clear()


# ── Pipeline entry point ──────────────────────────────────────────────────────

def load_file_to_dicts(file_path: str) -> List[Dict]:
    """Read CSV or Excel and return list of row dicts."""
    path = Path(file_path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(how="all")
    return df.to_dict("records")


def run_bank_pipeline(file_path: str) -> int:
    """
    Run the bank statement ETL pipeline.

    Parameters
    ----------
    file_path : str
        Path to bank statement CSV or Excel file.

    Returns
    -------
    int
        Number of transactions processed.
    """
    logger.info(f"Starting bank ETL pipeline for: {file_path}")
    rows = load_file_to_dicts(file_path)
    logger.info(f"Loaded {len(rows)} raw rows")

    options = PipelineOptions(runner="DirectRunner")

    with beam.Pipeline(options=options) as pipeline:
        (
            pipeline
            | "CreateRows" >> beam.Create(rows)
            | "NormaliseColumns" >> beam.ParDo(NormaliseColumns())
            | "CleanAndEnrich" >> beam.ParDo(CleanAndEnrich())
            | "WriteToChroma"
            >> beam.ParDo(
                WriteToChroma(
                    collection_name=BANK_COLLECTION,
                    chroma_dir=str(CHROMA_DIR),
                )
            )
        )

    logger.success(f"Bank ETL pipeline complete – {len(rows)} rows processed")
    return len(rows)
