"""
DHL Document Fine-tuning Dataset Preparation
Uses PyMuPDF (fitz) — no poppler required.

Steps:
  1. Convert all PDFs -> PNG images at 150 DPI
  2. Assign START / CONTINUATION labels per page
  3. Write train.jsonl / val.jsonl / test.jsonl

Label format: "<Document Class> | <START or CONTINUATION>"

Output:
  Training_Data/
    images/
      single/   <class>/<stem>_p<n>.png      (12,000 PDFs × 1 page)
      multi/    <class>/<stem>_p<n>.png      (3,000 PDFs × 2 pages)
      packets/  <packet_id>_p<n>.png         (5,000 PDFs × avg 5.3 pages)
    train.jsonl
    val.jsonl
    test.jsonl
    dataset_stats.json
"""

import json, random, time, argparse
from pathlib import Path
from collections import defaultdict, Counter
import fitz   # PyMuPDF

BASE     = Path(__file__).parent
OUT_DIR  = BASE / "Training_Data"
IMG_DIR  = OUT_DIR / "images"
DPI      = 150
MAT      = fitz.Matrix(DPI/72, DPI/72)   # scale matrix for DPI

CLASSES = {
    1:"Commercial Invoice", 2:"House Bill of Lading",
    3:"Certificate of Origin", 4:"Shipper's Letter of Instruction",
    5:"Dangerous Goods Declaration", 6:"Verified Gross Mass",
    7:"House Airway Bill", 8:"Packing List", 9:"Customs Declaration",
    10:"Cargo Manifest", 11:"Import/Export License", 12:"Power of Attorney",
}
CLASS_FOLDERS = {
    1:"01_Commercial_Invoice", 2:"02_House_Bill_of_Lading",
    3:"03_Certificate_of_Origin", 4:"04_Shippers_Letter_of_Instruction",
    5:"05_Dangerous_Goods_Declaration", 6:"06_Verified_Gross_Mass",
    7:"07_House_Airway_Bill", 8:"08_Packing_List",
    9:"09_Customs_Declarations", 10:"10_Cargo_Manifest",
    11:"11_Import_Export_License", 12:"12_Power_of_Attorney",
}

INSTRUCTION_TMPL = (
    "Analyze this DHL logistics document page.\n\n"
    "Previous page: {prev}\n\n"
    "Output format: <document_class> | <START or CONTINUATION>\n\n"
    "Document classes: Commercial Invoice, House Bill of Lading, "
    "Certificate of Origin, Shipper's Letter of Instruction, "
    "Dangerous Goods Declaration, Verified Gross Mass, House Airway Bill, "
    "Packing List, Customs Declaration, Cargo Manifest, "
    "Import/Export License, Power of Attorney\n\n"
    "START = first page of a new document\n"
    "CONTINUATION = this page continues the same document as the previous page"
)

FIRST_PAGE_PREV = "none (first page of batch)"

# Cap on single-page standalone docs per class — they're all START and inflate imbalance
MAX_SINGLE_DOC_PER_CLASS = 250   # 250 × 12 classes = 3,000 total

def pdf_to_pngs(pdf_path: Path, out_folder: Path, stem: str, skip_existing=True) -> list[Path]:
    paths = []
    try:
        doc = fitz.open(str(pdf_path))
        for i, page in enumerate(doc, 1):
            img_path = out_folder / f"{stem}_p{i}.png"
            if skip_existing and img_path.exists():
                paths.append(img_path)
                continue
            pix = page.get_pixmap(matrix=MAT)
            pix.save(str(img_path))
            paths.append(img_path)
        doc.close()
    except Exception as e:
        print(f"  ERROR: {pdf_path.name} — {e}")
    return paths

def make_example(img_rel: str, label: str, source: str,
                 prev_label: str = FIRST_PAGE_PREV) -> dict:
    return {
        "messages": [
            {"role": "user", "content": [
                {"type": "image"},
                {"type": "text", "text": INSTRUCTION_TMPL.format(prev=prev_label)}
            ]},
            {"role": "assistant", "content": label}
        ],
        "image": img_rel,
        "label": label,
        "prev_label": prev_label,
        "source": source,
    }

# ─────────────────────────────────────────────────────────────────────────
def step1_single_docs(examples: list, skip_existing=True):
    """Single-page PDFs — all START. Capped at MAX_SINGLE_DOC_PER_CLASS per class
    to prevent all-START examples from dominating the dataset."""
    print(f"\n[STEP 1/3] Single-doc PDFs (Synthetic_Data/) — cap {MAX_SINGLE_DOC_PER_CLASS}/class ...")
    synth = BASE / "Synthetic_Data"
    total = 0
    for idx, folder_name in CLASS_FOLDERS.items():
        cls   = CLASSES[idx]
        pdf_d = synth / folder_name / "pdfs"
        if not pdf_d.exists(): continue
        img_d = IMG_DIR / "single" / folder_name
        img_d.mkdir(parents=True, exist_ok=True)
        pdfs  = sorted(pdf_d.rglob("*.pdf"))
        # Convert all PDFs to PNG (reuse images if regenerating dataset later)
        # but only add a capped sample to examples
        all_imgs = []
        for pdf in pdfs:
            all_imgs.extend(pdf_to_pngs(pdf, img_d, pdf.stem, skip_existing))
        random.shuffle(all_imgs)
        sampled = all_imgs[:MAX_SINGLE_DOC_PER_CLASS]
        for img in sampled:
            rel = img.relative_to(OUT_DIR).as_posix()
            examples.append(make_example(rel, f"{cls} | START", "single_doc",
                                         prev_label=FIRST_PAGE_PREV))
        total += len(sampled)
        print(f"  {folder_name:<45} {len(pdfs):>5} PDFs -> {len(sampled)} sampled (of {len(all_imgs)})")
    print(f"  Subtotal: {total:,} examples")
    return total

# ─────────────────────────────────────────────────────────────────────────
def step2_multipage_docs(examples: list, skip_existing=True):
    """3,000 two-page PDFs — page 1=START, page 2+=CONTINUATION."""
    print("\n[STEP 2/3] Multi-page docs (Synthetic_Data_MultiPage/) ...")
    mp = BASE / "Synthetic_Data_MultiPage"
    total_s = total_c = 0
    for folder in sorted(mp.iterdir()):
        if not folder.is_dir(): continue
        pdf_d = folder / "pdfs"
        if not pdf_d.exists(): continue
        # Find which class this folder belongs to
        cls = None
        for idx, fn in CLASS_FOLDERS.items():
            if folder.name == fn:
                cls = CLASSES[idx]; break
        if cls is None: continue
        img_d = IMG_DIR / "multi" / folder.name
        img_d.mkdir(parents=True, exist_ok=True)
        pdfs  = sorted(pdf_d.rglob("*.pdf"))
        s = c = 0
        for pdf in pdfs:
            imgs = pdf_to_pngs(pdf, img_d, pdf.stem, skip_existing)
            prev = FIRST_PAGE_PREV
            for pg_num, img in enumerate(imgs, 1):
                pos   = "START" if pg_num == 1 else "CONTINUATION"
                label = f"{cls} | {pos}"
                rel   = img.relative_to(OUT_DIR).as_posix()
                examples.append(make_example(rel, label, "multi_doc", prev_label=prev))
                prev = label   # next page's context = this page's label
                if pos == "START": s += 1
                else:              c += 1
        total_s += s; total_c += c
        if s+c > 0:
            print(f"  {folder.name:<45} {len(pdfs):>4} docs -> {s} START + {c} CONTINUATION")
    print(f"  Subtotal: {total_s:,} START + {total_c:,} CONTINUATION = {total_s+total_c:,}")
    return total_s + total_c

# ─────────────────────────────────────────────────────────────────────────
def step3_splitting_packets(examples: list, skip_existing=True):
    """5,000 multi-doc packets — labels from annotation JSON."""
    print("\n[STEP 3/3] Splitting packets (Synthetic_Data_Splitting_v2/) ...")
    sp    = BASE / "Synthetic_Data_Splitting_v2"
    pdf_d = sp / "pdfs"
    ann_d = sp / "annotations"
    img_d = IMG_DIR / "packets"
    img_d.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(pdf_d.glob("*.pdf")) if pdf_d.exists() else []
    total_s = total_c = 0

    for i, pdf in enumerate(pdfs):
        ann_f = ann_d / (pdf.stem + ".json")
        if not ann_f.exists(): continue
        ann   = json.loads(ann_f.read_text())
        docs  = ann.get("documents", [])

        # Build page -> label mapping
        page_label = {}
        for doc in docs:
            cls = doc["doc_class"]
            for pg in range(doc["page_start"], doc["page_end"]+1):
                pos = "START" if pg == doc["page_start"] else "CONTINUATION"
                page_label[pg] = f"{cls} | {pos}"

        # Build page -> prev_label mapping (each page knows what came before it
        # in the same packet — this is the real-world sequential context)
        page_prev = {}
        prev = FIRST_PAGE_PREV
        for pg_num in sorted(page_label.keys()):
            page_prev[pg_num] = prev
            prev = page_label[pg_num]

        imgs = pdf_to_pngs(pdf, img_d, pdf.stem, skip_existing)
        for pg_num, img in enumerate(imgs, 1):
            label = page_label.get(pg_num, "Unknown | START")
            prev  = page_prev.get(pg_num, FIRST_PAGE_PREV)
            rel   = img.relative_to(OUT_DIR).as_posix()
            examples.append(make_example(rel, label, "splitting_packet", prev_label=prev))
            if "CONTINUATION" in label: total_c += 1
            else:                        total_s += 1

        if (i+1) % 500 == 0 or i < 3:
            print(f"  [{i+1:>5}/{len(pdfs)}] {pdf.stem}  {ann['total_pages']}pp  {len(docs)} docs")

    print(f"  Subtotal: {total_s:,} START + {total_c:,} CONTINUATION from {len(pdfs)} packets")
    return total_s + total_c

# ─────────────────────────────────────────────────────────────────────────
def doc_key(img_rel: str) -> str:
    """
    Group pages from the same source PDF together to prevent data leakage.
    Uses individual PDF stem as key — NOT class folder — so different PDFs
    from the same class can go to different splits (fixes val/test coverage).
    """
    parts = img_rel.split("/")
    if len(parts) >= 3 and parts[1] == "packets":
        # "images/packets/packet_0001_p3.png" → "images/packets/packet_0001"
        return "images/packets/" + parts[2].rsplit("_p", 1)[0]
    else:
        # "images/multi/01_CI/ci_mp_0001_p2.png" → "images/multi/01_CI/ci_mp_0001"
        # "images/single/01_CI/ci_0001_p1.png"   → "images/single/01_CI/ci_0001"
        stem = parts[-1].rsplit("_p", 1)[0]
        return "/".join(parts[:-1]) + "/" + stem

def split_dataset(examples: list, seed=42):
    """
    80/10/10 split by SOURCE DOCUMENT (not by page, not by class folder).
    Pages from the same PDF always stay in the same split.
    Different PDFs from the same class are distributed across all splits.
    """
    random.seed(seed)
    by_doc = defaultdict(list)
    for ex in examples:
        by_doc[doc_key(ex["image"])].append(ex)
    docs = list(by_doc.keys())
    random.shuffle(docs)
    n      = len(docs)
    n_tr   = int(n * 0.80)
    n_va   = int(n * 0.10)
    tr_set = set(docs[:n_tr])
    va_set = set(docs[n_tr:n_tr+n_va])
    train, val, test = [], [], []
    for ex in examples:
        key = doc_key(ex["image"])
        if   key in tr_set: train.append(ex)
        elif key in va_set: val.append(ex)
        else:               test.append(ex)
    return train, val, test

def write_jsonl(examples, path):
    with open(path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

def print_split_stats(examples, name):
    pos    = Counter(ex["label"].split(" | ")[1] if " | " in ex["label"] else "?" for ex in examples)
    by_cls = Counter(ex["label"].split(" | ")[0] for ex in examples)
    print(f"\n  {name}: {len(examples):,} examples")
    print(f"    START={pos.get('START',0):,}  CONTINUATION={pos.get('CONTINUATION',0):,}")
    for cls, n in sorted(by_cls.items(), key=lambda x:-x[1]):
        print(f"    {cls:<42} {n:>7,}")

# ─────────────────────────────────────────────────────────────────────────
def main(dpi=150, skip_existing=True):
    global DPI, MAT
    DPI = dpi; MAT = fitz.Matrix(DPI/72, DPI/72)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    print("="*65)
    print("DHL Document Dataset Preparation")
    print(f"DPI={DPI}  skip_existing={skip_existing}")
    print("="*65)

    t0       = time.time()
    examples = []

    step1_single_docs(examples,      skip_existing)
    step2_multipage_docs(examples,   skip_existing)
    step3_splitting_packets(examples, skip_existing)

    elapsed = time.time() - t0
    print(f"\n{'='*65}")
    print(f"Total examples: {len(examples):,}  ({elapsed/60:.1f} min)")

    # Distribution
    pos    = Counter(ex["label"].split(" | ")[1] if " | " in ex["label"] else "?" for ex in examples)
    by_cls = Counter(ex["label"].split(" | ")[0] for ex in examples)
    by_src = Counter(ex["source"] for ex in examples)
    print(f"\nPosition:  START={pos.get('START',0):,}  CONTINUATION={pos.get('CONTINUATION',0):,}")
    print(f"Source:    {dict(by_src)}")
    print(f"\nClass distribution:")
    for cls, n in sorted(by_cls.items(), key=lambda x:-x[1]):
        print(f"  {cls:<42} {n:>7,}")

    # Split
    train, val, test = split_dataset(examples)

    # Shuffle each split — prevents same-class clustering (e.g. 1000 CI in a row)
    # Without this, gradient updates get biased toward whichever class fills the
    # current batch, causing unstable training and artificially high loss spikes.
    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)

    print_split_stats(train, "TRAIN (80%)")
    print_split_stats(val,   "VAL   (10%)")
    print_split_stats(test,  "TEST  (10%)")

    # Write
    write_jsonl(train, OUT_DIR/"train.jsonl")
    write_jsonl(val,   OUT_DIR/"val.jsonl")
    write_jsonl(test,  OUT_DIR/"test.jsonl")

    stats = {
        "total": len(examples), "train": len(train), "val": len(val), "test": len(test),
        "start_count": pos.get("START",0), "continuation_count": pos.get("CONTINUATION",0),
        "class_counts": dict(by_cls), "source_counts": dict(by_src),
        "dpi": DPI, "elapsed_minutes": round(elapsed/60, 1),
    }
    (OUT_DIR/"dataset_stats.json").write_text(json.dumps(stats, indent=2))

    print(f"\nSaved to {OUT_DIR}/")
    print(f"  train.jsonl : {len(train):,} examples")
    print(f"  val.jsonl   : {len(val):,} examples")
    print(f"  test.jsonl  : {len(test):,} examples")
    print(f"  images/     : see {IMG_DIR}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dpi",           type=int,  default=150)
    p.add_argument("--no-skip",       action="store_true", help="Re-convert even if image exists")
    args = p.parse_args()
    main(dpi=args.dpi, skip_existing=not args.no_skip)
