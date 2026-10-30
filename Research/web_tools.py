# - web_search(query: str) -> str
# - fetch_url(url: str) -> str
# - python_docs(symbol: str) -> str
# - tools = [...]

import os
import re
import sys
import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from Terminal.shell import run, truncate

MAX_PAGE_CHARS = 20_000

@tool(parse_docstring=True)
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return the top results, each with a title, URL and a short excerpt from the page.

    Use this for information that isn't in the project or the Python docs, e.g. an unfamiliar error message, a library's current API, or how to do something. The excerpts are short, so read a promising page in full with fetch_url. Returns an error if web search hasn't been set up with a TAVILY_API_KEY.

    Args:
        query: What to search for. Specific queries work best, e.g. include the library name and the exact error text.
        max_results: Number of results to return, from 1 to 10. Defaults to 5.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: web search is not set up. Add TAVILY_API_KEY to .env (free key at tavily.com)"

    from tavily import TavilyClient

    try:
        response = TavilyClient(api_key=api_key).search(query, max_results=min(max(max_results, 1), 10))
    except Exception as e:
        return f"Error: search failed: {e}"

    results = response.get("results", [])
    if not results:
        return f"No results for {query!r}"

    return "\n\n".join(f"{r['title']}\n{r['url']}\n{r.get('content', '')[:500]}" for r in results)


@tool(parse_docstring=True)
def fetch_url(url: str) -> str:
    """Download a web page and return its readable text, with the page title first.

    Use this to read documentation, a README or an article, for example one found with web_search. HTML tags, scripts, menus, headers and footers are removed; plain text and JSON are returned as they are. Pages longer than 20,000 characters are cut. Only http and https URLs work, and pages that need a login or JavaScript to show their content may come back empty.

    Args:
        url: Full URL starting with http:// or https://.
    """
    if not url.startswith(("http://", "https://")):
        return "Error: only http and https URLs are supported"

    try:
        response = httpx.get(url, follow_redirects=True, timeout=20, headers={"User-Agent": "Mozilla/5.0 (agent)"})
        response.raise_for_status()
    except httpx.HTTPError as e:
        return f"Error: could not fetch {url}: {e}"

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type:
        if content_type.startswith(("text/", "application/json")):
            return response.text[:MAX_PAGE_CHARS]
        return f"Error: {url} is not a text page ({content_type})"

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "svg"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else url
    text = re.sub(r"\n\s*\n+", "\n\n", soup.get_text("\n", strip=True))
    if len(text) > MAX_PAGE_CHARS:
        text = text[:MAX_PAGE_CHARS] + f"\n... (page cut at {MAX_PAGE_CHARS} characters)"

    return f"{title}\n\n{text}"


@tool(parse_docstring=True)
def python_docs(symbol: str) -> str:
    """Show the built-in documentation, signature and docstring, for a Python module, class, function or method installed in the agent's environment.

    Use this to check exactly how to call something, e.g. a function's parameters, before writing code that uses it. Works for the standard library and any installed package, and is faster and more reliable than a web search for API details. Output is cut at 300 lines.

    Args:
        symbol: Dotted name, e.g. 'pathlib.Path.resolve', 'json.dumps' or 'langgraph.graph.StateGraph'.
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*", symbol):
        return f"Error: invalid symbol name: {symbol!r}"

    output = run([sys.executable, "-m", "pydoc", symbol], max_lines=None)
    if "No Python documentation found" in output:
        return f"Error: no documentation found for {symbol}. Check the spelling and that the package is installed"

    return truncate(output, max_lines=300)


tools = [web_search, fetch_url, python_docs]
