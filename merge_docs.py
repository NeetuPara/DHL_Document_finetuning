"""
Merges all blank template PDFs from Documents/ into two output PDFs.
Sorted by document class number (01-12).
Each source PDF contributes its first page only (keeps output compact).

Output:
  Documents/blank_templates_part1.pdf  (~10 pages)
  Documents/blank_templates_part2.pdf  (~9 pages)

Run:
  pip install pypdf
  python merge_docs.py
"""

from pathlib import Path

try:
    from pypdf import PdfWriter, PdfReader
except ImportError:
    from PyPDF2 import PdfWriter, PdfReader

BASE = Path(__file__).parent / "Documents"

# All PDFs sorted by class folder number then filename
pdf_files = sorted(BASE.rglob("*.pdf"), key=lambda p: p.parts)

print(f"Found {len(pdf_files)} PDFs:\n")
for p in pdf_files:
    print(f"  {p.relative_to(BASE)}")

# Collect first page from each PDF
pages = []   # list of (source_path, page_object)
for pdf_path in pdf_files:
    try:
        reader = PdfReader(str(pdf_path))
        if len(reader.pages) == 0:
            print(f"  SKIP (0 pages): {pdf_path.name}")
            continue
        pages.append((pdf_path, reader.pages[0]))
        print(f"  OK  ({len(reader.pages)} pages, using p1): {pdf_path.name}")
    except Exception as e:
        print(f"  ERR {pdf_path.name}: {e}")

print(f"\nTotal pages collected: {len(pages)}")

# Split into two roughly equal halves
mid = len(pages) // 2

def write_pdf(page_list, out_path):
    writer = PdfWriter()
    for _, page in page_list:
        writer.add_page(page)
    with open(out_path, "wb") as f:
        writer.write(f)
    size_mb = out_path.stat().st_size / 1e6
    print(f"  Saved: {out_path.name}  ({len(page_list)} pages, {size_mb:.1f} MB)")

print("\nWriting output PDFs ...")
out1 = BASE / "blank_templates_part1.pdf"
out2 = BASE / "blank_templates_part2.pdf"

write_pdf(pages[:mid],  out1)
write_pdf(pages[mid:],  out2)

print("\nDone.")
print(f"  Part 1: {mid} pages — {[p.name for p, _ in pages[:mid]]}")
print(f"  Part 2: {len(pages)-mid} pages — {[p.name for p, _ in pages[mid:]]}")
