Minimal trafilatura.extract stub added to support test execution in CI-local environments. This file mirrors the local implementation under scripts/scrape-website/scrape_website/trafilatura/__init__.py

[File contents below]

from urllib.parse import urlparse
import re


def _extract_text_from_html(html_content: str) -> tuple[str, str]:
    try:
        # Simple regex-based extraction for tests: first <h1> and all <p>
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_content, re.IGNORECASE | re.DOTALL)
        title = re.sub(r"\s+", " ", h1_match.group(1)).strip() if h1_match else ""
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html_content, re.IGNORECASE | re.DOTALL)
        paragraphs = [re.sub(r"<[^>]+>", "", p).strip() for p in paragraphs if p.strip()]
        body = "\n\n".join(paragraphs)
        if not body:
            # Fallback to stripping tags from the body
            body = re.sub(r"<[^>]+>", "", html_content).strip()
        return title, body
    except Exception:
        return "", ""

def extract(html_content: str, url: str = '', **kwargs) -> str | None:
    """Minimal extract implementation returning markdown with YAML front matter.
    This is a lightweight stub for tests and integration in environments
    where the real `trafilatura` package is unavailable.
    """
    if not html_content or len(html_content.strip()) == 0:
        return None
    title, body = _extract_text_from_html(html_content)
    parsed = urlparse(url or '')
    hostname = parsed.hostname or ''
    front = ["---"]
    if title:
        front.append(f"title: {title}")
    front.append(f"url: {url}")
    front.append(f"hostname: {hostname}")
    front.append("---\n")
    content = body or ''
    return "\n".join(front) + content
