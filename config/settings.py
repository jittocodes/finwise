"""
config/settings.py
------------------
Centralised configuration and environment management.
All secrets and tuneable parameters live here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma_db"

for d in [DATA_DIR, UPLOADS_DIR, CHROMA_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ── LLM Provider (model-agnostic) ────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
# Options: "anthropic" | "openai" | "ollama"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Model names per provider
LLM_MODELS = {
    "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
    "openai": os.getenv("OPENAI_MODEL", "gpt-4o"),
    "ollama": OLLAMA_MODEL,
}


# ── Embeddings (open-source, no API key) ─────────────────────────────────────
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "all-MiniLM-L6-v2"
)  # sentence-transformers


# ── Market Data APIs ──────────────────────────────────────────────────────────
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "demo")
# yfinance is free, no key needed


# ── ChromaDB Collections ──────────────────────────────────────────────────────
BANK_COLLECTION = "bank_transactions"
INVESTMENT_COLLECTION = "investments"
MARKET_COLLECTION = "market_context"
NEWS_COLLECTION = "financial_news"


# ── ETL Settings ──────────────────────────────────────────────────────────────
CHUNK_SIZE = 500          # Characters per RAG chunk
CHUNK_OVERLAP = 50


class UserFinancials(BaseModel):
    """Structured input for user's monthly financial profile."""
    monthly_salary: float = Field(..., description="Monthly take-home salary (INR)")
    monthly_emis: float = Field(default=0.0, description="Total monthly EMIs (INR)")
    monthly_expenses: float = Field(default=0.0, description="Estimated monthly expenses (INR)")

    @property
    def monthly_investable(self) -> float:
        return max(0.0, self.monthly_salary - self.monthly_emis - self.monthly_expenses)
