"""
advisor/advisor.py
------------------
Main orchestrator that pulls all RAG contexts together and invokes
the LangChain advisor chain to produce investment recommendations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage
from loguru import logger

from advisor.chains import build_advisor_chain, build_chat_chain
from config.settings import UserFinancials
from market.market_rag import refresh_market_rag
from rag.bank_rag import get_spending_summary
from rag.investment_rag import get_portfolio_summary


@dataclass
class AdvisorSession:
    """Holds state for a single advisory session."""
    financials: Optional[UserFinancials] = None
    bank_summary: str = ""
    portfolio_summary: str = ""
    market_summary: str = ""
    chat_history: List = field(default_factory=list)
    context_ready: bool = False


def build_user_profile(financials: UserFinancials) -> str:
    investable = financials.monthly_investable
    savings_rate = (investable / financials.monthly_salary * 100) if financials.monthly_salary > 0 else 0
    return (
        f"Monthly Salary: ₹{financials.monthly_salary:,.0f}\n"
        f"Monthly EMIs: ₹{financials.monthly_emis:,.0f}\n"
        f"Monthly Expenses (estimated): ₹{financials.monthly_expenses:,.0f}\n"
        f"Monthly Investable Surplus: ₹{investable:,.0f}\n"
        f"Savings Rate: {savings_rate:.1f}%\n"
        f"Annual Investable Corpus: ₹{investable * 12:,.0f}"
    )


class FinWiseAdvisor:
    """
    High-level advisor that orchestrates RAG retrieval + LLM chain.
    """

    def __init__(self):
        self._advisor_chain = None
        self._chat_chain = None
        self.session = AdvisorSession()

    def _get_advisor_chain(self):
        if self._advisor_chain is None:
            self._advisor_chain = build_advisor_chain()
        return self._advisor_chain

    def _get_chat_chain(self):
        if self._chat_chain is None:
            self._chat_chain = build_chat_chain()
        return self._chat_chain

    def prepare_context(
        self,
        financials: UserFinancials,
        refresh_market: bool = True,
        market_summary_override: Optional[str] = None,
    ) -> str:
        """Pull all RAG context. Call this once before generating advice."""
        logger.info("Preparing RAG context for advisor...")

        self.session.financials = financials
        self.session.bank_summary = get_spending_summary()
        self.session.portfolio_summary = get_portfolio_summary()

        if market_summary_override:
            self.session.market_summary = market_summary_override
        elif refresh_market:
            self.session.market_summary = refresh_market_rag()
        else:
            self.session.market_summary = "Market data not fetched. Enable refresh_market=True."

        self.session.context_ready = True
        logger.success("Context prepared successfully")
        return "Context ready ✓"

    def generate_advice(
        self,
        question: str = "Based on my financial situation, where should I invest this month?",
    ) -> str:
        """Generate full investment advice."""
        if not self.session.context_ready:
            return "⚠️ Please call prepare_context() first or use the UI to upload your files."

        user_profile = build_user_profile(self.session.financials)
        logger.info(f"Generating advice for question: {question[:60]}...")

        chain = self._get_advisor_chain()
        response = chain.invoke({
            "user_profile": user_profile,
            "bank_summary": self.session.bank_summary,
            "portfolio_summary": self.session.portfolio_summary,
            "market_summary": self.session.market_summary,
            "question": question,
        })

        # Store in chat history
        self.session.chat_history.append(HumanMessage(content=question))
        self.session.chat_history.append(AIMessage(content=response))

        return response

    def chat(self, message: str) -> str:
        """Follow-up conversational message using chat history."""
        if not self.session.context_ready:
            return "⚠️ Please generate initial advice first."

        context = (
            f"User Profile:\n{build_user_profile(self.session.financials)}\n\n"
            f"Portfolio Summary:\n{self.session.portfolio_summary[:500]}\n\n"
            f"Market Summary:\n{self.session.market_summary[:500]}"
        )

        chain = self._get_chat_chain()
        response = chain.invoke({
            "context": context,
            "history": self.session.chat_history[-10:],  # last 5 turns
            "question": message,
        })

        self.session.chat_history.append(HumanMessage(content=message))
        self.session.chat_history.append(AIMessage(content=response))

        return response

    def reset_session(self):
        self.session = AdvisorSession()
        logger.info("Advisor session reset")
