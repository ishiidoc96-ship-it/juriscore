"""
Generate NVIDIA vector embeddings for semantic search over KenyaLaw data.

Uses NVIDIA NIM API to generate embeddings for all metadata items.
Output: data/brain/embeddings/embeddings.json
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
EMBEDDING_MODEL = "nvidia/nv-embedqa-e5-v5"  # Free NVIDIA embedding model


def get_api_key() -> str:
    """Get NVIDIA API key from env."""
    key = NVIDIA_API_KEY
    if not key:
        key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        print("Error: NVIDIA_API_KEY not set. Set it in your environment.")
        sys.exit(1)
    return key


def generate_embeddings_batch(texts: List[str], api_key: str) -> List[List[float]]:
    """Generate embeddings for a batch of texts using NVIDIA NIM API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": EMBEDDING_MODEL,
        "input": texts,
        "input_type": "query",
        "encoding_format": "float",
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{NVIDIA_BASE_URL}/embeddings",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]
    except Exception as e:
        print(f"  Error generating embeddings: {e}")
        return []


def build_embedding_text(item: Dict) -> str:
    """Build text to embed from a metadata item."""
    parts = []
    if item.get("title"):
        parts.append(item["title"])
    if item.get("citation"):
        parts.append(item["citation"])
    if item.get("court"):
        parts.append(f"Court: {item['court']}")
    if item.get("topics"):
        parts.append(f"Topics: {', '.join(item['topics'])}")
    if item.get("excerpt"):
        parts.append(item["excerpt"][:300])
    return " | ".join(parts)


def build_embeddings(metadata_dir: str, output_dir: str, batch_size: int = 100):
    """Generate embeddings for all metadata items."""
    api_key = get_api_key()
    meta_path = Path(metadata_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Load all metadata
    all_items = []
    for filename in ["cases.json", "legislation.json", "gazettes.json", "bills.json", "articles.json"]:
        filepath = meta_path / filename
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                items = json.load(f)
                all_items.extend(items)
                print(f"  Loaded {len(items)} items from {filename}")

    if not all_items:
        print("No metadata found. Run build_metadata.py first.")
        sys.exit(1)

    print(f"\nGenerating embeddings for {len(all_items)} items...")
    print(f"  Model: {EMBEDDING_MODEL}")
    print(f"  Batch size: {batch_size}")

    embeddings = []
    texts = []
    metadata = []

    for i, item in enumerate(all_items):
        text = build_embedding_text(item)
        texts.append(text)
        metadata.append({
            "title": item.get("title", ""),
            "type": item.get("type", ""),
            "url": item.get("url", ""),
            "court": item.get("court", ""),
            "year": item.get("year", 0),
        })

        # Process batch
        if len(texts) >= batch_size or i == len(all_items) - 1:
            batch_num = (i + 1) // batch_size
            print(f"  Batch {batch_num}: embedding {len(texts)} items...")

            batch_embeddings = generate_embeddings_batch(texts, api_key)
            for emb in batch_embeddings:
                embeddings.append(emb)

            texts = []
            time.sleep(0.5)  # Rate limit

    # Save embeddings
    output = {
        "model": EMBEDDING_MODEL,
        "dimension": len(embeddings[0]) if embeddings else 0,
        "count": len(embeddings),
        "embeddings": embeddings,
        "metadata": metadata[:len(embeddings)],
    }

    output_file = out_path / "embeddings.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f)

    print(f"\nDone! Written {output_file}")
    print(f"  Total embeddings: {len(embeddings)}")
    print(f"  Dimension: {output['dimension']}")


if __name__ == "__main__":
    metadata_dir = sys.argv[1] if len(sys.argv) > 1 else "data/brain/metadata"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "data/brain/embeddings"
    build_embeddings(metadata_dir, output_dir)
