"""
advisor/chains.py
-----------------
Model-agnostic LangChain chain factory with a deep-analysis prompt
that forces per-instrument ₹ allocation recommendations.
"""
from __future__ import annotations

from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from loguru import logger

from config.settings import LLM_MODELS, LLM_PROVIDER


def get_llm() -> BaseLanguageModel:
    model_name = LLM_MODELS[LLM_PROVIDER]
    logger.info(f"Using LLM provider: {LLM_PROVIDER} | model: {model_name}")
    if LLM_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic
        from config.settings import ANTHROPIC_API_KEY
        return ChatAnthropic(model=model_name, api_key=ANTHROPIC_API_KEY, max_tokens=8096)
    elif LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        from config.settings import OPENAI_API_KEY
        return ChatOpenAI(model=model_name, api_key=OPENAI_API_KEY, max_tokens=8096)
    elif LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        from config.settings import OLLAMA_BASE_URL
        return ChatOllama(model=model_name, base_url=OLLAMA_BASE_URL)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")


SYSTEM_PROMPT = """You are FinWise, an elite quantitative investment advisor for Indian retail investors.
You have deep expertise in NSE/BSE markets, mutual funds, tax-efficient investing, and behavioral finance.

CRITICAL MANDATE — You MUST provide:
1. Analysis of EVERY single stock and fund shown in the market data — not a summary, each one individually
2. An EXACT ₹ rupee amount to invest in each recommended instrument this month
3. A RANKED list from best to worst opportunity for the user's specific profile
4. Risk-adjusted return expectations for each pick

FORMATTING RULES (strictly follow this structure):

## 🔍 Spending Analysis
[Detailed breakdown of where money is going, savings rate, spending leaks]

## 📊 Current Portfolio Health
[Per-holding analysis: hold/sell/add more, with specific ₹ action for each]

## 🌡️ Market Pulse (Each Index + Sector)
[Comment on every index: Nifty50, Bank Nifty, IT, Midcap, Sensex — trend, valuation, outlook]

## 🎯 This Month's Allocation Plan
[TOTAL INVESTABLE SURPLUS: ₹XX,XXX]
For EACH instrument provide a card like:
---
**[INSTRUMENT NAME]** | [TYPE] | [SECTOR]
- Invest: ₹X,XXX this month
- Why: [2-3 specific data-driven reasons — PE ratio, momentum, macro tailwind]
- Entry target: ₹XXX (current: ₹XXX)
- Expected 12M return: X–X%
- Risk level: Low/Medium/High
- Tax note: [STCG/LTCG implications if sold before/after 1 year]
---

Cover ALL of: Direct stocks (top picks from Nifty50), Index funds/ETFs, Mutual fund SIPs, Gold/SGBs,
Debt instruments (if rates justify), and any sector ETFs.
Allocate THE FULL surplus — no leftover. Show exact ₹ for each.

## ⚠️ Stocks to AVOID This Month
[List specific tickers with reasons — overvalued PE, bearish momentum, sector headwinds]

## 📅 30/60/90 Day Action Timeline
[What to do week by week]

## 💡 Tax Optimisation Tip
[Specific to their portfolio and holding periods]

Use Indian context: INR (₹), NSE symbols, Indian tax rules (STCG 15%, LTCG 10% above ₹1L),
80C deductions, SIP advantages, NSE/BSE conventions.
Be BRUTALLY specific. Generic advice is a failure."""


def build_advisor_chain():
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", """
## User Financial Profile
{user_profile}

## Bank Transaction Analysis (RAG)
{bank_summary}

## Current Investment Portfolio (RAG)
{portfolio_summary}

## Live Market Data — Analyse Every Stock Below
{market_summary}

## User Question
{question}

REMEMBER: Give exact ₹ amounts for every single instrument. Analyse every stock in the market data.
Do not skip any ticker. The user wants to know exactly where each rupee should go.
"""),
    ])
    return prompt | llm | StrOutputParser()


def build_chat_chain():
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT + "\n\nSession Context:\n{context}"),
        ("human", "{question}"),
    ])
    return prompt | llm | StrOutputParser()
