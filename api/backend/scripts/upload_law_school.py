"""
Bulk upload law school files to Cloudinary.
Preserves folder structure: juriscore/law-school/{course}/{subcategory}/{filename}
"""
import os
import sys
import time
import json
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from api.backend.services.cloudinary_service import upload_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("upload")

# Source directory
LAW_SCHOOL_DIR = Path(os.getenv("LAW_SCHOOL_DIR", "C:/Users/pixel/Documents/Law_School"))

# Cloudinary folder prefix
CDN_PREFIX = "juriscore/law-school"

# Extensions to upload
UPLOAD_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".xlsx", ".csv"}

# Directories to skip
SKIP_DIRS = {"extracted_text", "graphify-out", "NotebookLM", "Scripts", "Archives"}

# Resource type mapping
RESOURCE_TYPE_MAP = {
    ".pdf": "raw",
    ".docx": "raw",
    ".doc": "raw",
    ".pptx": "raw",
    ".ppt": "raw",
    ".txt": "raw",
    ".xlsx": "raw",
    ".csv": "raw",
}

# Progress file
PROGRESS_FILE = Path(__file__).parent / "upload_progress.json"


def load_progress():
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"uploaded": [], "failed": [], "last_index": 0}


def save_progress(progress):
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


def get_course_name(rel_path: str) -> str:
    """Extract course name from relative path."""
    parts = Path(rel_path).parts
    if parts:
        return parts[0]
    return "general"


def collect_files():
    """Collect all uploadable files with their relative paths."""
    files = []
    for root, dirs, filenames in os.walk(LAW_SCHOOL_DIR):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in sorted(filenames):
            ext = Path(fname).suffix.lower()
            if ext not in UPLOAD_EXTENSIONS:
                continue

            full_path = Path(root) / fname
            rel_path = full_path.relative_to(LAW_SCHOOL_DIR)
            files.append((str(full_path), str(rel_path)))

    return files


def upload_all(resume=True):
    """Upload all files to Cloudinary."""
    files = collect_files()
    total = len(files)
    logger.info(f"Found {total} files to upload")

    progress = load_progress() if resume else {"uploaded": [], "failed": [], "last_index": 0}
    uploaded_set = set(progress["uploaded"])

    success = 0
    failed = 0
    skipped = 0

    for i, (full_path, rel_path) in enumerate(files):
        # Skip already uploaded
        if rel_path in uploaded_set:
            skipped += 1
            continue

        # Build Cloudinary folder path
        course = get_course_name(rel_path)
        cloud_folder = f"{CDN_PREFIX}/{course}"

        # Determine tags
        tags = ["law-school", course.lower()]
        ext = Path(rel_path).suffix.lower()
        if "notes" in rel_path.lower():
            tags.append("lecture-notes")
        elif "assignment" in rel_path.lower():
            tags.append("assignment")
        elif "outline" in rel_path.lower():
            tags.append("course-outline")
        elif "research" in rel_path.lower():
            tags.append("research")

        try:
            result = upload_file(
                file_path=full_path,
                folder=cloud_folder,
                resource_type=RESOURCE_TYPE_MAP.get(ext, "auto"),
                tags=tags,
            )
            success += 1
            progress["uploaded"].append(rel_path)
            logger.info(f"[{i+1}/{total}] OK: {rel_path} -> {result['url'][:60]}...")
        except Exception as e:
            failed += 1
            progress["failed"].append({"path": rel_path, "error": str(e)})
            logger.error(f"[{i+1}/{total}] FAIL: {rel_path} -> {e}")

        # Save progress every 10 files
        if (i + 1) % 10 == 0:
            progress["last_index"] = i
            save_progress(progress)

        # Rate limit: Cloudinary allows ~1500 req/min for free tier
        if (i + 1) % 50 == 0:
            time.sleep(1)

    # Final save
    progress["last_index"] = total
    save_progress(progress)

    logger.info(f"\n{'='*60}")
    logger.info(f"Upload complete: {success} success, {failed} failed, {skipped} skipped")
    logger.info(f"Total files: {total}")
    logger.info(f"{'='*60}")

    return {"success": success, "failed": failed, "skipped": skipped, "total": total}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Upload law school files to Cloudinary")
    parser.add_argument("--fresh", action="store_true", help="Start fresh (ignore progress)")
    parser.add_argument("--dry-run", action="store_true", help="List files without uploading")
    args = parser.parse_args()

    if args.dry_run:
        files = collect_files()
        print(f"\nFiles to upload: {len(files)}")
        for i, (full, rel) in enumerate(files[:20]):
            course = get_course_name(rel)
            print(f"  [{i+1}] {rel}  (course: {course})")
        if len(files) > 20:
            print(f"  ... and {len(files)-20} more")
    else:
        result = upload_all(resume=not args.fresh)
        sys.exit(0 if result["failed"] == 0 else 1)
