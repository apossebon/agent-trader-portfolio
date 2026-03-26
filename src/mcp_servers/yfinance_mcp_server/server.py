
import argparse
import os 
from langchain_core.tools import tool
from langchain_mcp_adapters.tools import to_fastmcp
from mcp.server.fastmcp import FastMCP

from src.mcp_servers.yfinance_mcp_server.tools.stock_price import get_stock_price
from src.mcp_servers.yfinance_mcp_server.tools.company_indicators import get_company_indicators
from src.mcp_servers.yfinance_mcp_server.tools.ticker_lookup import find_ticker
from src.mcp_servers.yfinance_mcp_server.tools.stock_price_date import get_stock_price_on_date
from src.mcp_servers.yfinance_mcp_server.tools.current_datetime import get_current_datetime


@tool(description="Find the ticker of a company (ex: Petrobras → PETR4.SA). Parameters: company_name = name of the company or asset (ex: Petrobras, JBS, etc.)")
async def find_ticker_tool(company_name: str) -> str:
    
    return find_ticker(company_name)

@tool (description="Return the current stock price or currency cotation. Parameters: ticker = ticker of the stock or currency cotation (ex: PETR4.SA or EURBRL=X or USDBRL=X )", ) 
async def get_stock_price_tool(ticker: str) -> str:
    return get_stock_price(ticker)

@tool (description= """
       convert the date to the format YYYY-MM-DD.
       return the price of the stock on the date format (YYYY-MM-DD).
       If there is no trading on that day, use the most recent closing price before.
       Parameters
       ----------
       ticker : str
           The ticker of the stock (ex: PETR4.SA).
       date : str
           The date to get the price (YYYY-MM-DD).
       Returns
       -------
       str
           The price of the stock on the date (YYYY-MM-DD).  
       """)
async def get_stock_price_on_date_tool(ticker: str, date: str) -> str:
    print(f"get_stock_price_on_date_tool: {ticker}, {date}")
    return get_stock_price_on_date(ticker, date)

@tool (description= """
       Returns the current date and time in the format "YYYY-MM-DD HH:MM:SS (timezone).
       Parameters
       ----------
       tz : str
           IANA timezone identifier (ex.: "UTC", "America/New_York",
           "Europe/London", "Asia/Tokyo"). Default: "America/Sao_Paulo".
       Returns
       -------
       str
           A string in the format "YYYY-MM-DD HH:MM:SS (timezone)".
       """)
async def get_current_datetime_tool(tz: str = "America/Sao_Paulo") -> str:
    return get_current_datetime(tz)

@tool (description="Return the company indicators. parameters: ticker = ticker of the stock (ex: PETR4.SA)")
async def get_company_indicators_tool(ticker: str) -> str:
    print(f"get_company_indicators_tool: {ticker}")
    return get_company_indicators(ticker)




tools_trader = [
    to_fastmcp(find_ticker_tool),
    to_fastmcp(get_stock_price_tool),
    to_fastmcp(get_stock_price_on_date_tool),
    to_fastmcp(get_current_datetime_tool), 
    to_fastmcp(get_company_indicators_tool),
]






mcp = FastMCP("yfinance-tools", host="0.0.0.0", port=8002, tools=tools_trader)


def parse_args():
    parser = argparse.ArgumentParser(description="Run FastMCP server with selectable transport.")
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default=os.getenv("FASTMCP_TRANSPORT", "stdio"),
                        help="Transport to use (default: stdio)")
    parser.add_argument("--host", default=os.getenv("FASTMCP_HOST", "127.0.0.1"),
                        help="Host/interface for HTTP/SSE (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.getenv("FASTMCP_PORT", "8000")),
                        help="Port for HTTP/SSE (default: 8000)")
    parser.add_argument("--path", default=os.getenv("FASTMCP_PATH", "/mcp"),
                        help="HTTP path when transport=http (default: /mcp)")
    return parser.parse_args()

def main():
    args = parse_args()

    # stdio (padrão) — ótimo para clientes que abrem o servidor como subprocesso
    if args.transport == "stdio":
        mcp.run(transport="stdio")  # equivalente a mcp.run()
        return

    # http (streamable HTTP) — recomendado para deploy web/remoto
    if args.transport == "streamable-http":
        # você pode customizar CORS e path se necessário
        mcp.run(transport="streamable-http")
        return

    # sse — útil para compatibilidade com clientes que esperam SSE
    if args.transport == "sse":
        mcp.run(transport="sse")
        return

if __name__ == "__main__":
    main()


