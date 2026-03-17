"""
main.py
-------
Entry point for FinWise. Launches the Gradio UI.

Usage:
    python main.py                         # Default port 7860
    python main.py --port 8080             # Custom port
    python main.py --share                 # Public Gradio share link
    python main.py --no-ui --demo          # CLI demo mode (no UI)
"""
from __future__ import annotations

import argparse
import sys

from loguru import logger

# ── Logger setup ──────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add("data/finwise.log", rotation="10 MB", retention="7 days", level="DEBUG")


def cli_demo():
    """Run a quick CLI demo without the UI."""
    from config.settings import UserFinancials
    from advisor.advisor import FinWiseAdvisor
    from etl.bank_pipeline import run_bank_pipeline
    from etl.investment_pipeline import run_investment_pipeline

    logger.info("=== FinWise CLI Demo ===")

    # Create sample data files
    import pandas as pd
    from config.settings import UPLOADS_DIR

    bank_path = UPLOADS_DIR / "sample_bank.csv"
    inv_path = UPLOADS_DIR / "sample_investments.csv"

    # Sample bank statement
    bank_df = pd.DataFrame({
        "Date": ["01-Jan-2025","05-Jan-2025","10-Jan-2025","15-Jan-2025",
                 "20-Jan-2025","25-Jan-2025","28-Jan-2025","01-Feb-2025",
                 "06-Feb-2025","15-Feb-2025"],
        "Description": ["Salary credit","Swiggy food order","HDFC EMI payment",
                        "Amazon shopping","Zerodha SIP","Electricity bill",
                        "Uber ride","Salary credit","Netflix subscription",
                        "Pharmacy purchase"],
        "Debit": ["","450","25000","3200","5000","1800","320","","649","850"],
        "Credit": ["100000","","","","","","","100000","",""],
        "Balance": ["150000","149550","124550","121350","116350","114550",
                    "114230","214230","213581","212731"],
    })
    bank_df.to_csv(bank_path, index=False)
    logger.info(f"Sample bank CSV created at {bank_path}")

    # Sample investments
    inv_df = pd.DataFrame({
        "Date": ["01-Mar-2024","01-Mar-2024","01-Jun-2024","01-Jan-2025"],
        "Asset": ["RELIANCE.NS","Axis Bluechip Fund","HDFCBANK.NS","SGB Gold Bond"],
        "Type": ["stock","mf","stock","gold"],
        "Units": [10, 500, 20, 5],
        "BuyPrice": [2500, 45.5, 1650, 6200],
        "CurrentPrice": [2950, 52.3, 1720, 7100],
        "Sector": ["Energy","Equity MF","Banking","Commodities"],
    })
    inv_df.to_csv(inv_path, index=False)
    logger.info(f"Sample investment CSV created at {inv_path}")

    # Run ETL
    run_bank_pipeline(str(bank_path))
    run_investment_pipeline(str(inv_path))

    # Prepare context and generate advice
    advisor = FinWiseAdvisor()
    financials = UserFinancials(
        monthly_salary=100000,
        monthly_emis=25000,
        monthly_expenses=35000,
    )
    advisor.prepare_context(financials=financials, refresh_market=True)
    advice = advisor.generate_advice()

    print("\n" + "="*70)
    print("FINWISE INVESTMENT ADVICE")
    print("="*70)
    print(advice)
    print("="*70)


def main():
    parser = argparse.ArgumentParser(description="FinWise – AI Investment Advisor")
    parser.add_argument("--port", type=int, default=7860, help="UI port (default: 7860)")
    parser.add_argument("--share", action="store_true", help="Create public Gradio share link")
    parser.add_argument("--no-ui", action="store_true", help="Skip UI launch")
    parser.add_argument("--demo", action="store_true", help="Run CLI demo with sample data")
    args = parser.parse_args()

    if args.demo:
        cli_demo()
        return

    if not args.no_ui:
        import gradio as gr
        from ui.app import build_ui, CSS
        logger.info(f"Starting FinWise UI on port {args.port}...")
        demo = build_ui()
        demo.launch(
            server_port=args.port,
            share=args.share,
            show_error=True,
            css=CSS,
            theme=gr.themes.Soft(primary_hue="blue"),
        )


if __name__ == "__main__":
    main()
