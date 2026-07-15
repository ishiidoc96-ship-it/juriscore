"""
Build structured metadata from scrape-website Markdown output.

Reads all .md files from data/kenyalaw.org/text/ and extracts:
- Case titles, citations, courts, dates, topics
- Legislation titles, cap numbers, years
- Gazette notices, bills, articles

Output: data/brain/metadata/cases.json, legislation.json, etc.
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# KenyaLaw URL patterns
CASE_PATTERN = re.compile(r'/akn/ke/judgment/(\w+)/(\d+)/(\d+)/')
LEGISLATION_PATTERN = re.compile(r'/akn/ke/act/(\d+)/([^/]+)/')
SUBSIDIARY_PATTERN = re.compile(r'/akn/ke/act/ln/(\d+)/(\d+)/')
GAZETTE_PATTERN = re.compile(r'/akn/ke/act/gn/(\d+)/(\d+)/')
BILL_PATTERN = re.compile(r'/akn/ke/bill/(\w+)/(\d+-\d+-\d+)/([^/]+)/')
ARTICLE_PATTERN = re.compile(r'/articles/(\d{4}-\d{2}-\d{2})/')

COURT_MAP = {
    'kesc': 'Supreme Court',
    'keca': 'Court of Appeal',
    'kehc': 'High Court',
    'keelc': 'Environment and Land Court',
    'keelrc': 'Employment and Labour Relations Court',
    'keic': 'Industrial Court',
    'kemc': "Magistrate's Court",
    'kekc': "Kadhi's Court",
    'scc': 'Small Claims Court',
}

TOPIC_KEYWORDS = {
    'constitutional': ['constitution', 'constitutional', 'fundamental rights', 'bill of rights', 'chapter four'],
    'criminal': ['criminal', 'penal code', 'murder', 'manslaughter', 'theft', 'robbery', 'fraud', 'drug', 'narcotic'],
    'contract': ['contract', 'agreement', 'breach', 'consideration', 'offer', 'acceptance'],
    'tort': ['tort', 'negligence', 'damages', 'nuisance', 'defamation', 'liability'],
    'land': ['land', 'property', 'title', 'lease', 'tenancy', 'eviction', 'boundary'],
    'family': ['family', 'marriage', 'divorce', 'custody', 'succession', 'inheritance', 'probate'],
    'employment': ['employment', 'labour', 'worker', 'salary', 'dismissal', 'termination'],
    'commercial': ['company', 'corporate', 'business', 'partnership', 'insolvency', 'bankruptcy'],
    'tax': ['tax', 'revenue', 'vat', 'income tax', 'customs', 'duty'],
    'environment': ['environment', 'pollution', 'conservation', 'ecological', 'climate'],
    'administrative': ['administrative', 'judicial review', 'public body', 'government', 'procurement'],
    'human_rights': ['human rights', 'equality', 'discrimination', 'freedom', 'dignity'],
    'media': ['media', 'press', 'broadcasting', 'journalist', 'defamation'],
    'technology': ['digital', 'cyber', 'data protection', 'privacy', 'electronic'],
    'insurance': ['insurance', 'policy', 'claim', 'underwriting'],
    'intellectual_property': ['copyright', 'trademark', 'patent', 'intellectual property'],
    'maritime': ['admiralty', 'maritime', 'shipping', 'vessel'],
    'international': ['treaty', 'convention', 'international', 'jurisdiction'],
}


def extract_court_from_url(url: str) -> str:
    """Extract court name from kenyalaw.org URL."""
    match = CASE_PATTERN.search(url)
    if match:
        code = match.group(1).lower()
        return COURT_MAP.get(code, code.upper())
    return ''


def extract_year_from_url(url: str) -> int:
    """Extract year from kenyalaw.org URL."""
    patterns = [CASE_PATTERN, LEGISLATION_PATTERN, SUBSIDIARY_PATTERN, GAZETTE_PATTERN]
    for pat in patterns:
        match = pat.search(url)
        if match:
            try:
                return int(match.group(2) if 'act/gn' in url else match.group(1 if pat == CASE_PATTERN else 1))
            except (ValueError, IndexError):
                pass
    return 0


def classify_topic(text: str) -> List[str]:
    """Classify text into legal topics based on keyword matching."""
    text_lower = text.lower()
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                topics.append(topic)
                break
    return topics[:5]  # Max 5 topics


def parse_frontmatter(content: str) -> Dict[str, str]:
    """Parse YAML frontmatter from Markdown file."""
    meta = {}
    if content.startswith('---'):
        end = content.find('---', 3)
        if end > 0:
            fm = content[3:end].strip()
            for line in fm.split('\n'):
                if ':' in line:
                    key, _, val = line.partition(':')
                    meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta


def parse_case_metadata(title: str, url: str, content: str, meta: Dict) -> Dict[str, Any]:
    """Extract structured metadata for a court case."""
    citation_match = re.search(r'\[(\d{4})\]\s*(\w+)?', title) or re.search(r'(\d{4})\s*eKLR', title)
    citation = citation_match.group(0) if citation_match else ''

    court = extract_court_from_url(url)
    year = 0
    year_match = re.search(r'(\d{4})', title)
    if year_match:
        try:
            year = int(year_match.group(1))
        except ValueError:
            pass
    if not year:
        year = extract_year_from_url(url)

    excerpt = content[:500] if content else ''
    topics = classify_topic(title + ' ' + excerpt)

    return {
        'type': 'case',
        'title': title,
        'citation': citation,
        'court': court,
        'year': year,
        'url': url,
        'topics': topics,
        'excerpt': excerpt,
        'date': meta.get('date', ''),
    }


def parse_legislation_metadata(title: str, url: str, content: str, meta: Dict) -> Dict[str, Any]:
    """Extract structured metadata for legislation."""
    cap_match = re.search(r'Cap(?:\.|\s)(\d+)', title, re.IGNORECASE)
    cap_number = cap_match.group(1) if cap_match else ''

    year = extract_year_from_url(url)
    topics = classify_topic(title + ' ' + content[:300])

    return {
        'type': 'legislation',
        'title': title,
        'cap_number': cap_number,
        'year': year,
        'url': url,
        'topics': topics,
        'excerpt': content[:500] if content else '',
        'date': meta.get('date', ''),
    }


def parse_gazette_metadata(title: str, url: str, content: str, meta: Dict) -> Dict[str, Any]:
    """Extract structured metadata for gazette notices."""
    year = extract_year_from_url(url)
    return {
        'type': 'gazette',
        'title': title,
        'year': year,
        'url': url,
        'topics': classify_topic(title + ' ' + content[:300]),
        'excerpt': content[:500] if content else '',
        'date': meta.get('date', ''),
    }


def process_file(filepath: Path) -> Optional[Dict[str, Any]]:
    """Process a single Markdown file and extract metadata."""
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    meta = parse_frontmatter(content)
    url = meta.get('url', '')
    title = meta.get('title', filepath.stem)

    if not url:
        # Try to reconstruct from filename
        url = f"https://www.kenyalaw.org{filepath.stem}"

    if CASE_PATTERN.search(url) or 'judgment' in url.lower():
        return parse_case_metadata(title, url, content, meta)
    elif LEGISLATION_PATTERN.search(url) or SUBSIDIARY_PATTERN.search(url) or 'legislation' in url.lower():
        return parse_legislation_metadata(title, url, content, meta)
    elif GAZETTE_PATTERN.search(url) or 'gazette' in url.lower():
        return parse_gazette_metadata(title, url, content, meta)
    elif BILL_PATTERN.search(url) or 'bill' in url.lower():
        return {
            'type': 'bill',
            'title': title,
            'year': extract_year_from_url(url),
            'url': url,
            'topics': classify_topic(title + ' ' + content[:300]),
            'excerpt': content[:500] if content else '',
            'date': meta.get('date', ''),
        }
    elif ARTICLE_PATTERN.search(url) or 'article' in url.lower():
        return {
            'type': 'article',
            'title': title,
            'url': url,
            'topics': classify_topic(title + ' ' + content[:300]),
            'excerpt': content[:500] if content else '',
            'date': meta.get('date', ''),
        }
    else:
        # Generic document
        return {
            'type': 'document',
            'title': title,
            'url': url,
            'topics': classify_topic(title + ' ' + content[:300]),
            'excerpt': content[:500] if content else '',
            'date': meta.get('date', ''),
        }


def build_metadata(text_dir: str, output_dir: str):
    """Build metadata index from crawled Markdown files."""
    text_path = Path(text_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if not text_path.exists():
        print(f"Error: {text_dir} does not exist. Run the crawler first.")
        print(f"  cd scripts/scrape-website")
        print(f"  uv run python app.py https://www.kenyalaw.org/ --concurrency 10 --delay 5.0 --timeout 60")
        sys.exit(1)

    md_files = list(text_path.rglob('*.md'))
    print(f"Found {len(md_files)} Markdown files in {text_dir}")

    cases = []
    legislation = []
    gazettes = []
    bills = []
    articles = []
    documents = []

    for i, filepath in enumerate(md_files):
        if (i + 1) % 1000 == 0:
            print(f"  Processing {i + 1}/{len(md_files)}...")

        result = process_file(filepath)
        if not result:
            continue

        doc_type = result.get('type', 'document')
        if doc_type == 'case':
            cases.append(result)
        elif doc_type == 'legislation':
            legislation.append(result)
        elif doc_type == 'gazette':
            gazettes.append(result)
        elif doc_type == 'bill':
            bills.append(result)
        elif doc_type == 'article':
            articles.append(result)
        else:
            documents.append(result)

    # Write outputs
    outputs = {
        'cases.json': cases,
        'legislation.json': legislation,
        'gazettes.json': gazettes,
        'bills.json': bills,
        'articles.json': articles,
        'documents.json': documents,
    }

    for filename, data in outputs.items():
        filepath = out_path / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  Written {filepath}: {len(data)} items")

    # Write combined index
    all_items = cases + legislation + gazettes + bills + articles + documents
    with open(out_path / 'all_metadata.json', 'w', encoding='utf-8') as f:
        json.dump(all_items, f, indent=2, ensure_ascii=False)
    print(f"\nTotal: {len(all_items)} documents indexed")
    print(f"  Cases: {len(cases)}")
    print(f"  Legislation: {len(legislation)}")
    print(f"  Gazettes: {len(gazettes)}")
    print(f"  Bills: {len(bills)}")
    print(f"  Articles: {len(articles)}")
    print(f"  Other: {len(documents)}")

    return all_items


if __name__ == '__main__':
    text_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/kenyalaw.org/text'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'data/brain/metadata'
    build_metadata(text_dir, output_dir)
