"""
Web scraping handler — fetch URLs and extract structured data.
Uses requests + BeautifulSoup (no API keys needed).
"""

import time
import requests
from bs4 import BeautifulSoup


def handle(task, job):
    """Scrape a batch of URLs and extract key content."""
    payload = task.get("task_payload") or {}
    job_payload = job.get("input_payload") or {}

    urls = payload.get("urls") or job_payload.get("urls", [])

    if not urls:
        # If a single URL was provided as text
        text = job_payload.get("text", "")
        if text.startswith("http"):
            urls = [u.strip() for u in text.split("\n") if u.strip().startswith("http")]

    if not urls:
        return (
            "## Web Scraping Report\n\n"
            "No URLs provided. In production, this worker would:\n"
            "- Fetch each URL with proper headers\n"
            "- Extract page title, meta description, headings\n"
            "- Pull main content text\n"
            "- Extract all links and images\n"
            "- Return structured data per page\n"
        )

    results = []
    for url in urls:
        try:
            start = time.time()
            resp = requests.get(
                url,
                timeout=15,
                headers={"User-Agent": "DCN-Worker/1.0 (research project)"}
            )
            resp.raise_for_status()
            elapsed = round(time.time() - start, 2)

            soup = BeautifulSoup(resp.text, "html.parser")

            title = soup.title.string.strip() if soup.title and soup.title.string else "No title"

            # Meta description
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag["content"][:200]

            # Headings
            headings = []
            for h in soup.find_all(["h1", "h2", "h3"], limit=10):
                text = h.get_text(strip=True)
                if text:
                    headings.append(f"  - {h.name}: {text[:80]}")

            # Links count
            links = soup.find_all("a", href=True)
            images = soup.find_all("img", src=True)

            # Main text preview
            paragraphs = soup.find_all("p")
            main_text = " ".join(p.get_text(strip=True) for p in paragraphs[:5])[:300]

            result = (
                f"### {url}\n"
                f"**Title:** {title}\n"
                f"**Description:** {meta_desc or 'None'}\n"
                f"**Links:** {len(links)} | **Images:** {len(images)} | **Time:** {elapsed}s\n"
            )
            if headings:
                result += f"**Headings:**\n" + "\n".join(headings[:5]) + "\n"
            if main_text:
                result += f"**Preview:** {main_text}...\n"

            results.append(result)

        except Exception as e:
            results.append(f"### {url}\n**Error:** {e}\n")

    return (
        f"## Web Scraping Results\n\n"
        f"Scraped {len(urls)} URLs\n\n"
        + "\n---\n\n".join(results)
    )
