# tools/browser.py
# Gives Kairos the ability to browse the web and extract information from pages.

from dataclasses import dataclass
from playwright.sync_api import sync_playwright

@dataclass
class BrowserResult:
    """
    Holds the result of a browser operation.

    url     → the page that was visited
    content → the extracted text content of the page
    message → a human readable status message
    success → True if the operation succeeded
    """
    url : str
    content : str
    message : str
    success : bool

async def _visit(url: str, timeout: int) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        # Use a real browser context with proper user agent
        context = await browser.new_context(
            # Real Chrome user agent — not headless
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
            # Hide automation flags
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            ignore_https_errors=True,
        )

        page = await context.new_page()

        # Remove automation detection
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        # Block images/css/fonts for speed
        await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf}", 
                        lambda r: r.abort())

        await page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
        content = await page.inner_text("body")
        await browser.close()
        return content[:5000]


def visit_page(url: str, retries: int = 3) -> BrowserResult:
    """
    Visit a URL and return the visible text content.
    Uses Playwright with stealth settings to avoid bot detection.
    Retries up to 3 times with increasing timeouts.
    """
    last_error = ""

    for attempt in range(retries):
        timeout = 20 + (attempt * 5)   # 20s, 25s, 30s

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ]
                )

                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 720},
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": (
                            "text/html,application/xhtml+xml,"
                            "application/xml;q=0.9,*/*;q=0.8"
                        ),
                    },
                    ignore_https_errors=True,
                )

                page = context.new_page()

                # Hide automation flags
                page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', "
                    "{get: () => undefined});"
                )

                # Block images/css/fonts for speed
                page.route(
                    "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf}",
                    lambda r: r.abort()
                )

                page.goto(
                    url,
                    timeout=timeout * 1000,
                    wait_until="domcontentloaded"
                )

                content = page.inner_text("body")
                browser.close()

                return BrowserResult(
                    url=url,
                    content=content[:5000],
                    message="OK",
                    success=True,
                )

        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                time.sleep(2)

    return BrowserResult(
        url=url,
        content="",
        message=f"Failed after {retries} attempts: {last_error}",
        success=False,
    )



from ddgs import DDGS

def search_web(query: str) -> BrowserResult:
    """
    Search the web using DuckDuckGo API library.
    No bot detection — returns clean results directly.
    No browser needed for searches.
    """
    try:
        with DDGS() as ddgs:
            # Get top 5 results
            results = list(ddgs.text(query, max_results=5))

        if not results:
            return BrowserResult(
                url     = f"ddg:{query}",
                content = "No results found.",
                message = "No results.",
                success = False,
            )

        # Format results cleanly for the LLM
        lines = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'No title')}")
            lines.append(f"   {r.get('href', '')}")
            lines.append(f"   {r.get('body', 'No description')[:200]}")
            lines.append("")

        content = "\n".join(lines)

        return BrowserResult(
            url     = f"ddg:{query}",
            content = content,
            message = "Search complete.",
            success = True,
        )

    except Exception as e:
        return BrowserResult(
            url     = f"ddg:{query}",
            content = "",
            message = f"Search failed: {e}",
            success = False,
        )