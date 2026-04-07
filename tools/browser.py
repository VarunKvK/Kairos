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

def visit_page(url : str, retries: int = 3)-> BrowserResult:
    """
    Visit a URL and return the visible text content of the page.
    Runs headlessly — no browser window opens on your screen.

    Example:
        result = visit_page("https://example.com")
        print(result.content)
    """
    last_error = ""

    for attempt in range(1, retries + 1):
        try:
            with sync_playwright() as p:
                # Launch Chromium in headless mode (invisible browser)
                # ignore_https_errors → ignores invalid SSL certificates

                browser = p.chromium.launch(headless = True)
                context = browser.new_context(ignore_https_errors=True)
                page = context.new_page()

                # Block images, fonts and stylesheets to load pages faster
                page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())

                # Visit the URL — timeout increases with each retry attempt
                # Attempt 1 → 20s, Attempt 2 → 30s, Attempt 3 → 40s
                timeout = (15 + (attempt * 5)) * 1000
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)

                # Extract only the visible text — strip all HTML tags
                content = page.inner_text("body")

                browser.close()

                return BrowserResult(
                    url = url,
                    content = content.strip(),
                    message = f"Successfully visited {url}",
                    success = True,
                )

        except Exception as e:
            last_error = str(e)
            # If we have retries left, try again
            if attempt < retries:
                continue
    
    # All retries exhausted
    return BrowserResult(
        url     = url,
        content = "",
        message = f"Failed after {retries} attempts. Last error: {last_error}",
        success = False,
    )

def search_web(query: str) -> BrowserResult:
    """
    Search Google for a query and return the results page content.

    Example:
        result = search_web("Python list comprehension")
        print(result.content)
    """

    # Convert the query into a Google search URL
    # e.g. "Python list" becomes "https://www.google.com/search?q=Python+list"
    search_url = "https://www.google.com/search?q=" + query.replace(" ", "+")

    return visit_page(search_url)