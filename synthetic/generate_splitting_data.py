"""
Creates multi-page PDF packets for document SPLITTING training.

Real-world scenario: DHL receives a single PDF containing
Commercial Invoice + Packing List + COO + HAWB all together.
The model must identify page boundaries and classify each sub-document.

Output structure:
  Synthetic_Data_Splitting/
    pdfs/          packet_0001.pdf  (3-8 pages, mixed document types)
    annotations/   packet_0001.json (page ranges + class for each doc)

Each annotation:
{
  "packet_id": "packet_0001",
  "total_pages": 5,
  "documents": [
    {"doc_class": "Commercial Invoice", "class_index": 1,
     "page_start": 1, "page_end": 2, "source_doc": "ci_0042"},
    {"doc_class": "Packing List",       "class_index": 8,
     "page_start": 3, "page_end": 3, "source_doc": "pl_0117"},
    ...
  ]
}
"""
import json, random, argparse
from pathlib import Path
import fitz   # PyMuPDF

SYNTH_DIR  = Path(__file__).parent.parent / "Synthetic_Data"
OUTPUT_DIR = Path(__file__).parent.parent / "Synthetic_Data_Splitting"
PDF_OUT    = OUTPUT_DIR / "pdfs"
ANN_OUT    = OUTPUT_DIR / "annotations"

# ── Document class registry ───────────────────────────────────────────────
# Each entry: (folder_name, class_display_name, class_index, typical_pages)
# typical_pages: how many PDF pages this doc type usually has in real life
CLASS_REGISTRY = [
    ("01_Commercial_Invoice",           "Commercial Invoice",              1, [1,1,1,1,2]),
    ("02_House_Bill_of_Lading",         "House Bill of Lading",            2, [1,1,2]),
    ("03_Certificate_of_Origin",        "Certificate of Origin",           3, [1,1,1]),
    ("04_Shippers_Letter_of_Instruction","Shipper's Letter of Instruction", 4, [1,1,2]),
    ("05_Dangerous_Goods_Declaration",  "Dangerous Goods Declaration",     5, [1,1,2]),
    ("06_Verified_Gross_Mass",          "Verified Gross Mass",             6, [1,1]),
    ("07_House_Airway_Bill",            "House Airway Bill",               7, [1,1,1]),
    ("08_Packing_List",                 "Packing List",                    8, [1,1,2,2]),
    ("09_Customs_Declarations",         "Customs Declaration",             9, [1,1]),
    ("10_Cargo_Manifest",               "Cargo Manifest",                  10,[1,1,2]),
    ("11_Import_Export_License",        "Import/Export License",           11,[1,1,2]),
    ("12_Power_of_Attorney",            "Power of Attorney",               12,[1,1,1]),
]

# ── Realistic packet templates (which doc classes travel together) ─────────
# Based on actual DHL shipment document requirements
PACKET_TEMPLATES = [
    # Standard air export
    ["01","08","07"],
    # Standard air export + COO
    ["01","08","07","03"],
    # Air export with DG
    ["01","08","05","07"],
    # Air export full
    ["01","08","03","07","04"],
    # Ocean export basic
    ["01","08","02"],
    # Ocean export with COO
    ["01","08","02","03"],
    # Ocean export with VGM
    ["01","08","02","06"],
    # Ocean export full
    ["01","08","02","03","06","04"],
    # Ocean with DG
    ["01","08","02","05","06"],
    # Express courier (small parcel)
    ["01","09"],
    # Express courier with customs
    ["01","09","07"],
    # Import entry
    ["01","08","11"],
    # Full import packet
    ["01","08","11","10"],
    # With POA
    ["01","08","12","07"],
    # Full export with SLI
    ["01","08","04","03","07"],
    # Hazmat ocean full
    ["01","08","02","05","06","03"],
    # Complex mixed 6 doc types
    ["01","08","02","03","04","07"],
    # Manifest-heavy
    ["01","08","10","02","11"],
    # All-in export packet (7 docs)
    ["01","08","02","03","04","06","07"],
    # Random 3 — chosen at generation time
    "RANDOM_3",
    "RANDOM_4",
    "RANDOM_5",
]

def get_class_by_idx(idx_str):
    """Return (folder, display_name, class_index, pages_list) for a 2-digit index string."""
    for entry in CLASS_REGISTRY:
        if entry[0].startswith(idx_str + "_"):
            return entry
    return None

def get_pdf_pool(folder_name, sample_size=None):
    """Get all available PDFs for a class."""
    folder = SYNTH_DIR / folder_name / "pdfs"
    pdfs = sorted(folder.rglob("*.pdf"))
    if not pdfs:
        return []
    if sample_size:
        return random.choices(pdfs, k=sample_size)
    return pdfs

def build_packet(packet_id: int, template) -> dict | None:
    """
    Build one multi-page packet PDF from a template.
    Returns annotation dict or None if failed.
    """
    # Resolve template
    if template == "RANDOM_3":
        indices = random.sample([e[0][:2] for e in CLASS_REGISTRY], 3)
    elif template == "RANDOM_4":
        indices = random.sample([e[0][:2] for e in CLASS_REGISTRY], 4)
    elif template == "RANDOM_5":
        indices = random.sample([e[0][:2] for e in CLASS_REGISTRY], 5)
    else:
        indices = template

    # Build list of (class_entry, pdf_path) pairs
    doc_list = []
    used_classes = set()
    for idx in indices:
        entry = get_class_by_idx(idx)
        if not entry or idx in used_classes:
            continue
        used_classes.add(idx)
        pool = get_pdf_pool(entry[0])
        if not pool:
            continue
        pdf_path = random.choice(pool)
        doc_list.append((entry, pdf_path))

    if len(doc_list) < 2:
        return None   # need at least 2 docs for splitting

    # Shuffle order (real packets aren't always in the same order)
    random.shuffle(doc_list)

    # ── Merge PDFs with PyMuPDF ───────────────────────────────────────────
    fname     = f"packet_{packet_id:04d}.pdf"
    out_path  = PDF_OUT / fname
    merged    = fitz.open()

    documents = []
    current_page = 1

    for entry, pdf_path in doc_list:
        folder_name, class_name, class_index, _ = entry
        try:
            src = fitz.open(str(pdf_path))
        except Exception:
            continue

        n_pages_in_src = len(src)

        # Insert all pages from this document
        merged.insert_pdf(src)
        src.close()

        documents.append({
            "doc_class":    class_name,
            "class_index":  class_index,
            "page_start":   current_page,
            "page_end":     current_page + n_pages_in_src - 1,
            "n_pages":      n_pages_in_src,
            "source_file":  pdf_path.name,
            "source_class_folder": folder_name,
        })
        current_page += n_pages_in_src

    if len(merged) < 2:
        merged.close()
        return None

    # Optionally insert blank separator pages (mimics real scans, 20% chance)
    # — skip for now, can add later for augmentation

    merged.save(str(out_path))
    merged.close()

    annotation = {
        "packet_id":    fname.replace(".pdf", ""),
        "total_pages":  current_page - 1,
        "n_documents":  len(documents),
        "class_sequence": [d["doc_class"] for d in documents],
        "documents":    documents,
        "task":         "splitting",
    }
    (ANN_OUT / fname.replace(".pdf", ".json")).write_text(
        json.dumps(annotation, indent=2)
    )
    return annotation


def generate(count: int = 3000):
    PDF_OUT.mkdir(parents=True, exist_ok=True)
    ANN_OUT.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_OUT.glob("*.pdf")) + list(ANN_OUT.glob("*.json")):
        f.unlink()

    print(f"Generating {count} multi-page splitting packets...")
    ok = 0; fail = 0
    page_counts = []
    doc_counts  = []

    for i in range(1, count + 1):
        template = random.choice(PACKET_TEMPLATES)
        ann = build_packet(i, template)
        if ann:
            ok += 1
            page_counts.append(ann["total_pages"])
            doc_counts.append(ann["n_documents"])
            if i <= 5 or i % 500 == 0:
                seq = " + ".join(d["doc_class"][:12] for d in ann["documents"])
                print(f"  [{i:04d}] {ann['total_pages']}pp  {ann['n_documents']} docs  |  {seq}")
        else:
            fail += 1

    print(f"\nResults: {ok} packets generated, {fail} failed")
    if page_counts:
        print(f"Avg pages/packet: {sum(page_counts)/len(page_counts):.1f}  "
              f"(min={min(page_counts)}, max={max(page_counts)})")
        print(f"Avg docs/packet:  {sum(doc_counts)/len(doc_counts):.1f}  "
              f"(min={min(doc_counts)}, max={max(doc_counts)})")
    print(f"Done -> {OUTPUT_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Generate multi-page document packets for splitting task training")
    p.add_argument("--count", type=int, default=3000,
                   help="Number of multi-page packets to generate (default 3000)")
    generate(p.parse_args().count)
