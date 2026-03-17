# 💹 FinWise — AI-Powered Investment Advisor

> Analyses your bank statements, scans every Nifty50 stock in real time, and tells you exactly where to put your money — ₹2,000 here, ₹5,000 there — with PE ratios, RSI signals, and sector outlook as the reasoning.

```
Built with Claude (Anthropic) · LangChain · Apache Beam · ChromaDB · yfinance · Gradio
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          DATA SOURCES                               │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │  Bank Statement │  │   Investment    │  │    Live Market      │ │
│  │   CSV / Excel   │  │  Portfolio CSV  │  │  yfinance · 60 stks │ │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘ │
└───────────┼────────────────────┼─────────────────────┼────────────┘
            │                    │                      │
            ▼                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           ETL LAYER                                 │
│                                                                     │
│  ┌──────────────────────┐  ┌──────────────────────┐                 │
│  │   Apache Beam ETL    │  │   Apache Beam ETL    │                 │
│  │  Normalise columns   │  │  Enrich P&L · Sector │                 │
│  │  Auto-categorise txn │  │  Gain/loss per hold  │                 │
│  │  13 spend categories │  │  Asset type mapping  │                 │
│  └──────────┬───────────┘  └──────────┬───────────┘                 │
└─────────────┼──────────────────────────┼────────────────────────────┘
              │                          │
              ▼                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ChromaDB  ·  Local Vector Store                  │
│          open-source · persists to disk · no cloud needed           │
│                                                                     │
│   Embeddings: sentence-transformers/all-MiniLM-L6-v2 (free, local) │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ bank_transactions│  │   investments    │  │  market_context  │  │
│  │  spending RAG    │  │  portfolio RAG   │  │  live data RAG   │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │  all 3 collections
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      LangChain Advisor Chain                        │
│                                                                     │
│   Bank RAG + Portfolio RAG + Market RAG → single structured prompt  │
│   Forces per-stock ₹ allocation · ranks all 60 opportunities        │
│   STCG/LTCG tax notes · 30/60/90 day action plan                    │
│                                                                     │
│   MODEL AGNOSTIC — switch with one env var:                         │
│   ┌────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│   │  Claude (Ant.) │  │  GPT-4o (OpenAI)│  │  Ollama (local) │     │
│   │  ANTHROPIC_API │  │  OPENAI_API_KEY │  │  free · no key  │     │
│   └────────────────┘  └─────────────────┘  └─────────────────┘     │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Gradio UI  ·  Dark Terminal Theme                │
│                                                                     │
│   Upload  │  Monthly Profile  │  Investment Advice  │  Chat        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## What It Does

Upload your bank statement and portfolio CSV each month. Enter your salary, EMIs, and expenses. FinWise scans every Nifty50 + Midcap stock in real time and produces output like:

```
╔══ HDFCBANK.NS ═══════════════════════════════════════════╗
║  Invest: ₹3,000 this month                               ║
║  Why: PE 18.2 (below 5Y avg), RSI 41 (oversold),        ║
║       rate-cut tailwind for banking sector               ║
║  Entry target: ₹1,680  (current: ₹1,720)                ║
║  Expected 12M return: 14–18%                             ║
║  Risk: Medium  |  Tax: LTCG after 1 year                 ║
╚══════════════════════════════════════════════════════════╝
```

Per stock it receives: `Price · PE · Forward PE · PB · Beta · ROE · D/E · Revenue growth · Earnings growth · RSI(14) · Dividend yield · 1D/1W/1M/3M momentum · % from 52W high`

---

## File Structure

```
finwise/
├── config/
│   └── settings.py            # env vars, LLM provider, collection names
├── etl/
│   ├── bank_pipeline.py       # Apache Beam: bank CSV → ChromaDB
│   └── investment_pipeline.py # Apache Beam: portfolio CSV → ChromaDB
├── rag/
│   ├── store.py               # ChromaDB + HuggingFace embeddings
│   ├── bank_rag.py            # spending analysis retrieval
│   └── investment_rag.py      # portfolio P&L retrieval
├── market/
│   ├── fetcher.py             # yfinance: full Nifty50 scan + indices
│   └── market_rag.py          # market context → ChromaDB + summary
├── advisor/
│   ├── chains.py              # model-agnostic LangChain chain factory
│   └── advisor.py             # main orchestrator (RAG → LLM → advice)
├── ui/
│   └── app.py                 # Gradio dark-terminal web interface
├── main.py                    # entry point
├── requirements.txt
└── .env.example
```

---

## Quick Start

```bash
# 1. Install
git clone <repo>
cd finwise
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Add your LLM API key (see LLM options below)

# 3. Run
python main.py
# → opens at http://localhost:7860

# CLI demo with auto-generated sample data
python main.py --demo
```

---

## LLM Options — One Env Var

| Provider | `LLM_PROVIDER=` | Cost | Setup |
|---|---|---|---|
| **Anthropic Claude** | `anthropic` | Paid | `ANTHROPIC_API_KEY=sk-ant-...` |
| **OpenAI GPT-4o** | `openai` | Paid | `OPENAI_API_KEY=sk-...` |
| **Ollama (local)** | `ollama` | Free | `ollama pull llama3` |

No code changes. Switch providers by editing one line in `.env`.

---

## Input Formats

### Bank Statement CSV
```
Date,Description,Debit,Credit,Balance
01-Jan-2025,Salary credit,,100000,150000
05-Jan-2025,Swiggy food order,450,,149550
10-Jan-2025,HDFC Home Loan EMI,25000,,124550
20-Jan-2025,Zerodha SIP - Axis Bluechip,5000,,116350
```
Column names are flexible — the ETL pipeline recognises most Indian bank export formats (HDFC, SBI, ICICI, Kotak, Axis).

### Investment Portfolio CSV
```
Date,Asset,Type,Units,BuyPrice,CurrentPrice,Sector
01-Mar-2024,RELIANCE.NS,stock,10,2500,2950,Energy
01-Mar-2024,Axis Bluechip Fund,mf,500,45.5,52.3,Equity MF
01-Jan-2025,SGB Gold Bond,gold,5,6200,7100,Commodities
15-Feb-2025,NIFTYBEES.NS,etf,100,220,235,Index ETF
```

Supported asset types: `stock` · `mf` · `etf` · `fd` · `gold` · `bond` · `real_estate`

---

## Market Coverage

| Category | What's fetched |
|---|---|
| Indian indices | Nifty50, Sensex, Bank Nifty, Nifty IT, Nifty Midcap, FMCG, Pharma, Auto, Metal |
| Stocks | Full Nifty50 universe + 10 Midcap picks (60 total) |
| Per-stock data | PE, Forward PE, PB, Beta, ROE, D/E, revenue growth, earnings growth, RSI(14), dividend yield, 1D/1W/1M/3M momentum, % from 52W high |
| ETFs | NIFTYBEES, BANKBEES, GOLDBEES, ITBEES, MIDCAPETF |
| Commodities | Gold, Silver, Crude Oil WTI, Natural Gas |
| Global markets | S&P 500, NASDAQ 100, Dow Jones, Hang Seng, Nikkei 225, FTSE 100, VIX |
| Macro | RBI Repo rate, Reverse Repo, CRR |
| News sentiment | Alpha Vantage (optional free key) |

---

## Auto-detected Spending Categories

`Food & Dining` · `Shopping` · `Transport` · `Entertainment` · `Salary Income` · `Loan / EMI` · `Rent / Housing` · `Healthcare` · `Utilities` · `Investments` · `Cash` · `Transfers` · `Insurance`

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM orchestration | **LangChain** | Chains, memory, model-agnostic |
| Vector store | **ChromaDB** | Open-source, fully local |
| Embeddings | **sentence-transformers** | Free, no API key, runs on CPU |
| ETL pipeline | **Apache Beam** | Scalable, handles large CSVs |
| Market data | **yfinance** | Free Yahoo Finance API |
| News/sentiment | **Alpha Vantage** | Free tier (optional) |
| UI | **Gradio** | Fast to ship, looks great |

---

## Environment Variables

```bash
# .env

# LLM (pick one)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
# OPENAI_API_KEY=sk-your-key-here
# OLLAMA_MODEL=llama3

# Market news (optional — get free key at alphavantage.co)
ALPHA_VANTAGE_KEY=demo

# Embeddings — open-source, downloads automatically on first run
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

---

## Disclaimer

This is a personal open-source project for educational purposes. Nothing here constitutes financial advice. Always do your own research before investing.

---

*Built with significant AI assistance (Claude by Anthropic). The architecture decisions, domain logic, and prompt engineering are the author's own.*