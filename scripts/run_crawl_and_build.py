"""
KenyaLaw Brain Pipeline — Full setup and build script.

This script:
1. Installs the crawler (scrape-website)
2. Crawls kenyalaw.org
3. Builds metadata index
4. Builds knowledge graph
5. Generates embeddings
6. Integrates with backend

Run: python scripts/run_crawl_and_build.py [step]
Steps: crawl, metadata, graph, embeddings, all
"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SCRAPE_DIR = PROJECT_ROOT / "scripts" / "scrape-website"
DATA_DIR = PROJECT_ROOT / "data"
BRAIN_DIR = DATA_DIR / "brain"
CRAWL_OUTPUT = DATA_DIR / "kenyalaw.org"


def run(cmd: list, cwd: str = None, env: dict = None):
    """Run a command and stream output."""
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    result = subprocess.run(cmd, cwd=cwd or str(PROJECT_ROOT), env=env)
    if result.returncode != 0:
        print(f"Error: Command failed with return code {result.returncode}")
        sys.exit(1)
    return result


def step_install():
    """Install the scraper."""
    print("\n[STEP 1] Installing scrape-website crawler...")
    run(["pip", "install", "aiohttp", "aiofiles", "aiodns", "lxml",
         "trafilatura", "protego", "aiolimiter", "httpx"])


def step_crawl():
    """Crawl kenyalaw.org."""
    print("\n[STEP 2] Crawling kenyalaw.org...")
    print("  This may take several hours for a full crawl.")
    print("  Output: data/kenyalaw.org/text/")

    # Ensure output directory exists
    CRAWL_OUTPUT.mkdir(parents=True, exist_ok=True)

    # Run the crawler
    # Use moderate concurrency to respect kenyalaw.org's rate limits
    cmd = [
        sys.executable, "-m", "scrape_website.cli",
        "https://www.kenyalaw.org/",
        "--concurrency", "10",
        "--delay", "5.0",
        "--timeout", "60",
        "--concurrency", "10",
    ]

    # If uv is available, use it
    uv_path = SCRAPE_DIR / ".venv" / "Scripts" / "uv.exe"
    if uv_path.exists():
        cmd = ["uv", "run", "python", "-m", "scrape_website.cli",
               "https://www.kenyalaw.org/",
               "--concurrency", "10",
               "--delay", "5.0",
               "--timeout", "60"]
        run(cmd, cwd=str(SCRAPE_DIR))
    else:
        # Fallback to direct Python
        try:
            import scrape_website
            run(cmd)
        except ImportError:
            print("  scrape-website not installed. Installing...")
            step_install()
            run(cmd)


def step_metadata():
    """Build metadata index."""
    print("\n[STEP 3] Building metadata index...")
    run([
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "build_metadata.py"),
        str(CRAWL_OUTPUT / "text"),
        str(BRAIN_DIR / "metadata"),
    ])


def step_graph():
    """Build knowledge graph."""
    print("\n[STEP 4] Building knowledge graph...")
    run([
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "build_graph.py"),
        str(BRAIN_DIR / "metadata"),
        str(CRAWL_OUTPUT / "text"),
        str(BRAIN_DIR / "graph"),
    ])


def step_embeddings():
    """Generate embeddings."""
    print("\n[STEP 5] Generating NVIDIA embeddings...")
    print("  Requires NVIDIA_API_KEY environment variable.")
    run([
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "build_embeddings.py"),
        str(BRAIN_DIR / "metadata"),
        str(BRAIN_DIR / "embeddings"),
    ])


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"

    print("=" * 60)
    print("KenyaLaw Brain Pipeline")
    print("=" * 60)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data dir: {DATA_DIR}")
    print(f"Brain dir: {BRAIN_DIR}")
    print(f"Step: {step}")
    print()

    steps = {
        "install": [step_install],
        "crawl": [step_crawl],
        "metadata": [step_metadata],
        "graph": [step_graph],
        "embeddings": [step_embeddings],
        "all": [step_install, step_crawl, step_metadata, step_graph, step_embeddings],
    }

    if step not in steps:
        print(f"Unknown step: {step}")
        print(f"Available: {', '.join(steps.keys())}")
        sys.exit(1)

    for s in steps[step]:
        s()

    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)
    print(f"\nBrain data location: {BRAIN_DIR}")
    print("To use in the app, set BRAIN_DIR environment variable.")


if __name__ == "__main__":
    main()
