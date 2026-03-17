"""
ui/app.py
---------
FinWise — luxury dark terminal UI with animated allocation cards,
live market ticker, and deep per-stock advice rendering.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Tuple

import gradio as gr
from loguru import logger

from advisor.advisor import FinWiseAdvisor
from config.settings import UPLOADS_DIR, UserFinancials
from etl.bank_pipeline import run_bank_pipeline
from etl.investment_pipeline import run_investment_pipeline

_advisor = FinWiseAdvisor()

# ── Handlers ──────────────────────────────────────────────────────────────────

def _save(file_obj) -> str:
    src = Path(file_obj.name)
    dst = UPLOADS_DIR / src.name
    shutil.copy(src, dst)
    return str(dst)


def process_bank(f):
    if f is None:
        return "⚠ No file uploaded"
    try:
        n = run_bank_pipeline(_save(f))
        return f"✅ {n} transactions indexed"
    except Exception as e:
        return f"❌ {e}"


def process_inv(f):
    if f is None:
        return "⚠ No file uploaded"
    try:
        n = run_investment_pipeline(_save(f))
        return f"✅ {n} holdings indexed"
    except Exception as e:
        return f"❌ {e}"


def refresh_mkt():
    try:
        from market.market_rag import refresh_market_rag
        summary = refresh_market_rag()
        lines = summary.split("\n")
        preview = "\n".join(lines[:60])
        return preview, summary
    except Exception as e:
        return f"❌ {e}", ""


def generate(bank_f, inv_f, salary, emis, expenses, question, mkt_full, progress=gr.Progress()):
    log = []
    progress(0.05, desc="Processing files…")

    if bank_f:
        log.append(process_bank(bank_f))
    if inv_f:
        log.append(process_inv(inv_f))

    try:
        fin = UserFinancials(
            monthly_salary=float(salary or 0),
            monthly_emis=float(emis or 0),
            monthly_expenses=float(expenses or 0),
        )
    except Exception as e:
        return f"❌ Bad inputs: {e}", "\n".join(log)

    progress(0.2, desc="Building RAG context…")
    _advisor.prepare_context(
        financials=fin,
        refresh_market=(not mkt_full),
        market_summary_override=mkt_full if mkt_full else None,
    )

    q = question.strip() or (
        "Give me a comprehensive investment plan. Analyse every single stock and ETF in the "
        "market data. For each recommended instrument, tell me the EXACT ₹ amount to invest "
        "this month. Rank all opportunities. Cover stocks, SIPs, ETFs, gold, and debt."
    )

    progress(0.5, desc="AI analysing all stocks…")
    advice = _advisor.generate_advice(q)
    progress(1.0, desc="Done")
    log.append("✅ Deep analysis complete")
    return advice, "\n".join(log)


def chat(msg, history):
    if not msg.strip():
        return "", history
    r = _advisor.chat(msg)
    history.append((msg, r))
    return "", history


def reset():
    _advisor.reset_session()
    return "> ↺ Session cleared. Upload data and run analysis again.", "Session cleared ✓"


# ── CSS / Theme ───────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg: #080c10;
    --surface: #0d1117;
    --surface2: #161b22;
    --border: #21262d;
    --accent: #00d4aa;
    --accent2: #f7c948;
    --accent3: #ff6b6b;
    --accent4: #7c6af5;
    --text: #e6edf3;
    --muted: #8b949e;
    --green: #3fb950;
    --red: #f85149;
    --glow: 0 0 20px rgba(0,212,170,0.15);
    --font-display: 'Syne', sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; }
body, .gradio-container {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: var(--font-display) !important;
}

/* Animated grid background */
.gradio-container::before {
    content: '';
    position: fixed; inset: 0; z-index: 0;
    background-image:
        linear-gradient(rgba(0,212,170,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,212,170,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
}

/* Hero header */
.fw-hero {
    position: relative;
    padding: 48px 40px 40px;
    background: linear-gradient(135deg, #0a1628 0%, #0d1117 50%, #0a1628 100%);
    border-bottom: 1px solid var(--border);
    overflow: hidden;
    margin-bottom: 0;
}
.fw-hero::after {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(0,212,170,0.08) 0%, transparent 70%);
    pointer-events: none;
}
.fw-hero-title {
    font-size: 3rem;
    font-weight: 800;
    letter-spacing: -1px;
    background: linear-gradient(90deg, #00d4aa 0%, #7c6af5 50%, #f7c948 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
    margin-bottom: 8px;
}
.fw-hero-sub {
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    letter-spacing: 2px;
    text-transform: uppercase;
}
.fw-badge {
    display: inline-block;
    background: rgba(0,212,170,0.1);
    border: 1px solid rgba(0,212,170,0.3);
    color: var(--accent);
    font-family: var(--font-mono);
    font-size: 0.7rem;
    padding: 3px 10px;
    border-radius: 20px;
    margin-right: 8px;
    margin-top: 12px;
}

/* Tabs */
.tab-nav { background: var(--surface) !important; border-bottom: 1px solid var(--border) !important; }
.tab-nav button {
    font-family: var(--font-display) !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    color: var(--muted) !important;
    border-radius: 0 !important;
    padding: 14px 20px !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.2s !important;
}
.tab-nav button.selected {
    color: var(--accent) !important;
    border-bottom-color: var(--accent) !important;
    background: transparent !important;
}

/* Panels */
.fw-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
}
.fw-panel-title {
    font-size: 0.7rem;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--accent);
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.fw-panel-title::before {
    content: '';
    width: 6px; height: 6px;
    background: var(--accent);
    border-radius: 50%;
    box-shadow: 0 0 8px var(--accent);
}

/* Metric cards */
.fw-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.fw-metric {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    text-align: center;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.fw-metric:hover { border-color: var(--accent); box-shadow: var(--glow); }
.fw-metric-val {
    font-family: var(--font-mono);
    font-size: 1.4rem;
    font-weight: 500;
    color: var(--accent);
    display: block;
}
.fw-metric-label { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

/* Inputs */
label { color: var(--muted) !important; font-size: 0.75rem !important; font-family: var(--font-mono) !important;
        text-transform: uppercase !important; letter-spacing: 1px !important; }
input[type=number], input[type=text], textarea, .gr-textbox textarea {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.9rem !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
input:focus, textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(0,212,170,0.1) !important;
    outline: none !important;
}

/* File upload */
.gr-file-upload { background: var(--surface2) !important; border: 1px dashed var(--border) !important;
                  border-radius: 10px !important; transition: border-color 0.2s !important; }
.gr-file-upload:hover { border-color: var(--accent) !important; }

/* Buttons */
.gr-button {
    font-family: var(--font-display) !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    border-radius: 8px !important;
    transition: all 0.2s !important;
    letter-spacing: 0.5px !important;
}
.gr-button-primary {
    background: linear-gradient(135deg, #00d4aa, #00b896) !important;
    border: none !important;
    color: #080c10 !important;
    box-shadow: 0 4px 15px rgba(0,212,170,0.3) !important;
}
.gr-button-primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(0,212,170,0.4) !important;
}
.gr-button-secondary {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
}
.gr-button-secondary:hover { border-color: var(--accent) !important; color: var(--accent) !important; }
.gr-button-stop { background: rgba(248,81,73,0.15) !important; border: 1px solid rgba(248,81,73,0.4) !important; color: var(--red) !important; }

/* Advice output — rendered markdown */
.advice-box { background: var(--surface) !important; border: 1px solid var(--border) !important;
              border-radius: 12px !important; padding: 28px !important; font-family: var(--font-display) !important; }
.advice-box h2 { color: var(--accent) !important; font-size: 1.1rem !important; margin: 24px 0 12px !important;
                 padding-bottom: 8px !important; border-bottom: 1px solid var(--border) !important; }
.advice-box h3 { color: var(--accent2) !important; font-size: 0.95rem !important; margin: 16px 0 8px !important; }
.advice-box strong { color: var(--text) !important; }
.advice-box hr { border-color: var(--border) !important; margin: 16px 0 !important; }
.advice-box code { background: var(--surface2) !important; color: var(--accent) !important;
                   font-family: var(--font-mono) !important; padding: 2px 6px !important; border-radius: 4px !important; }
.advice-box ul, .advice-box ol { padding-left: 20px !important; }
.advice-box li { margin: 6px 0 !important; color: var(--text) !important; line-height: 1.6 !important; }
.advice-box p { line-height: 1.7 !important; color: #c9d1d9 !important; margin: 8px 0 !important; }

/* Chatbot */
.gr-chatbot { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 12px !important; }
.message.user { background: rgba(124,106,245,0.15) !important; border: 1px solid rgba(124,106,245,0.3) !important; }
.message.bot { background: var(--surface2) !important; border: 1px solid var(--border) !important; }

/* Status chips */
.status-ok { color: var(--green) !important; font-family: var(--font-mono) !important; font-size: 0.8rem !important; }
.status-err { color: var(--red) !important; font-family: var(--font-mono) !important; font-size: 0.8rem !important; }

/* Market preview mono */
.mkt-preview textarea {
    font-family: var(--font-mono) !important;
    font-size: 0.72rem !important;
    line-height: 1.5 !important;
    color: #88d4b0 !important;
    background: #060a0e !important;
}

/* Log box */
.log-box textarea {
    font-family: var(--font-mono) !important;
    font-size: 0.75rem !important;
    color: var(--muted) !important;
    background: var(--surface2) !important;
}

/* Progress bar */
.gr-progress { background: rgba(0,212,170,0.2) !important; }
.gr-progress-bar { background: var(--accent) !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--surface); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }
"""

HEADER_HTML = """
<div class="fw-hero">
  <div class="fw-hero-title">💹 FinWise</div>
  <div class="fw-hero-sub">Quantitative Investment Intelligence · Powered by LangChain + ChromaDB</div>
  <div style="margin-top:12px">
    <span class="fw-badge">⬡ Nifty50 Analysis</span>
    <span class="fw-badge">⬡ Per-Stock ₹ Allocation</span>
    <span class="fw-badge">⬡ Live Market RAG</span>
    <span class="fw-badge">⬡ Model Agnostic LLM</span>
  </div>
</div>
"""

METRICS_HTML = """
<div class="fw-metrics">
  <div class="fw-metric"><span class="fw-metric-val" id="m-surplus">₹0</span><div class="fw-metric-label">Monthly Surplus</div></div>
  <div class="fw-metric"><span class="fw-metric-val" id="m-rate">0%</span><div class="fw-metric-label">Savings Rate</div></div>
  <div class="fw-metric"><span class="fw-metric-val" id="m-annual">₹0</span><div class="fw-metric-label">Annual Corpus</div></div>
  <div class="fw-metric"><span class="fw-metric-val" style="color:var(--accent2)">LIVE</span><div class="fw-metric-label">Market Data</div></div>
</div>
<script>
function updateMetrics() {
  const s = parseFloat(document.querySelector('#salary-input input')?.value || 0);
  const e = parseFloat(document.querySelector('#emis-input input')?.value || 0);
  const x = parseFloat(document.querySelector('#exp-input input')?.value || 0);
  const surplus = Math.max(0, s - e - x);
  const rate = s > 0 ? (surplus/s*100).toFixed(1) : 0;
  document.getElementById('m-surplus').textContent = '₹' + surplus.toLocaleString('en-IN');
  document.getElementById('m-rate').textContent = rate + '%';
  document.getElementById('m-annual').textContent = '₹' + (surplus*12).toLocaleString('en-IN');
}
document.addEventListener('input', updateMetrics);
setTimeout(updateMetrics, 1000);
</script>
"""


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="FinWise — Investment Intelligence") as demo:
        mkt_full_state = gr.State("")

        gr.HTML(HEADER_HTML)

        with gr.Tabs(elem_classes=["main-tabs"]):

            # ── TAB 1: Setup ─────────────────────────────────────────────────
            with gr.TabItem("⚙️  Setup & Data"):
                gr.HTML("""<div class="fw-panel-title" style="padding:20px 0 0 4px">
                    INPUT SOURCES</div>""")

                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        gr.HTML('<div class="fw-panel-title">🏦 BANK STATEMENT</div>')
                        bank_f = gr.File(label="Upload CSV / Excel",
                                         file_types=[".csv",".xlsx",".xls"])
                        bank_btn = gr.Button("▶ Process Bank Statement", variant="secondary", size="sm")
                        bank_st = gr.Textbox(label="Status", interactive=False, lines=1,
                                              elem_classes=["log-box"])
                        bank_btn.click(process_bank, bank_f, bank_st)

                    with gr.Column(scale=1):
                        gr.HTML('<div class="fw-panel-title">📈 INVESTMENT PORTFOLIO</div>')
                        inv_f = gr.File(label="Upload CSV / Excel",
                                         file_types=[".csv",".xlsx",".xls"])
                        inv_btn = gr.Button("▶ Process Portfolio", variant="secondary", size="sm")
                        inv_st = gr.Textbox(label="Status", interactive=False, lines=1,
                                             elem_classes=["log-box"])
                        inv_btn.click(process_inv, inv_f, inv_st)

                gr.HTML('<div style="height:1px;background:var(--border);margin:8px 0 20px"></div>')
                gr.HTML('<div class="fw-panel-title">👤 MONTHLY FINANCIAL PROFILE</div>')
                gr.HTML(METRICS_HTML)

                with gr.Row():
                    salary_in = gr.Number(label="Monthly Salary (₹)", value=100000,
                                           precision=0, elem_id="salary-input")
                    emis_in   = gr.Number(label="Total EMIs (₹)", value=20000,
                                           precision=0, elem_id="emis-input")
                    exp_in    = gr.Number(label="Living Expenses (₹)", value=30000,
                                           precision=0, elem_id="exp-input")

                gr.HTML('<div style="height:1px;background:var(--border);margin:20px 0"></div>')
                gr.HTML('<div class="fw-panel-title">📡 LIVE MARKET DATA — NIFTY50 + MIDCAP</div>')

                with gr.Row():
                    mkt_btn = gr.Button("🔄 Fetch All Stocks + Indices (Nifty50 full scan)",
                                         variant="secondary")
                    mkt_st_chip = gr.Textbox(label="", interactive=False, lines=1, scale=0,
                                              elem_classes=["log-box"], min_width=180)

                mkt_preview = gr.Textbox(
                    label="Market Snapshot Preview",
                    interactive=False, lines=20, max_lines=30,
                    elem_classes=["mkt-preview"],
                )

                def _refresh(prog=gr.Progress()):
                    prog(0.1, desc="Connecting to yfinance…")
                    preview, full = refresh_mkt()
                    prog(1.0)
                    lines = len(full.split("\n")) if full else 0
                    return preview, full, f"✅ {lines} data lines fetched"

                mkt_btn.click(_refresh, outputs=[mkt_preview, mkt_full_state, mkt_st_chip])

            # ── TAB 2: Deep Advice ───────────────────────────────────────────
            with gr.TabItem("🎯  Investment Advice"):
                gr.HTML('<div class="fw-panel-title" style="padding:20px 0 8px 4px">AI ANALYSIS ENGINE</div>')

                custom_q = gr.Textbox(
                    label="Custom Question (leave blank for full analysis)",
                    placeholder="e.g. Which oversold Nifty50 stocks are worth buying this month?",
                    lines=2,
                )

                with gr.Row():
                    gen_btn = gr.Button(
                        "🚀  Run Deep Market Analysis + Allocate ₹ Across All Stocks",
                        variant="primary", scale=3,
                    )
                    rst_btn = gr.Button("↺ Reset", variant="stop", scale=1)

                proc_log = gr.Textbox(label="Pipeline Log", interactive=False,
                                       lines=2, elem_classes=["log-box"])

                gr.HTML('<div style="height:1px;background:var(--border);margin:12px 0 16px"></div>')

                advice_out = gr.Markdown(
                    value="> ⬡ Upload your data and click **Run Deep Market Analysis** to get "
                          "per-stock ₹ allocations across the full Nifty50 universe.",
                    elem_classes=["advice-box"],
                )

                gen_btn.click(
                    fn=generate,
                    inputs=[bank_f, inv_f, salary_in, emis_in, exp_in,
                            custom_q, mkt_full_state],
                    outputs=[advice_out, proc_log],
                )
                rst_btn.click(reset, outputs=[advice_out, proc_log])

            # ── TAB 3: Chat ──────────────────────────────────────────────────
            with gr.TabItem("💬  Ask Advisor"):
                gr.HTML('<div class="fw-panel-title" style="padding:20px 0 8px 4px">'
                        'CONVERSATIONAL ADVISOR — Ask anything after generating advice</div>')

                chatbot = gr.Chatbot(label="", height=520,
                                      avatar_images=(None, "https://api.dicebear.com/7.x/bottts/svg?seed=finwise"))
                with gr.Row():
                    chat_in = gr.Textbox(placeholder="Ask a follow-up…", show_label=False, scale=5)
                    send_btn = gr.Button("Send ↵", variant="primary", scale=1)

                send_btn.click(chat, [chat_in, chatbot], [chat_in, chatbot])
                chat_in.submit(chat, [chat_in, chatbot], [chat_in, chatbot])

            # ── TAB 4: Data Format ───────────────────────────────────────────
            with gr.TabItem("📋  Data Format"):
                gr.Markdown("""
## Expected Input Formats

### 🏦 Bank Statement CSV
```
Date,Description,Debit,Credit,Balance
01-Jan-2025,Salary credit,,100000,150000
05-Jan-2025,Swiggy food order,450,,149550
10-Jan-2025,HDFC Home Loan EMI,25000,,124550
15-Jan-2025,Amazon shopping,3200,,121350
20-Jan-2025,Zerodha SIP - Axis Bluechip,5000,,116350
```
> **Column names are flexible** — the ETL pipeline recognises most bank export formats
> (HDFC, SBI, ICICI, Kotak, Axis etc.). Date formats are auto-parsed.

---

### 📈 Investment Portfolio CSV
```
Date,Asset,Type,Units,BuyPrice,CurrentPrice,Sector
01-Mar-2024,RELIANCE.NS,stock,10,2500,2950,Energy
01-Mar-2024,Axis Bluechip Fund,mf,500,45.5,52.3,Equity MF
01-Jun-2024,HDFCBANK.NS,stock,20,1650,1720,Banking
01-Jan-2025,SGB Gold Bond,gold,5,6200,7100,Commodities
15-Feb-2025,NIFTYBEES.NS,etf,100,220,235,Index ETF
```

| Type value | Meaning |
|---|---|
| `stock` | Direct equity NSE/BSE |
| `mf` | Mutual Fund / SIP unit |
| `etf` | Exchange Traded Fund |
| `fd` | Fixed Deposit |
| `gold` | Physical gold / SGB |
| `bond` | NCD / Govt bond |

---

### 🔧 LLM Configuration (`.env`)
```bash
LLM_PROVIDER=anthropic           # anthropic | openai | ollama
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# OLLAMA_MODEL=llama3            # free local model

ALPHA_VANTAGE_KEY=demo           # free key: alphavantage.co
EMBEDDING_MODEL=all-MiniLM-L6-v2  # open-source, no key needed
```

---

### 📊 What FinWise Analyses Per Stock
For every Nifty50 + Midcap stock the AI receives:
`Price · 1D/1W/1M/3M momentum · PE · Forward PE · PB ratio · Beta · ROE · D/E ratio · Revenue growth · Earnings growth · RSI(14) · Dividend yield · Market cap · % from 52W high`
""")

    return demo
