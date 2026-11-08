"""Läser ut texten ur alla PDF-filer i mappen pdf_in och skriver ut den.

Användning (från projektmappen):
    python src/pdf_text.py
"""

import sys
from pathlib import Path

from pypdf import PdfReader

# Projektmappen är mappen ovanför src/
PROJECT_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = PROJECT_DIR / "pdf_in"


def extract_text(pdf_path: Path) -> str:
    """Returnerar all text i PDF:en, sida för sida, med tom rad mellan sidorna."""
    reader = PdfReader(pdf_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip()


def main() -> None:
    if not PDF_DIR.is_dir():
        sys.exit(f"Mappen finns inte: {PDF_DIR}")

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        sys.exit(f"Inga PDF-filer hittades i {PDF_DIR}")

    for pdf_path in pdf_files:
        text = extract_text(pdf_path)
        print(f"===== {pdf_path.name} =====")
        if text:
            print(text)
        else:
            print("(Ingen text hittades. PDF:en är troligen en skannad bild, kräver OCR.)")
        print()


if __name__ == "__main__":
    main()
