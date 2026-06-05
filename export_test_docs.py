"""
Export source PDFs for all records in test.jsonl into a dedicated folder.

Output structure:
  test_documents/
    splitting_packets/   ← multi-doc PDFs (test the full pipeline)
    single_docs/         ← single-page PDFs per class
    multi_page/          ← 2-page PDFs per class

Run:
    python export_test_docs.py
"""
import json, shutil
from pathlib import Path
from collections import defaultdict, Counter

BASE     = Path(__file__).parent
TV2      = BASE / "Training_Data_v2"
SYNTH    = BASE / "Synthetic_Data"
SYNTH_MP = BASE / "Synthetic_Data_MultiPage"
SPLIT    = BASE / "Synthetic_Data_Splitting_v2"
OUT      = BASE / "test_documents"

CLASS_FOLDER = {
    "Commercial Invoice":              "01_Commercial_Invoice",
    "House Bill of Lading":            "02_House_Bill_of_Lading",
    "Certificate of Origin":           "03_Certificate_of_Origin",
    "Shipper's Letter of Instruction": "04_Shippers_Letter_of_Instruction",
    "Dangerous Goods Declaration":     "05_Dangerous_Goods_Declaration",
    "Verified Gross Mass":             "06_Verified_Gross_Mass",
    "House Airway Bill":               "07_House_Airway_Bill",
    "Packing List":                    "08_Packing_List",
    "Customs Declaration":             "09_Customs_Declarations",
    "Cargo Manifest":                  "10_Cargo_Manifest",
    "Import/Export License":           "11_Import_Export_License",
    "Power of Attorney":               "12_Power_of_Attorney",
}

def pdf_from_image(image_rel: str, source: str, doc_class: str = None) -> Path | None:
    """Derive source PDF path from the JSONL image field."""
    parts = Path(image_rel).stem  # e.g. 'packet_1632_p2' or 'commercial_invoice_0042'

    if source == "splitting_packet":
        # images/packets/packet_XXXX_pN.png  →  Synthetic_Data_Splitting_v2/pdfs/packet_XXXX.pdf
        pid = parts.rsplit("_p", 1)[0]      # 'packet_1632'
        return SPLIT / "pdfs" / f"{pid}.pdf"

    if source == "single_doc":
        # images/single/<class_folder>/<stem>.png  →  Synthetic_Data/<class_folder>/pdfs/<stem>.pdf
        # prepare_dataset_v2 may append _p1 to single-page images for consistency — strip it
        folder = CLASS_FOLDER.get(doc_class)
        if not folder:
            return None
        import re as _re
        base_stem = _re.sub(r"_p\d+$", "", parts)
        return SYNTH / folder / "pdfs" / f"{base_stem}.pdf"

    if source == "multi_doc":
        # images/multi/<class_folder>/<stem>_p1.png  →  Synthetic_Data_MultiPage/<class_folder>/pdfs/<stem_no_p>.pdf
        folder = CLASS_FOLDER.get(doc_class)
        if not folder:
            return None
        base_stem = parts.rsplit("_p", 1)[0]   # strip _p1 / _p2
        return SYNTH_MP / folder / "pdfs" / f"{base_stem}.pdf"

    return None


def main():
    # ── Recreate output folder ────────────────────────────────────────────────
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "splitting_packets").mkdir(parents=True)
    (OUT / "single_docs").mkdir(parents=True)
    (OUT / "multi_page").mkdir(parents=True)

    # ── Read test.jsonl ───────────────────────────────────────────────────────
    records = []
    with open(TV2 / "test.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    print(f"Test records: {len(records):,}")

    # ── Collect unique PDFs ───────────────────────────────────────────────────
    seen     = set()
    copied   = Counter()
    missing  = []

    for r in records:
        source = r.get("source", "")
        image  = r.get("image", "")
        try:
            lbl = json.loads(r["label"])
            doc_class = lbl.get("class")
        except Exception:
            doc_class = None

        pdf_path = pdf_from_image(image, source, doc_class)
        if pdf_path is None or str(pdf_path) in seen:
            continue
        seen.add(str(pdf_path))

        if not pdf_path.exists():
            missing.append(str(pdf_path))
            continue

        # Destination subfolder
        if source == "splitting_packet":
            dest_dir = OUT / "splitting_packets"
        elif source == "single_doc":
            folder   = CLASS_FOLDER.get(doc_class, "unknown")
            dest_dir = OUT / "single_docs" / folder
            dest_dir.mkdir(parents=True, exist_ok=True)
        else:
            folder   = CLASS_FOLDER.get(doc_class, "unknown")
            dest_dir = OUT / "multi_page" / folder
            dest_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(pdf_path, dest_dir / pdf_path.name)
        copied[source] += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\nCopied PDFs:")
    print(f"  splitting_packets : {copied['splitting_packet']:>4}")
    print(f"  single_docs       : {copied['single_doc']:>4}")
    print(f"  multi_page        : {copied['multi_doc']:>4}")
    print(f"  Total             : {sum(copied.values()):>4}")
    if missing:
        print(f"\nMissing ({len(missing)}) — PDFs not found on disk:")
        for m in missing[:5]:
            print(f"  {m}")

    print(f"\nOutput: {OUT}")
    print(f"\nFolder structure:")
    for sub in sorted(OUT.rglob("*.pdf")):
        rel = sub.relative_to(OUT)
        print(f"  {rel}")


if __name__ == "__main__":
    main()
