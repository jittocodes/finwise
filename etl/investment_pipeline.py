"""
etl/investment_pipeline.py
--------------------------
Apache Beam pipeline that reads the user's investment portfolio CSV/Excel,
enriches each holding with gain/loss calculations, and writes to ChromaDB.

Expected columns (flexible):
    Date | Asset | Type | Units | BuyPrice | CurrentPrice
    (Type: stock / mf / fd / gold / crypto / bond / real_estate)
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List

import apache_beam as beam
import pandas as pd
from loguru import logger

from config.settings import CHROMA_DIR, INVESTMENT_COLLECTION
from rag.store import get_chroma_collection, upsert_documents


# ── Column aliases ────────────────────────────────────────────────────────────
INVESTMENT_COLUMN_MAP = {
    "date": ["date", "purchase date", "investment date", "buy date"],
    "asset": ["asset", "stock", "symbol", "fund name", "instrument", "name"],
    "type": ["type", "asset type", "category", "instrument type"],
    "units": ["units", "quantity", "shares", "lots"],
    "buy_price": ["buyprice", "buy price", "purchase price", "avg price", "cost"],
    "current_price": ["currentprice", "current price", "ltp", "market price", "nav"],
    "sector": ["sector", "industry"],
}


# ── Beam DoFns ────────────────────────────────────────────────────────────────

class NormaliseInvestmentColumns(beam.DoFn):
    def process(self, row: Dict[str, Any]):
        row_lower = {k.lower().strip().replace(" ", ""): v for k, v in row.items()}
        normalised: Dict[str, Any] = {}
        for canonical, aliases in INVESTMENT_COLUMN_MAP.items():
            for alias in aliases:
                key = alias.replace(" ", "")
                if key in row_lower:
                    normalised[canonical] = row_lower[key]
                    break
            else:
                normalised[canonical] = None
        yield normalised


class EnrichInvestment(beam.DoFn):
    @staticmethod
    def _to_float(v) -> float:
        try:
            return float(str(v).replace(",", "").replace("₹", "").strip())
        except (ValueError, TypeError):
            return 0.0

    def process(self, row: Dict[str, Any]):
        units = self._to_float(row.get("units"))
        buy_price = self._to_float(row.get("buy_price"))
        current_price = self._to_float(row.get("current_price"))
        asset = str(row.get("asset") or "Unknown")
        asset_type = str(row.get("type") or "Unknown").lower()
        sector = str(row.get("sector") or "N/A")

        invested_value = units * buy_price
        current_value = units * current_price
        pnl = current_value - invested_value
        pnl_pct = (pnl / invested_value * 100) if invested_value > 0 else 0.0

        raw_date = str(row.get("date") or "")
        try:
            date_str = pd.to_datetime(raw_date, dayfirst=True).strftime("%Y-%m-%d")
        except Exception:
            date_str = raw_date

        enriched = {
            "id": str(uuid.uuid4()),
            "date": date_str,
            "asset": asset,
            "type": asset_type,
            "sector": sector,
            "units": units,
            "buy_price": buy_price,
            "current_price": current_price,
            "invested_value": invested_value,
            "current_value": current_value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        }

        direction = "profit" if pnl >= 0 else "loss"
        enriched["text"] = (
            f"Investment in {asset} ({asset_type}, sector: {sector}): "
            f"Purchased {units} units @ ₹{buy_price:,.2f} on {date_str}. "
            f"Current price ₹{current_price:,.2f}. "
            f"Invested ₹{invested_value:,.2f}, current value ₹{current_value:,.2f}. "
            f"P&L: ₹{pnl:,.2f} ({pnl_pct:.2f}% {direction})."
        )
        yield enriched


class WriteInvestmentsToChroma(beam.DoFn):
    def __init__(self, collection_name: str, chroma_dir: str):
        self.collection_name = collection_name
        self.chroma_dir = chroma_dir
        self._buffer: List[Dict] = []

    def setup(self):
        self._collection = get_chroma_collection(self.collection_name, self.chroma_dir)

    def process(self, row: Dict[str, Any]):
        self._buffer.append(row)
        if len(self._buffer) >= 50:
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
        logger.info(f"Flushed {len(self._buffer)} investments to ChromaDB")
        self._buffer.clear()


# ── Pipeline entry point ──────────────────────────────────────────────────────

def run_investment_pipeline(file_path: str) -> int:
    logger.info(f"Starting investment ETL pipeline for: {file_path}")
    path = Path(file_path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(how="all")
    rows = df.to_dict("records")
    logger.info(f"Loaded {len(rows)} investment rows")

    from apache_beam.options.pipeline_options import PipelineOptions
    options = PipelineOptions(runner="DirectRunner")

    with beam.Pipeline(options=options) as pipeline:
        (
            pipeline
            | "CreateRows" >> beam.Create(rows)
            | "NormaliseColumns" >> beam.ParDo(NormaliseInvestmentColumns())
            | "EnrichInvestment" >> beam.ParDo(EnrichInvestment())
            | "WriteToChroma"
            >> beam.ParDo(
                WriteInvestmentsToChroma(
                    collection_name=INVESTMENT_COLLECTION,
                    chroma_dir=str(CHROMA_DIR),
                )
            )
        )

    logger.success(f"Investment ETL pipeline complete – {len(rows)} rows processed")
    return len(rows)
