"""
Creates Training_Data_v3/test_new.jsonl — a focused 2500-sample test set.

Key design decisions:
  1. Keeps WHOLE PACKETS together — Split IoU is meaningless on partial packets
  2. Weights multi-page packets 3-4x — harder splitting cases, more signal
  3. Guarantees all 12 classes are represented with enough samples
  4. Keeps blank/empty forms proportionally — needed for hallucination metrics
  5. Covers corner cases: long bundles, mixed-class packets, rare classes

Run:
    python create_test_new.py

Output: Training_Data_v3/test_new.jsonl  (~2500 samples)
"""

import json, re, random
from pathlib import Path
from collections import defaultdict

BASE_DIR  = Path(__file__).parent
INPUT     = BASE_DIR / "Training_Data_v3" / "test.jsonl"
OUTPUT    = BASE_DIR / "Training_Data_v3" / "test_new.jsonl"
TARGET    = 2500
SEED      = 42

random.seed(SEED)

CLASSES = [
    "Commercial Invoice", "House Bill of Lading", "Certificate of Origin",
    "Shipper's Letter of Instruction", "Dangerous Goods Declaration",
    "Verified Gross Mass", "House Airway Bill", "Packing List",
    "Customs Declaration", "Cargo Manifest", "Import/Export License",
    "Power of Attorney",
]
START_FIELDS = [
    "shipper_name", "consignee_name", "document_date", "document_number",
    "country_of_origin", "country_of_destination", "description_of_goods",
    "license_number", "validity_start", "validity_end", "licensee_name",
]

def is_blank(label: dict) -> bool:
    if label.get("position") != "START":
        return False
    return all(label.get(f) is None or str(label.get(f) or "").strip() == ""
               for f in START_FIELDS)

# ── Load & group by packet ───────────────────────────────────────────────────

print(f"Reading {INPUT} ...")
with open(INPUT) as f:
    rows = [json.loads(l) for l in f]
print(f"  {len(rows):,} total records")

packets = defaultdict(list)
for r in rows:
    m = re.search(r"(packet_\d+)", r["image"])
    key = m.group(1) if m else re.sub(r"_p\d+\..*$", "", Path(r["image"]).stem)
    packets[key].append(r)

print(f"  {len(packets):,} distinct packets")

# ── Classify each packet ─────────────────────────────────────────────────────

def classify_packet(pages):
    n = len(pages)
    classes, has_blank = set(), False
    for p in pages:
        lbl = json.loads(p["label"])
        classes.add(lbl.get("class", "Unknown"))
        if is_blank(lbl):
            has_blank = True
    # complexity weight: prefer harder multi-page packets
    if n == 1:   weight = 1
    elif n == 2: weight = 2
    elif n <= 5: weight = 3
    else:        weight = 4
    return dict(n=n, classes=classes, has_blank=has_blank,
                weight=weight, pages=pages)

pkt_info = {k: classify_packet(v) for k, v in packets.items()}

blank_pkts  = {k: v for k, v in pkt_info.items() if v["has_blank"]}
filled_pkts = {k: v for k, v in pkt_info.items() if not v["has_blank"]}
print(f"  {len(filled_pkts):,} filled packets  |  {len(blank_pkts):,} blank packets")

# ── Build complexity buckets across filled packets ───────────────────────────

buckets = {"1-page": [], "2-page": [], "3-5 pages": [], "6+ pages": []}
for pkt_id, info in filled_pkts.items():
    n = info["n"]
    if   n == 1: buckets["1-page"].append(pkt_id)
    elif n == 2: buckets["2-page"].append(pkt_id)
    elif n <= 5: buckets["3-5 pages"].append(pkt_id)
    else:        buckets["6+ pages"].append(pkt_id)

for bkt, ids in buckets.items():
    pages = sum(filled_pkts[i]["n"] for i in ids)
    print(f"  {bkt:12s}: {len(ids):4d} packets  ({pages:5d} pages)")

# ── Per-class index ──────────────────────────────────────────────────────────

class_to_pkts = defaultdict(list)
for pkt_id, info in filled_pkts.items():
    for cls in info["classes"]:
        class_to_pkts[cls].append(pkt_id)

# ── Sample strategy ──────────────────────────────────────────────────────────
#
# Step 1 — guarantee minimum coverage per class (15 packets, prefer multi-page)
# Step 2 — fill remaining budget with complexity-weighted sampling
# Step 3 — add blank packets proportionally (target ~8% of total)

selected = set()

# Step 1: minimum per class
MIN_PKTS_PER_CLASS = 15
print(f"\nEnsuring {MIN_PKTS_PER_CLASS} packets per class ...")
for cls in CLASSES:
    candidates = sorted(class_to_pkts[cls],
                        key=lambda pid: -filled_pkts[pid]["weight"])
    added = 0
    for pid in candidates:
        if pid not in selected:
            selected.add(pid)
            added += 1
        if added >= MIN_PKTS_PER_CLASS:
            break
    if added < MIN_PKTS_PER_CLASS:
        print(f"  Warning: only {added} packets available for {cls}")

current_samples = sum(filled_pkts[p]["n"] for p in selected)
print(f"  After minimum pass: {len(selected)} packets / {current_samples} samples")

# Step 2: weighted sampling to fill budget (reserve ~8% for blanks)
BLANK_BUDGET = int(TARGET * 0.08)
FILLED_BUDGET = TARGET - BLANK_BUDGET
remaining_budget = FILLED_BUDGET - current_samples

if remaining_budget > 0:
    # Allocate remaining budget: 20% to single-page, 80% to multi-page
    # (step 1 already pulled mostly multi-page packets for class coverage)
    single_budget = int(remaining_budget * 0.20)
    multi_budget  = remaining_budget - single_budget

    def fill_from_pool(pool_ids, budget, info_dict):
        used = set()
        added_ids = []
        random.shuffle(pool_ids)
        for pid in pool_ids:
            if pid in selected or pid in used:
                continue
            if budget <= 0:
                break
            used.add(pid)
            added_ids.append(pid)
            budget -= info_dict[pid]["n"]
        return added_ids

    single_pool = [pid for pid in buckets["1-page"] if pid not in selected]
    multi_pool  = ([pid for pid in buckets["6+ pages"]  if pid not in selected] +
                   [pid for pid in buckets["3-5 pages"] if pid not in selected] +
                   [pid for pid in buckets["2-page"]    if pid not in selected])

    for pid in fill_from_pool(single_pool, single_budget, filled_pkts):
        selected.add(pid)
    for pid in fill_from_pool(multi_pool, multi_budget, filled_pkts):
        selected.add(pid)

current_samples = sum(filled_pkts[p]["n"] for p in selected)
print(f"  After weighted fill: {len(selected)} packets / {current_samples} samples")

# Step 3: blank packets (spread across classes)
blank_selected = []
blank_pool = list(blank_pkts.items())
random.shuffle(blank_pool)
blank_samples_added = 0
for pkt_id, info in blank_pool:
    if blank_samples_added >= BLANK_BUDGET:
        break
    blank_selected.append(pkt_id)
    blank_samples_added += info["n"]

print(f"  Blank packets: {len(blank_selected)} / {blank_samples_added} samples")

# ── Assemble final list ──────────────────────────────────────────────────────

all_samples = []
for pid in selected:
    # Sort pages within packet by page number
    pages = sorted(filled_pkts[pid]["pages"],
                   key=lambda r: int(re.search(r"_p(\d+)", r["image"]).group(1))
                   if re.search(r"_p(\d+)", r["image"]) else 0)
    all_samples.extend(pages)

for pid in blank_selected:
    pages = sorted(blank_pkts[pid]["pages"],
                   key=lambda r: int(re.search(r"_p(\d+)", r["image"]).group(1))
                   if re.search(r"_p(\d+)", r["image"]) else 0)
    all_samples.extend(pages)

# Shuffle at packet level (not page level — keep packets contiguous for IoU)
# Group back into packets, shuffle packets, then flatten
pkt_order = list(selected) + blank_selected
random.shuffle(pkt_order)
final_samples = []
all_pages_by_pkt = {}
for pid in selected:
    all_pages_by_pkt[pid] = sorted(
        filled_pkts[pid]["pages"],
        key=lambda r: int(re.search(r"_p(\d+)", r["image"]).group(1))
        if re.search(r"_p(\d+)", r["image"]) else 0)
for pid in blank_selected:
    all_pages_by_pkt[pid] = sorted(
        blank_pkts[pid]["pages"],
        key=lambda r: int(re.search(r"_p(\d+)", r["image"]).group(1))
        if re.search(r"_p(\d+)", r["image"]) else 0)

for pid in pkt_order:
    final_samples.extend(all_pages_by_pkt[pid])

# ── Stats ────────────────────────────────────────────────────────────────────

print(f"\n{'='*55}")
print(f"  Final test_new.jsonl: {len(final_samples):,} samples")
print(f"{'='*55}")

# Complexity breakdown
cplx = {"1-page": 0, "2-page": 0, "3-5 pages": 0, "6+ pages": 0, "blank": 0}
for pid in selected:
    n = filled_pkts[pid]["n"]
    if   n == 1: cplx["1-page"]    += n
    elif n == 2: cplx["2-page"]    += n
    elif n <= 5: cplx["3-5 pages"] += n
    else:        cplx["6+ pages"]  += n
for pid in blank_selected:
    cplx["blank"] += blank_pkts[pid]["n"]
for k, v in cplx.items():
    print(f"  {k:12s}: {v:4d} samples  ({v/len(final_samples)*100:.1f}%)")

# Class coverage
print()
cls_counts = defaultdict(int)
for r in final_samples:
    lbl = json.loads(r["label"])
    cls_counts[lbl.get("class", "?")] += 1
for cls in CLASSES:
    print(f"  {cls:<40s}: {cls_counts.get(cls, 0):4d}")

# ── Save ─────────────────────────────────────────────────────────────────────

with open(OUTPUT, "w", encoding="utf-8") as f:
    for r in final_samples:
        f.write(json.dumps(r) + "\n")

print(f"\nSaved → {OUTPUT}")
print(f"Eval command: python eval_all_models.py --test-jsonl Training_Data_v3/test_new.jsonl")
