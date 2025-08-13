# server.py
from mcp.server.fastmcp import FastMCP, Context
import httpx
from bs4 import BeautifulSoup
from typing import List
from dataclasses import dataclass
import urllib.parse
import sys
import traceback
import asyncio
from datetime import datetime, timedelta
import re
import os
import argparse

# "beautifulsoup4>=4.13.3", "httpx>=0.28.1", "mcp[cli]>=1.3.0"]

@dataclass
class SearchResult:
    title: str
    link: str
    snippet: str
    position: int

class RateLimiter:
    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.requests = []

    async def acquire(self):
        now = datetime.now()
        self.requests = [req for req in self.requests if now - req < timedelta(minutes=1)]
        if len(self.requests) >= self.requests_per_minute:
            wait_time = 60 - (now - self.requests[0]).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        self.requests.append(now)

class DuckDuckGoSearcher:
    BASE_URL = "https://html.duckduckgo.com/html"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    def __init__(self):
        self.rate_limiter = RateLimiter()

    def format_results_for_llm(self, results: List[SearchResult]) -> str:
        if not results:
            return ("No results were found for your search query. This could be due to "
                    "DuckDuckGo's bot detection or the query returned no matches. "
                    "Please try rephrasing your search or try again in a few minutes.")
        output = [f"Found {len(results)} search results:\n"]
        for result in results:
            output.append(f"{result.position}. {result.title}")
            output.append(f"   URL: {result.link}")
            output.append(f"   Summary: {result.snippet}")
            output.append("")
        return "\n".join(output)

    async def search(self, query: str, ctx: Context, max_results: int = 10) -> List[SearchResult]:
        try:
            await self.rate_limiter.acquire()
            data = {"q": query, "b": "", "kl": ""}
            await ctx.info(f"Searching DuckDuckGo for: {query}")
            async with httpx.AsyncClient() as client:
                response = await client.post(self.BASE_URL, data=data, headers=self.HEADERS, timeout=30.0)
                response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            if not soup:
                await ctx.error("Failed to parse HTML response")
                return []
            results = []
            for result in soup.select(".result"):
                title_elem = result.select_one(".result__title")
                if not title_elem:
                    continue
                link_elem = title_elem.find("a")
                if not link_elem:
                    continue
                title = link_elem.get_text(strip=True)
                link = link_elem.get("href", "")
                if "y.js" in link:
                    continue
                if link.startswith("//duckduckgo.com/l/?uddg="):
                    link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                snippet_elem = result.select_one(".result__snippet")
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                results.append(SearchResult(title=title, link=link, snippet=snippet, position=len(results) + 1))
                if len(results) >= max_results:
                    break
            await ctx.info(f"Successfully found {len(results)} results")
            return results
        except httpx.TimeoutException:
            await ctx.error("Search request timed out")
            return []
        except httpx.HTTPError as e:
            await ctx.error(f"HTTP error occurred: {str(e)}")
            return []
        except Exception as e:
            await ctx.error(f"Unexpected error during search: {str(e)}")
            traceback.print_exc(file=sys.stderr)
            return []

class WebContentFetcher:
    def __init__(self):
        self.rate_limiter = RateLimiter(requests_per_minute=20)

    async def fetch_and_parse(self, url: str, ctx: Context) -> str:
        try:
            await self.rate_limiter.acquire()
            await ctx.info(f"Fetching content from: {url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    follow_redirects=True,
                    timeout=30.0,
                )
                response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup(["script", "style", "nav", "header", "footer"]):
                element.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > 8000:
                text = text[:8000] + "... [content truncated]"
            await ctx.info(f"Successfully fetched and parsed content ({len(text)} characters)")
            return text
        except httpx.TimeoutException:
            await ctx.error(f"Request timed out for URL: {url}")
            return "Error: The request timed out while trying to fetch the webpage."
        except httpx.HTTPError as e:
            await ctx.error(f"HTTP error occurred while fetching {url}: {str(e)}")
            return f"Error: Could not access the webpage ({str(e)})"
        except Exception as e:
            await ctx.error(f"Error fetching content from {url}: {str(e)}")
            return f"Error: An unexpected error occurred while fetching the webpage ({str(e)})"

# Initialize FastMCP server

mcp = FastMCP("ddg-search", host="0.0.0.0", port=8001)
searcher = DuckDuckGoSearcher()
fetcher = WebContentFetcher()

@mcp.tool()
async def search(query: str, ctx: Context, max_results: int = 10) -> str:
    """Search in Internet websites with DuckDuckGo and return formatted results. Can also be used to sentiment analysis of companies."""
    print(f"search: {query}, max_results: {max_results}")
    try:
        results = await searcher.search(query, ctx, max_results)
        return searcher.format_results_for_llm(results)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return f"An error occurred while searching: {str(e)}"

@mcp.tool()
async def fetch_content(url: str, ctx: Context) -> str:
    """Fetch and parse content from a webpage URL."""
    print(f"fetch_content: {url}")
    return await fetcher.fetch_and_parse(url, ctx)

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
