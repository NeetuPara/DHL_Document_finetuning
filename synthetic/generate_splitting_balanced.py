"""
Balanced splitting data — shipment-type approach.

Core insight: real shipments fall into 4 types, each with different document sets.
By controlling HOW MANY packets of each type, we control class coverage directly.

Type A — Ocean Freight     (750 packets):  HBL + CI + PL + [VGM,DGD,SLI,COO,EEI,POA,Manifest]
Type B — Air Freight       (750 packets):  HAWB + CI + PL + [DGD,SLI,COO,EEI,POA]
Type C — Express / Postal  (750 packets):  CN23 + CI + [HAWB,POA,EEI]
Type D — Mixed / Complex   (750 packets):  All 12 classes sampled with equal weight

Target coverage per class: ≥ 25% (≥750 / 3000 packets)
"""
import json, random, argparse
from pathlib import Path
import fitz
from collections import Counter, defaultdict

BASE       = Path(__file__).parent.parent
SYNTH_DIR  = BASE / "Synthetic_Data"
MP_DIR     = BASE / "Synthetic_Data_MultiPage"
OUTPUT_DIR = BASE / "Synthetic_Data_Splitting_v2"
PDF_OUT    = OUTPUT_DIR / "pdfs"
ANN_OUT    = OUTPUT_DIR / "annotations"

CLASSES = {
    1:  ("Commercial Invoice",              "01_Commercial_Invoice",             True,  "01_Commercial_Invoice"),
    2:  ("House Bill of Lading",            "02_House_Bill_of_Lading",           False, None),
    3:  ("Certificate of Origin",           "03_Certificate_of_Origin",          False, None),
    4:  ("Shipper's Letter of Instruction", "04_Shippers_Letter_of_Instruction", False, None),
    5:  ("Dangerous Goods Declaration",     "05_Dangerous_Goods_Declaration",    False, None),
    6:  ("Verified Gross Mass",             "06_Verified_Gross_Mass",            False, None),
    7:  ("House Airway Bill",               "07_House_Airway_Bill",              False, None),
    8:  ("Packing List",                    "08_Packing_List",                   True,  "08_Packing_List"),
    9:  ("Customs Declaration",             "09_Customs_Declarations",           False, None),
    10: ("Cargo Manifest",                  "10_Cargo_Manifest",                 True,  "10_Cargo_Manifest"),
    11: ("Import/Export License",           "11_Import_Export_License",          False, None),
    12: ("Power of Attorney",               "12_Power_of_Attorney",              False, None),
}

_sp = {}; _mp = {}

def sp(folder):
    if folder not in _sp:
        _sp[folder] = sorted((SYNTH_DIR / folder / "pdfs").rglob("*.pdf"))
    return _sp[folder]

def mp(mf):
    if mf not in _mp:
        _mp[mf] = sorted((MP_DIR / mf / "pdfs").rglob("*.pdf"))
    return _mp[mf]

def pick(cls_idx, force_mp=False):
    _, folder, can_mp, mp_folder = CLASSES[cls_idx]
    if force_mp and can_mp and mp_folder:
        pool = mp(mp_folder)
        if pool: return random.choice(pool), True
    pool = sp(folder)
    return (random.choice(pool), False) if pool else (None, False)


# ═══════════════════════════════════════════════════════════════════════════
# Shipment type template generators
# ═══════════════════════════════════════════════════════════════════════════

def type_a_ocean():
    """Ocean freight packet — HBL guaranteed. 4-8 docs."""
    # Always: CI + HBL + PL
    base = [1, 2, 8]
    # Optionals (pick 1-4 from ocean-relevant docs, WEIGHTED toward underrepresented)
    ocean_opts = [
        (3,  40),  # COO
        (4,  50),  # SLI
        (5,  40),  # DGD
        (6,  90),  # VGM — mandatory in most ocean packets
        (10, 85),  # Cargo Manifest — very common in ocean
        (11, 50),  # EEI
        (12, 45),  # POA
    ]
    n_extra = random.randint(2, 5)  # pick more extras so VGM/Manifest appear more
    weights = [w for _, w in ocean_opts]; classes = [c for c, _ in ocean_opts]
    extra = random.choices(classes, weights=weights, k=n_extra)
    all_cls = base + extra
    # Occasionally have 2× VGM (multiple containers) or 2× SLI
    if random.random() < 0.15 and 6 in extra: all_cls.append(6)
    # Occasionally CI is multipage
    result = [(c, c in [1] and random.random()<0.3) for c in all_cls]
    return result

def type_b_air():
    """Air freight packet — HAWB guaranteed. 3-7 docs."""
    base = [1, 7, 8]
    air_opts = [
        (3,  45),  # COO
        (4,  55),  # SLI
        (5,  50),  # DGD — common in air
        (11, 55),  # EEI
        (12, 45),  # POA
    ]
    n_extra = random.randint(1, 3)
    weights = [w for _, w in air_opts]; classes = [c for c, _ in air_opts]
    extra = random.choices(classes, weights=weights, k=n_extra)
    all_cls = base + extra
    if random.random() < 0.1 and 5 in extra: all_cls.append(5)  # 2× DGD
    result = [(c, c in [1, 8] and random.random()<0.35) for c in all_cls]
    return result

def type_c_express():
    """Express / postal packet — CN23 guaranteed. 2-5 docs."""
    # Always: CI + CN23
    base = [1, 9]
    # CN23 appears multiple times (multiple parcels in one submission)
    n_cn23 = random.choices([1, 2, 3, 4], weights=[30, 35, 25, 10])[0]
    cn23_list = [9] * n_cn23
    express_opts = [
        (7,  60),  # HAWB — common with express
        (12, 40),  # POA
        (11, 35),  # EEI
    ]
    n_extra = random.randint(0, 2)
    if n_extra > 0:
        weights = [w for _, w in express_opts]; classes = [c for c, _ in express_opts]
        extra = random.choices(classes, weights=weights, k=n_extra)
    else:
        extra = []
    all_cls = [1] + cn23_list + extra
    return [(c, False) for c in all_cls]

def type_d_mixed():
    """Mixed / complex — all 12 classes with equal weight. 3-7 docs."""
    # Weighted: give extra weight to VGM and Cargo Manifest to compensate
    # for them being ocean-only in other types
    weights_d = {1:6, 2:5, 3:5, 4:6, 5:6, 6:8, 7:5, 8:6, 9:4, 10:8, 11:6, 12:6}
    n_docs = random.randint(3, 7)
    chosen = random.choices(list(weights_d.keys()),
                            weights=list(weights_d.values()), k=n_docs)
    # Deduplicate but allow a few repeats (max 2 of same class, only for specific ones)
    seen = Counter(chosen)
    final = []
    for cls, count in seen.items():
        max_allowed = 3 if cls in [6, 9] else 2 if cls in [1, 5] else 1
        final.extend([cls] * min(count, max_allowed))
    if len(final) < 2:
        final.extend(random.choices(list(CLASSES.keys()), k=2))
    return [(c, c in [1, 8, 10] and random.random()<0.25) for c in final]


SHIPMENT_TYPES = [type_a_ocean, type_b_air, type_c_express, type_d_mixed]
TYPE_NAMES     = ["Ocean-Freight", "Air-Freight", "Express-Postal", "Mixed-Complex"]


def build_packet(packet_id, template_fn):
    template = template_fn()
    blocks   = []
    for cls_idx, force_mp in template:
        path, is_mp = pick(cls_idx, force_mp)
        if path is None: continue
        blocks.append((cls_idx, path, is_mp))

    if len(blocks) < 2: return None
    random.shuffle(blocks)

    merged = fitz.open(); docs = []; cur = 1
    for cls_idx, path, is_mp in blocks:
        try:   src = fitz.open(str(path))
        except: continue
        n = len(src)
        merged.insert_pdf(src); src.close()
        docs.append({"doc_class": CLASSES[cls_idx][0], "class_index": cls_idx,
                     "page_start": cur, "page_end": cur+n-1, "n_pages": n,
                     "is_multipage_doc": is_mp, "source_file": path.name})
        cur += n

    if len(merged) < 2: merged.close(); return None

    fname = f"packet_{packet_id:04d}.pdf"
    merged.save(str(PDF_OUT / fname)); merged.close()
    ann = {"packet_id": fname.replace(".pdf",""), "total_pages": cur-1,
           "n_documents": len(docs),
           "shipment_type": TYPE_NAMES[SHIPMENT_TYPES.index(template_fn)],
           "class_sequence": [d["doc_class"] for d in docs],
           "task": "splitting",
           "note": "is_multipage_doc=true = pages are CONTINUATION of same document, not a new document.",
           "documents": docs}
    (ANN_OUT / fname.replace(".pdf",".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=3000):
    PDF_OUT.mkdir(parents=True, exist_ok=True)
    ANN_OUT.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_OUT.glob("*.pdf")) + list(ANN_OUT.glob("*.json")): f.unlink()

    # 25% each shipment type = guaranteed balanced coverage
    per_type  = count // 4
    remainder = count % 4
    schedule  = []
    for i, fn in enumerate(SHIPMENT_TYPES):
        n = per_type + (1 if i < remainder else 0)
        schedule.extend([fn] * n)
    random.shuffle(schedule)

    print(f"Generating {count} BALANCED packets (4 shipment types × {per_type} each)...")
    ok = fail = 0
    page_counts = []; doc_counts = []; mp_docs = 0; total_docs = 0
    type_counts = Counter()

    for i, fn in enumerate(schedule, 1):
        ann = build_packet(i, fn)
        if ann:
            ok += 1
            page_counts.append(ann["total_pages"])
            doc_counts.append(ann["n_documents"])
            mp_docs   += sum(1 for d in ann["documents"] if d["is_multipage_doc"])
            total_docs += ann["n_documents"]
            type_counts[ann["shipment_type"]] += 1
            if i <= 5 or i % 500 == 0:
                seq = " + ".join(f"{d['doc_class'][:10]}(pp{d['page_start']}-{d['page_end']})"
                                 for d in ann["documents"])
                print(f"  [{i:04d}/{count}] {ann['total_pages']}pp  "
                      f"{ann['n_documents']} docs  [{ann['shipment_type'][:6]}]  |  {seq}")
        else:
            fail += 1

    # Coverage report
    class_count = Counter(); packet_has = defaultdict(int)
    for f in sorted(ANN_OUT.glob("*.json")):
        d = json.loads(f.read_text()); seen = set()
        for doc in d["documents"]:
            class_count[doc["doc_class"]] += 1; seen.add(doc["doc_class"])
        for cls in seen: packet_has[cls] += 1

    print(f"\n{'='*75}")
    print(f"Results: {ok:,} generated, {fail} failed")
    print(f"Avg pages/packet: {sum(page_counts)/len(page_counts):.1f}  "
          f"min={min(page_counts)}  max={max(page_counts)}")
    print(f"Avg docs/packet:  {sum(doc_counts)/len(doc_counts):.1f}")
    print(f"Multi-page doc rate: {100*mp_docs/total_docs:.0f}%")
    print(f"\nShipment type distribution: {dict(type_counts)}\n")

    print(f"  {'Class':<42} {'Instances':>10} {'Packets':>10} {'Coverage':>10}  Status")
    print(f"  {'-'*78}")
    all_ok = True
    for idx in range(1, 13):
        cls = CLASSES[idx][0]
        n = class_count.get(cls, 0); p = packet_has.get(cls, 0)
        pct = 100*p/ok if ok else 0
        status = "OK " if pct >= 20 else ("LOW" if pct >= 12 else "!!!")
        if pct < 20: all_ok = False
        print(f"  [{status}] {cls:<38} {n:>10,} {p:>10,} {pct:>9.1f}%")
    print(f"  {'-'*78}")
    print(f"  {'All 12 classes >= 20% coverage' if all_ok else 'WARNING: some classes below 20%'}")
    print(f"\n  Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=3000)
    generate(p.parse_args().count)
