"""
Build a knowledge graph from crawled KenyaLaw metadata.

Creates relationship maps:
- topic_cases.json: Topic → Case relationships
- topic_statutes.json: Topic → Statute relationships
- case_citations.json: Case → Cited cases
- court_hierarchy.json: Court structure + jurisdiction
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


COURT_HIERARCHY = {
    'Supreme Court': {
        'level': 1,
        'jurisdiction': 'Constitutional matters, election petitions, appeals from Court of Appeal',
        'precedent_value': 'binding on all courts',
    },
    'Court of Appeal': {
        'level': 2,
        'jurisdiction': 'Appeals from High Court, criminal and civil matters',
        'precedent_value': 'binding on High Court and below',
    },
    'High Court': {
        'level': 3,
        'jurisdiction': 'Original jurisdiction in constitutional matters, serious criminal cases, civil disputes over KES 20M',
        'precedent_value': 'binding on subordinate courts',
    },
    'Environment and Land Court': {
        'level': 3,
        'jurisdiction': 'Environmental matters, land disputes, planning',
        'precedent_value': 'binding on subordinate courts in land matters',
    },
    'Employment and Labour Relations Court': {
        'level': 3,
        'jurisdiction': 'Employment disputes, labour relations, trade unions',
        'precedent_value': 'binding on subordinate courts in employment matters',
    },
    "Magistrate's Court": {
        'level': 4,
        'jurisdiction': 'Criminal cases (less serious), civil disputes under KES 20M',
        'precedent_value': 'persuasive only',
    },
    "Kadhi's Court": {
        'level': 4,
        'jurisdiction': 'Muslim family law (marriage, divorce, inheritance) for Muslim parties',
        'precedent_value': 'persuasive only',
    },
    'Small Claims Court': {
        'level': 4,
        'jurisdiction': 'Civil claims up to KES 1 million, simplified procedures',
        'precedent_value': 'persuasive only',
    },
}


def build_topic_cases(cases: List[Dict]) -> Dict[str, List[Dict]]:
    """Build topic → case relationships."""
    topic_cases = defaultdict(list)
    for case in cases:
        topics = case.get('topics', [])
        for topic in topics:
            topic_cases[topic].append({
                'title': case.get('title', ''),
                'citation': case.get('citation', ''),
                'court': case.get('court', ''),
                'year': case.get('year', 0),
                'url': case.get('url', ''),
                'excerpt': case.get('excerpt', '')[:200],
            })
    # Sort by count descending
    return dict(sorted(topic_cases.items(), key=lambda x: -len(x[1])))


def build_topic_statutes(legislation: List[Dict]) -> Dict[str, List[Dict]]:
    """Build topic → statute relationships."""
    topic_statutes = defaultdict(list)
    for stat in legislation:
        topics = stat.get('topics', [])
        for topic in topics:
            topic_statutes[topic].append({
                'title': stat.get('title', ''),
                'cap_number': stat.get('cap_number', ''),
                'year': stat.get('year', 0),
                'url': stat.get('url', ''),
                'excerpt': stat.get('excerpt', '')[:200],
            })
    return dict(sorted(topic_statutes.items(), key=lambda x: -len(x[1])))


def build_case_citations(cases: List[Dict]) -> Dict[str, List[str]]:
    """Build case → cited cases relationships by analyzing title patterns."""
    citations = {}
    case_titles = {c.get('title', '').lower(): c.get('title', '') for c in cases}

    for case in cases:
        title = case.get('title', '')
        cited = []

        # Look for "v" or "vs" patterns (case names)
        v_match = re.search(r'\bv\b|\bvs\b|\bversus\b', title, re.IGNORECASE)
        if v_match:
            # Extract parties
            parties = re.split(r'\bv\b|\bvs\b|\bversus\b', title, flags=re.IGNORECASE)
            if len(parties) >= 2:
                defendant = parties[1].strip()
                # Look up defendant in our cases
                for ct_title in case_titles.values():
                    if defendant.lower() in ct_title.lower() or ct_title.lower() in defendant.lower():
                        cited.append(ct_title)

        if cited:
            citations[title] = cited[:5]

    return citations


def build_full_text_index(text_dir: str) -> Dict[str, str]:
    """Build a URL → full text index from crawled Markdown files."""
    text_path = Path(text_dir)
    index = {}

    if not text_path.exists():
        return index

    for filepath in text_path.rglob('*.md'):
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            # Extract URL from frontmatter
            url_match = re.search(r'url:\s*(.+)', content)
            if url_match:
                url = url_match.group(1).strip()
                # Strip frontmatter, keep content
                body_start = content.find('---', 3)
                if body_start > 0:
                    body_start = content.find('---', body_start + 3) + 3
                    body = content[body_start:].strip()[:5000]  # Limit to 5K chars
                    index[url] = body
        except Exception:
            continue

    return index


def build_graph(metadata_dir: str, text_dir: str, output_dir: str):
    """Build the complete knowledge graph."""
    meta_path = Path(metadata_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Load metadata
    cases_file = meta_path / 'cases.json'
    legislation_file = meta_path / 'legislation.json'

    if not cases_file.exists():
        print(f"Error: {cases_file} not found. Run build_metadata.py first.")
        sys.exit(1)

    with open(cases_file, encoding='utf-8') as f:
        cases = json.load(f)
    with open(legislation_file, encoding='utf-8') as f:
        legislation = json.load(f)

    print(f"Building graph from {len(cases)} cases and {len(legislation)} statutes...")

    # Build relationships
    topic_cases = build_topic_cases(cases)
    topic_statutes = build_topic_statutes(legislation)
    case_citations = build_case_citations(cases)

    # Write outputs
    outputs = {
        'topic_cases.json': topic_cases,
        'topic_statutes.json': topic_statutes,
        'case_citations.json': case_citations,
        'court_hierarchy.json': COURT_HIERARCHY,
    }

    for filename, data in outputs.items():
        filepath = out_path / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        count = len(data) if isinstance(data, (dict, list)) else 0
        print(f"  Written {filepath}: {count} entries")

    # Build full-text index if text directory exists
    text_path = Path(text_dir)
    if text_path.exists():
        print(f"\nBuilding full-text index from {text_dir}...")
        full_text_index = build_full_text_index(text_dir)
        with open(out_path / 'full_text_index.json', 'w', encoding='utf-8') as f:
            json.dump(full_text_index, f, indent=2, ensure_ascii=False)
        print(f"  Written full_text_index.json: {len(full_text_index)} documents")
    else:
        print(f"\nSkipping full-text index (text dir not found: {text_dir})")

    print(f"\nGraph built successfully!")
    print(f"  Topics with cases: {len(topic_cases)}")
    print(f"  Topics with statutes: {len(topic_statutes)}")
    print(f"  Case citation links: {len(case_citations)}")


if __name__ == '__main__':
    metadata_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/brain/metadata'
    text_dir = sys.argv[2] if len(sys.argv) > 2 else 'data/kenyalaw.org/text'
    output_dir = sys.argv[3] if len(sys.argv) > 3 else 'data/brain/graph'
    build_graph(metadata_dir, text_dir, output_dir)
