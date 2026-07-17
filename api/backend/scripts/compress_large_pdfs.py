"""
Compress large PDFs to fit Cloudinary's 10MB limit using pikepdf.
"""
import os
import sys
from pathlib import Path
import pikepdf

# Files to compress
FILES = [
    r"C:\Users\pixel\Documents\Law_School\General\Downloads\Books\(Oxford Handbooks) Shannon Vallor - The Oxford Handbook Of Philosophy Of Technology-Oxford University Press (2022).pdf",
    r"C:\Users\pixel\Documents\Law_School\KLS_112_Constitutional_Law\Lecture_Notes\Kenya Gazette Vol CXIXNo 93.pdf"
]

# Target size (9MB to be safe under 10MB limit)
TARGET_SIZE_MB = 9
TARGET_SIZE_BYTES = TARGET_SIZE_MB * 1024 * 1024

# Output directory
OUTPUT_DIR = Path(r"C:\Users\pixel\Documents\Law_School\compressed")

def compress_pdf(input_path: str, output_path: str) -> bool:
    """Compress a PDF file using pikepdf."""
    try:
        with pikepdf.open(input_path) as pdf:
            # Save with compression options
            pdf.save(
                output_path,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                normalize_content=True
            )

        # Check result size
        original_size = os.path.getsize(input_path)
        compressed_size = os.path.getsize(output_path)
        reduction = (1 - compressed_size / original_size) * 100

        print(f"Original: {original_size / 1024 / 1024:.1f}MB")
        print(f"Compressed: {compressed_size / 1024 / 1024:.1f}MB")
        print(f"Reduction: {reduction:.1f}%")

        return compressed_size <= TARGET_SIZE_BYTES

    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    for file_path in FILES:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue

        print(f"\nProcessing: {os.path.basename(file_path)}")
        output_path = OUTPUT_DIR / os.path.basename(file_path)

        if compress_pdf(file_path, str(output_path)):
            print("[OK] Compressed successfully")
        else:
            print("[FAIL] Still too large")

if __name__ == "__main__":
    main()
