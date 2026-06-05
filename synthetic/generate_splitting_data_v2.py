"""
Multi-page document SPLITTING training data — v2

Real-world rules:
1. A packet PDF can be 2-10+ pages total
2. A SINGLE document (e.g. Commercial Invoice) can span multiple consecutive pages
   (pages 1-2 = SAME invoice, continuation — NOT two different invoices)
3. Multiple documents of the SAME class can appear in ONE packet
   (e.g. packet has 2 CIs: pages 1-2 are CI#001, pages 3-4 are CI#002)
4. Document order is random (reflects real mixed packet submissions)
5. Single-page docs (COO, VGM, HAWB) and multi-page docs (CI, PL, Manifest) mixed

Annotation records:
  [
    {class: "Commercial Invoice", page_start:1, page_end:2, is_continuation: true},
    {class: "Packing List",       page_start:3, page_end:4, is_continuation: true},
    {class: "Certificate of Origin", page_start:5, page_end:5},
    {class: "House Airway Bill",  page_start:6, page_end:6},
  ]

Output: Synthetic_Data_Splitting_v2/  (separate folder, never touches other data)
"""
import json, random, argparse
from pathlib import Path
import fitz  # PyMuPDF

BASE       = Path(__file__).parent.parent
SYNTH_DIR  = BASE / "Synthetic_Data"          # single-page docs
MP_DIR     = BASE / "Synthetic_Data_MultiPage" # multi-page docs (CI, PL, Manifest)
OUTPUT_DIR = BASE / "Synthetic_Data_Splitting_v2"
PDF_OUT    = OUTPUT_DIR / "pdfs"
ANN_OUT    = OUTPUT_DIR / "annotations"

# ── Class registry: all 12 classes ────────────────────────────────────────
# (class_index, display_name, folder_in_synth, can_be_multipage, mp_folder)
CLASSES = [
    (1,  "Commercial Invoice",              "01_Commercial_Invoice",              True,  "01_Commercial_Invoice"),
    (2,  "House Bill of Lading",            "02_House_Bill_of_Lading",            True,  "02_House_Bill_of_Lading"),
    (3,  "Certificate of Origin",           "03_Certificate_of_Origin",           False, None),
    (4,  "Shipper's Letter of Instruction", "04_Shippers_Letter_of_Instruction",  True,  "04_Shippers_Letter_of_Instruction"),
    (5,  "Dangerous Goods Declaration",     "05_Dangerous_Goods_Declaration",     True,  "05_Dangerous_Goods_Declaration"),
    (6,  "Verified Gross Mass",             "06_Verified_Gross_Mass",             True,  "06_Verified_Gross_Mass"),
    (7,  "House Airway Bill",               "07_House_Airway_Bill",               False, None),
    (8,  "Packing List",                    "08_Packing_List",                    True,  "08_Packing_List"),
    (9,  "Customs Declaration",             "09_Customs_Declarations",            False, None),
    (10, "Cargo Manifest",                  "10_Cargo_Manifest",                  True,  "10_Cargo_Manifest"),
    (11, "Import/Export License",           "11_Import_Export_License",           True,  "11_Import_Export_License"),
    (12, "Power of Attorney",               "12_Power_of_Attorney",               False, None),
]
CLASS_BY_IDX = {c[0]: c for c in CLASSES}

# ── Pool helpers ─────────────────────────────────────────────────────────
_single_pools = {}
_multi_pools  = {}

def get_single_pool(folder):
    if folder not in _single_pools:
        p = sorted((SYNTH_DIR / folder / "pdfs").rglob("*.pdf"))
        _single_pools[folder] = p
    return _single_pools[folder]

def get_multi_pool(mp_folder):
    if mp_folder not in _multi_pools:
        p = sorted((MP_DIR / mp_folder / "pdfs").rglob("*.pdf"))
        _multi_pools[mp_folder] = p
    return _multi_pools[mp_folder]

def pick_doc(class_entry, force_multipage=False):
    """
    Returns (pdf_path, is_multipage).
    If force_multipage and multi-page pool exists, use multi-page variant.
    Otherwise use single-page pool.
    """
    idx, name, folder, can_mp, mp_folder = class_entry
    if force_multipage and can_mp and mp_folder:
        pool = get_multi_pool(mp_folder)
        if pool:
            return random.choice(pool), True
    pool = get_single_pool(folder)
    if pool:
        return random.choice(pool), False
    return None, False


# ── Packet templates — realistic real-world combinations ─────────────────
# Each template is a list of (class_index, force_multipage)
# class_index can repeat (e.g. 2 CIs in one packet)
TEMPLATES = [
    # === COMPACT (2-4 pages) ===
    [(1,False),(8,False)],                            # CI + PL
    [(1,False),(9,False)],                            # CI + CN23
    [(1,False),(7,False)],                            # CI + HAWB
    [(1,False),(8,False),(7,False)],                  # CI + PL + HAWB
    [(1,False),(8,False),(3,False)],                  # CI + PL + COO
    [(1,False),(3,False),(7,False)],                  # CI + COO + HAWB

    # === STANDARD (4-6 pages) ===
    [(1,False),(8,False),(7,False),(3,False)],        # CI + PL + HAWB + COO
    [(1,False),(8,False),(2,False)],                  # CI + PL + HBL
    [(1,False),(8,False),(2,False),(3,False)],        # CI + PL + HBL + COO
    [(1,False),(8,False),(5,False),(7,False)],        # CI + PL + DGD + HAWB
    [(1,False),(8,False),(2,False),(6,False)],        # CI + PL + HBL + VGM
    [(1,False),(8,False),(4,False),(7,False)],        # CI + PL + SLI + HAWB
    [(1,False),(8,False),(12,False),(7,False)],       # CI + PL + POA + HAWB

    # === CI 2-PAGE continuation (4-7 pages) ===
    [(1,True),(8,False),(7,False)],                   # CI(2pp) + PL + HAWB
    [(1,True),(8,False),(3,False),(7,False)],         # CI(2pp) + PL + COO + HAWB
    [(1,True),(8,False),(2,False),(3,False)],         # CI(2pp) + PL + HBL + COO
    [(1,True),(8,False),(5,False),(2,False)],         # CI(2pp) + PL + DGD + HBL

    # === PL 2-PAGE continuation (5-8 pages) ===
    [(1,False),(8,True),(7,False)],                   # CI + PL(2pp) + HAWB
    [(1,False),(8,True),(3,False),(7,False)],         # CI + PL(2pp) + COO + HAWB
    [(1,True),(8,True),(7,False)],                    # CI(2pp) + PL(2pp) + HAWB

    # === BOTH multi-page (6-9 pages) ===
    [(1,True),(8,True),(3,False),(7,False)],          # CI(2pp) + PL(2pp) + COO + HAWB
    [(1,True),(8,True),(2,False),(6,False)],          # CI(2pp) + PL(2pp) + HBL + VGM
    [(1,True),(8,True),(5,False),(2,False),(6,False)],# CI(2pp) + PL(2pp) + DGD + HBL + VGM

    # === FULL OCEAN EXPORT (6-10 pages) ===
    [(1,True),(8,True),(2,False),(3,False),(6,False),(4,False)],    # all ocean docs
    [(1,True),(8,True),(2,False),(3,False),(5,False),(6,False)],    # with DGD
    [(1,True),(8,True),(2,False),(3,False),(4,False),(7,False),(12,False)],

    # === MANIFEST-HEAVY (5-8 pages) ===
    [(1,False),(8,False),(10,True),(11,False)],       # CI + PL + Manifest(2pp) + EEI
    [(1,False),(10,True),(2,False),(11,False)],       # CI + Manifest(2pp) + HBL + EEI
    [(1,True),(8,True),(10,True)],                    # CI(2pp) + PL(2pp) + Manifest(2pp)

    # === HBL multi-page ===
    [(1,False),(8,False),(2,True)],                  # CI + PL + HBL(2pp)
    [(1,True),(8,False),(2,True),(3,False)],         # CI(2pp) + PL + HBL(2pp) + COO
    [(1,False),(8,True),(2,True),(6,True)],          # CI + PL(2pp) + HBL(2pp) + VGM(2pp)

    # === DGD multi-page (multiple hazmat entries) ===
    [(1,False),(8,False),(5,True),(2,False)],        # CI + PL + DGD(2pp) + HBL
    [(1,True),(8,True),(5,True),(2,False)],          # CI(2pp) + PL(2pp) + DGD(2pp) + HBL
    [(5,True),(1,True),(8,False),(7,False)],         # DGD(2pp) + CI(2pp) + PL + HAWB

    # === SLI multi-page (complex export) ===
    [(4,True),(1,False),(8,False),(7,False)],        # SLI(2pp) + CI + PL + HAWB
    [(1,True),(4,True),(8,True),(7,False)],          # CI(2pp) + SLI(2pp) + PL(2pp) + HAWB
    [(4,True),(1,True),(8,False),(2,False),(3,False)],# SLI(2pp) + CI(2pp) + PL + HBL + COO

    # === VGM multi-page (multiple containers) ===
    [(1,False),(8,False),(2,False),(6,True)],        # CI + PL + HBL + VGM(2pp)
    [(1,True),(8,True),(2,True),(6,True)],           # CI(2pp) + PL(2pp) + HBL(2pp) + VGM(2pp)

    # === EEI multi-page (many HTS lines) ===
    [(1,True),(11,True),(8,False),(7,False)],        # CI(2pp) + EEI(2pp) + PL + HAWB
    [(11,True),(1,True),(8,True),(2,False)],         # EEI(2pp) + CI(2pp) + PL(2pp) + HBL

    # === SAME CLASS APPEARS TWICE (different documents of same type) ===
    [(1,False),(1,False),(8,False),(7,False)],        # 2× CI + PL + HAWB  (e.g. 2 shippers)
    [(1,False),(1,False),(8,False),(8,False)],        # 2× CI + 2× PL
    [(1,True),(1,False),(8,False),(7,False)],         # CI(2pp) + CI(1pp) + PL + HAWB
    [(1,True),(1,True),(8,False),(7,False)],          # CI(2pp) + CI(2pp) + PL + HAWB
    [(3,False),(3,False),(1,False),(8,False)],        # 2× COO (diff goods batches) + CI + PL
    [(5,False),(5,False),(1,False),(8,False),(2,False)],  # 2× DGD(1pp) + CI + PL + HBL
    [(5,True),(5,False),(1,True),(8,False)],          # DGD(2pp) + DGD(1pp) + CI(2pp) + PL
    [(2,True),(2,False),(1,True),(8,False),(3,False)],# HBL(2pp) + HBL(1pp) + CI(2pp) + PL + COO
    [(8,True),(8,False),(1,False),(7,False),(3,False)],# PL(2pp) + PL(1pp) + CI + HAWB + COO

    # === 9-10 PAGE COMPLEX PACKETS ===
    [(1,True),(8,True),(2,True),(3,False),(4,True),(5,False),(6,True)],
    [(1,True),(1,False),(8,True),(2,False),(3,False),(7,False),(12,False)],
    [(1,True),(8,True),(10,True),(2,True),(3,False),(4,True)],
    [(5,True),(1,True),(8,True),(2,True),(6,True)],
    [(4,True),(1,True),(1,False),(8,True),(7,False),(3,False)],
]


def build_packet(packet_id: int) -> dict | None:
    template = random.choice(TEMPLATES)

    doc_blocks = []   # list of (class_entry, pdf_path, is_multipage)
    for cls_idx, force_mp in template:
        entry = CLASS_BY_IDX[cls_idx]
        pdf_path, is_mp = pick_doc(entry, force_multipage=force_mp)
        if pdf_path is None:
            continue
        doc_blocks.append((entry, pdf_path, is_mp))

    if len(doc_blocks) < 2:
        return None

    # Shuffle order — in real life packets aren't always in the same order
    random.shuffle(doc_blocks)

    # ── Merge into one PDF ────────────────────────────────────────────────
    fname    = f"packet_{packet_id:04d}.pdf"
    merged   = fitz.open()
    documents = []
    cur_page  = 1

    for entry, pdf_path, is_mp in doc_blocks:
        idx, cls_name, folder, _, _ = entry
        try:
            src = fitz.open(str(pdf_path))
        except Exception:
            continue
        n = len(src)
        merged.insert_pdf(src)
        src.close()

        documents.append({
            "doc_class":   cls_name,
            "class_index": idx,
            "page_start":  cur_page,
            "page_end":    cur_page + n - 1,
            "n_pages":     n,
            "is_multipage_doc": is_mp,   # True = this doc spans multiple pages as ONE document
            "source_file": pdf_path.name,
        })
        cur_page += n

    if len(merged) < 2:
        merged.close()
        return None

    merged.save(str(PDF_OUT / fname))
    merged.close()

    ann = {
        "packet_id":       fname.replace(".pdf",""),
        "total_pages":     cur_page - 1,
        "n_documents":     len(documents),
        "class_sequence":  [d["doc_class"] for d in documents],
        "task":            "splitting",
        "note": (
            "page_start/page_end define which pages belong to each document. "
            "When is_multipage_doc=true, consecutive pages are a CONTINUATION "
            "of the SAME document instance — not separate documents."
        ),
        "documents":       documents,
    }
    (ANN_OUT / fname.replace(".pdf",".json")).write_text(
        json.dumps(ann, indent=2))
    return ann


def generate(count: int = 3000):
    PDF_OUT.mkdir(parents=True, exist_ok=True)
    ANN_OUT.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_OUT.glob("*.pdf")) + list(ANN_OUT.glob("*.json")):
        f.unlink()

    print(f"Generating {count} splitting packets (realistic multi-page combos)...")
    ok = fail = 0
    page_counts = []; doc_counts = []
    multipage_doc_count = 0

    for i in range(1, count + 1):
        ann = build_packet(i)
        if ann:
            ok += 1
            page_counts.append(ann["total_pages"])
            doc_counts.append(ann["n_documents"])
            multipage_doc_count += sum(1 for d in ann["documents"] if d["is_multipage_doc"])
            if i <= 5 or i % 500 == 0:
                summary = []
                for d in ann["documents"]:
                    pp = f"(pp{d['page_start']}-{d['page_end']})"
                    summary.append(f"{d['doc_class'][:10]}{pp}")
                print(f"  [{i:04d}] {ann['total_pages']}pp  "
                      f"{ann['n_documents']} docs  |  {' + '.join(summary)}")
        else:
            fail += 1

    print(f"\n{'='*65}")
    print(f"Packets:      {ok:,} generated, {fail} failed")
    if page_counts:
        print(f"Pages/packet: avg={sum(page_counts)/len(page_counts):.1f}  "
              f"min={min(page_counts)}  max={max(page_counts)}")
        print(f"Docs/packet:  avg={sum(doc_counts)/len(doc_counts):.1f}  "
              f"min={min(doc_counts)}  max={max(doc_counts)}")
        total_docs = sum(doc_counts)
        print(f"Multi-page docs in packets: {multipage_doc_count}/{total_docs} "
              f"({100*multipage_doc_count/total_docs:.0f}%)")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Generate splitting training packets with correct multi-page handling")
    p.add_argument("--count", type=int, default=3000)
    generate(p.parse_args().count)
