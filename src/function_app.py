import os
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv
import requests
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _load_env(env_filename: str = ".env.dev") -> None:
    """
    Load environment variables from config directory.
    Defaults to .env.dev for local development.
    Automatically switches to .env.prod when deployed to Azure (detected via WEBSITE_INSTANCE_ID).
    """
    is_azure_production = os.getenv("WEBSITE_INSTANCE_ID") is not None
    
    if is_azure_production and env_filename == ".env.dev":
        env_filename = ".env.prod"
    
    env_path = os.path.join(_project_root(), "config", env_filename)
    load_dotenv(dotenv_path=env_path, override=False)


def _get_env(name: str) -> str:
    """Helper to fetch required env vars with a clean error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


# ------------------------------------------------------
# COMPANY EARNINGS DATA TOOLS
# ------------------------------------------------------

# Tool 1: get_company_revenue
tool_properties_company_revenue = [
    ToolProperty("company_symbol", "string", "Company ticker symbol (MSFT, TSLA, or NVDA)"),
    ToolProperty("fiscal_year", "number", "Fiscal year (e.g., 2024)"),
    ToolProperty("fiscal_quarter", "number", "Fiscal quarter (1, 2, 3, or 4)"),
]
tool_properties_company_revenue_json = json.dumps([prop.to_dict() for prop in tool_properties_company_revenue])

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_company_revenue",
    description="Get total revenue in USD millions for a given company's quarterly earnings report",
    toolProperties=tool_properties_company_revenue_json,
)
def get_company_revenue(context) -> str:
    """Get total revenue for a company's quarterly earnings."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("get_company_revenue")

    content = json.loads(context) if isinstance(context, str) else context
    args = content.get("arguments", {})
    symbol = args.get("company_symbol", "MSFT").upper()
    fiscal_year = int(args.get("fiscal_year", 2024))
    fiscal_quarter = int(args.get("fiscal_quarter", 4))

    # Validate inputs
    valid_symbols = ["MSFT", "TSLA", "NVDA"]
    if symbol not in valid_symbols:
        return json.dumps({
            "status": "error",
            "message": f"Invalid company symbol. Supported: {', '.join(valid_symbols)}"
        }, indent=2)

    if fiscal_quarter not in [1, 2, 3, 4]:
        return json.dumps({
            "status": "error",
            "message": "Fiscal quarter must be 1, 2, 3, or 4"
        }, indent=2)

    _load_env()

    try:
        api_key = _get_env("ALPHAVANTAGE_API_KEY")
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "INCOME_STATEMENT",
            "symbol": symbol,
            "apikey": api_key,
        }
        
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        # Find the matching quarterly report
        quarterly_reports = data.get("quarterlyReports", [])
        
        target_period = None
        for report in quarterly_reports:
            fiscal_date = report.get("fiscalDateEnding", "")
            report_year = int(fiscal_date[:4])
            report_month = int(fiscal_date[5:7])
            
            # Map month to fiscal quarter (approximate)
            if fiscal_quarter == 1 and report_month in [9, 10]:
                report_quarter = 1
            elif fiscal_quarter == 2 and report_month in [12, 1]:
                report_quarter = 2
            elif fiscal_quarter == 3 and report_month in [3, 4]:
                report_quarter = 3
            elif fiscal_quarter == 4 and report_month in [6, 7]:
                report_quarter = 4
            else:
                continue
            
            if report_year == fiscal_year and report_quarter == fiscal_quarter:
                target_period = report
                break
        
        if not target_period:
            # Fallback: use the most recent report if exact match not found
            if quarterly_reports:
                target_period = quarterly_reports[0]
                logger.warning(f"Exact period not found, using most recent: {target_period.get('fiscalDateEnding')}")
            else:
                return json.dumps({
                    "status": "error",
                    "message": "No quarterly data available"
                }, indent=2)
        
        # Extract revenue (totalRevenue field)
        revenue_str = target_period.get("totalRevenue", "0")
        revenue_millions = round(float(revenue_str) / 1_000_000, 2) if revenue_str and revenue_str != "None" else 0
        
        result = {
            "company": symbol,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "fiscal_date_ending": target_period.get("fiscalDateEnding"),
            "total_revenue_usd_millions": revenue_millions,
            "currency": "USD",
            "data_source": "Alpha Vantage",
            "raw_revenue": revenue_str
        }
        
        logger.info(f"Revenue for {symbol} FY{fiscal_year} Q{fiscal_quarter}: ${revenue_millions}M")
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e),
            "note": "Make sure ALPHAVANTAGE_API_KEY is configured in your .env file"
        }, indent=2)


# Tool 2: get_company_free_cash_flow
tool_properties_company_fcf = [
    ToolProperty("company_symbol", "string", "Company ticker symbol (MSFT, TSLA, or NVDA)"),
    ToolProperty("fiscal_year", "number", "Fiscal year (e.g., 2024)"),
    ToolProperty("fiscal_quarter", "number", "Fiscal quarter (1, 2, 3, or 4)"),
]
tool_properties_company_fcf_json = json.dumps([prop.to_dict() for prop in tool_properties_company_fcf])

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_company_free_cash_flow",
    description="Get free cash flow in USD millions for a given company's quarterly earnings report",
    toolProperties=tool_properties_company_fcf_json,
)
def get_company_free_cash_flow(context) -> str:
    """Get free cash flow for a company's quarterly earnings."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("get_company_free_cash_flow")

    content = json.loads(context) if isinstance(context, str) else context
    args = content.get("arguments", {})
    symbol = args.get("company_symbol", "MSFT").upper()
    fiscal_year = int(args.get("fiscal_year", 2024))
    fiscal_quarter = int(args.get("fiscal_quarter", 4))

    # Validate inputs
    valid_symbols = ["MSFT", "TSLA", "NVDA"]
    if symbol not in valid_symbols:
        return json.dumps({
            "status": "error",
            "message": f"Invalid company symbol. Supported: {', '.join(valid_symbols)}"
        }, indent=2)

    if fiscal_quarter not in [1, 2, 3, 4]:
        return json.dumps({
            "status": "error",
            "message": "Fiscal quarter must be 1, 2, 3, or 4"
        }, indent=2)

    _load_env()

    try:
        api_key = _get_env("ALPHAVANTAGE_API_KEY")
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "CASH_FLOW",
            "symbol": symbol,
            "apikey": api_key,
        }
        
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        # Find the matching quarterly report
        quarterly_reports = data.get("quarterlyReports", [])
        
        target_period = None
        for report in quarterly_reports:
            fiscal_date = report.get("fiscalDateEnding", "")
            report_year = int(fiscal_date[:4])
            report_month = int(fiscal_date[5:7])
            
            # Map month to fiscal quarter (approximate)
            if fiscal_quarter == 1 and report_month in [9, 10]:
                report_quarter = 1
            elif fiscal_quarter == 2 and report_month in [12, 1]:
                report_quarter = 2
            elif fiscal_quarter == 3 and report_month in [3, 4]:
                report_quarter = 3
            elif fiscal_quarter == 4 and report_month in [6, 7]:
                report_quarter = 4
            else:
                continue
            
            if report_year == fiscal_year and report_quarter == fiscal_quarter:
                target_period = report
                break
        
        if not target_period:
            # Fallback: use the most recent report if exact match not found
            if quarterly_reports:
                target_period = quarterly_reports[0]
                logger.warning(f"Exact period not found, using most recent: {target_period.get('fiscalDateEnding')}")
            else:
                return json.dumps({
                    "status": "error",
                    "message": "No quarterly cash flow data available"
                }, indent=2)
        
        # Calculate Free Cash Flow = Operating Cash Flow - Capital Expenditures
        op_cashflow_str = target_period.get("operatingCashflow", "0")
        capex_str = target_period.get("capitalExpenditures", "0")
        
        op_cashflow = float(op_cashflow_str) if op_cashflow_str and op_cashflow_str != "None" else 0
        capex = float(capex_str) if capex_str and capex_str != "None" else 0
        
        # Free Cash Flow = Operating Cash Flow - CapEx (CapEx is usually negative, so we add it)
        free_cash_flow = op_cashflow - abs(capex)
        fcf_millions = round(free_cash_flow / 1_000_000, 2)
        
        result = {
            "company": symbol,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "fiscal_date_ending": target_period.get("fiscalDateEnding"),
            "free_cash_flow_usd_millions": fcf_millions,
            "operating_cash_flow_usd_millions": round(op_cashflow / 1_000_000, 2),
            "capital_expenditures_usd_millions": round(abs(capex) / 1_000_000, 2),
            "currency": "USD",
            "data_source": "Alpha Vantage",
            "calculation": "Operating Cash Flow - Capital Expenditures"
        }
        
        logger.info(f"Free Cash Flow for {symbol} FY{fiscal_year} Q{fiscal_quarter}: ${fcf_millions}M")
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e),
            "note": "Make sure ALPHAVANTAGE_API_KEY is configured in your .env file"
        }, indent=2)
