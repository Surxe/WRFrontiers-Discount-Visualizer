"""
step1_scrape.py

Step 1: Scrape the news URL and save body text to prompt/scraped_news_page.txt.
"""

import json
import requests
from bs4 import BeautifulSoup
from config import PROMPT_DIR, SCRAPED_PAGE, REPO_ROOT

def scrape_url(url: str) -> str:
    """
    Downloads the news page and extracts the article body text.
    The site uses Nuxt SSR and embeds the article body in JSON-LD structured data.
    Falls back to BeautifulSoup body text if JSON-LD is not found.
    """
    print(f"[1/5] Scraping URL: {url}")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Try JSON-LD first (most reliable for this SSR site)
    for script_tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script_tag.string)
            if isinstance(data, dict) and "articleBody" in data:
                article_html = data["articleBody"]
                # Strip HTML tags from article body
                article_soup = BeautifulSoup(article_html, "html.parser")
                return article_soup.get_text(separator="\n").strip()
        except (json.JSONDecodeError, TypeError):
            continue

    # Fallback: extract all visible text from the page body
    print("  [!] JSON-LD not found; falling back to body text extraction.")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n").strip()


def save_scraped_page(text: str):
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    SCRAPED_PAGE.write_text(text, encoding="utf-8")
    print(f"  -> Saved scraped text to {SCRAPED_PAGE.relative_to(REPO_ROOT)}")


def run_step(url: str):
    article_text = scrape_url(url)
    save_scraped_page(article_text)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python step1_scrape.py <news_url>")
        sys.exit(1)
    run_step(sys.argv[1])
