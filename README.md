# 💹 FinWise – AI-Powered Investment Advisor

A production-grade, multi-file LangChain application that analyses your bank
statements and investment portfolio against live market data to give personalised
investment recommendations for Indian investors.

---

## Architecture

```
finwise/
├── config/
│   └── settings.py          ← Centralised env/config management
├── etl/
│   ├── bank_pipeline.py     ← Apache Beam: Bank CSV → ChromaDB
│   └── investment_pipeline.py ← Apache Beam: Investment CSV → ChromaDB
├── rag/
│   ├── store.py             ← ChromaDB helpers + HuggingFace embeddings
│   ├── bank_rag.py          ← Spending analysis retrieval
│   └── investment_rag.py    ← Portfolio retrieval
├── market/
│   ├── fetcher.py           ← yfinance + Alpha Vantage API
│   └── market_rag.py        ← Market context → ChromaDB + summary
├── advisor/
│   ├── chains.py            ← Model-agnostic LangChain chain factory
│   └── advisor.py           ← Main orchestrator
├── ui/
│   └── app.py               ← Gradio web interface
├── main.py                  ← Entry point
├── requirements.txt
└── .env.example
```

---

## Quick Start

### 1. Clone & Install

```bash
git clone <repo>
cd finwise
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set your LLM API key
```

### 3. Run

```bash
# Launch web UI (default port 7860)
python main.py

# Custom port with public share link
python main.py --port 8080 --share

# CLI demo with auto-generated sample data
python main.py --demo
```

Open `http://localhost:7860` in your browser.

---

## Model Agnostic – LLM Options

| Provider | `LLM_PROVIDER` | Cost | Notes |
|----------|--------------|------|-------|
| **Anthropic Claude** | `anthropic` | Paid | Best quality |
| **OpenAI GPT-4o** | `openai` | Paid | Alternative |
| **Ollama (local)** | `ollama` | Free | Llama3, Mistral, etc. |

Switch with a single env var — no code changes needed.

---

## Data Inputs

### Bank Statement CSV
```
Date,Description,Debit,Credit,Balance
01-Jan-2025,Salary credit,,100000,150000
05-Jan-2025,Swiggy food order,450,,149550
10-Jan-2025,HDFC EMI payment,25000,,124550
```

### Investment Portfolio CSV
```
Date,Asset,Type,Units,BuyPrice,CurrentPrice,Sector
01-Mar-2024,RELIANCE.NS,stock,10,2500,2950,Energy
01-Mar-2024,Axis Bluechip Fund,mf,500,45.5,52.3,Equity MF
01-Jan-2025,SGB Gold Bond,gold,5,6200,7100,Commodities
```

Supports flexible column names (most bank export formats work out of the box).

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| LLM orchestration | **LangChain** | Chains, memory, model-agnostic |
| Vector store | **ChromaDB** | Open-source, local, persistent |
| Embeddings | **sentence-transformers** | Free, no API key |
| ETL pipeline | **Apache Beam** | Scalable data processing |
| Market data | **yfinance** | Free Yahoo Finance API |
| News/sentiment | **Alpha Vantage** | Free tier available |
| UI | **Gradio** | Quick, polished web UI |

---

## Market Data Coverage

- **Indian Indices**: Nifty50, Sensex, Nifty Bank, Nifty IT, Nifty Midcap
- **Top Nifty50 Stocks**: Price, PE, beta, 52W range, sector
- **Commodities**: Gold, Silver, Crude Oil
- **Global Markets**: S&P 500, NASDAQ, Dow Jones
- **RBI Rates**: Repo, Reverse Repo, CRR, SLR
- **News Sentiment**: Via Alpha Vantage (optional)

---

## Spending Categories (Auto-detected)

Food & Dining · Shopping · Transport · Entertainment · Salary Income ·
Loan/EMI · Rent/Housing · Healthcare · Utilities · Investments · Cash · Transfers · Insurance

---

## Notes

- All RAG data is stored locally in `data/chroma_db/` (no cloud required)
- The embedding model (`all-MiniLM-L6-v2`) downloads automatically on first run
- Market data is live and requires internet connectivity
- Upload new CSVs each month — the ETL pipeline is incremental (upsert)
