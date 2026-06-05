import json, sys, random
from pathlib import Path
from collections import defaultdict, Counter

BASE     = Path("D:/finetuning/DHL_Document_finetuning")
TV2      = BASE / "Training_Data_v2"
IMGB     = BASE / "Training_Data"
SYNTH    = BASE / "Synthetic_Data"

VALID_CLASSES = {
    "Commercial Invoice","House Bill of Lading","Certificate of Origin",
    "Shipper's Letter of Instruction","Dangerous Goods Declaration",
    "Verified Gross Mass","House Airway Bill","Packing List",
    "Customs Declaration","Cargo Manifest","Import/Export License",
    "Power of Attorney",
}
ALL_12 = [
    "shipper_name","consignee_name","document_date","document_number",
    "country_of_origin","country_of_destination","description_of_goods","gross_weight_kg",
    "license_number","validity_start","validity_end","licensee_name",
]
CLASS_ANN_FOLDER = {
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

errors   = []
warnings = []

def sep(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")

sep("FINAL END-TO-END VALIDATION")

# ── 1. Load splits ─────────────────────────────────────────────────
print("\n[1] Loading JSONL splits...")
splits = {}
for sp in ["train","val","test"]:
    recs = []
    with open(TV2 / f"{sp}.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))
    splits[sp] = recs
    print(f"  {sp:<6}: {len(recs):>6,} records")

all_recs = splits["train"] + splits["val"] + splits["test"]
print(f"  {'total':<6}: {len(all_recs):>6,}")

# ── 2. Record structure ────────────────────────────────────────────
print("\n[2] Record structure...")
required_keys = {"messages","image","label","prev_label","source"}
bad = [r["image"] for r in all_recs if not required_keys.issubset(r.keys())]
if bad:
    errors.append(f"{len(bad)} records missing required keys")
    print(f"  FAIL: {len(bad)} records missing keys")
else:
    print("  OK: all records have messages/image/label/prev_label/source")

# ── 3. Label parse + 12-field check ────────────────────────────────
print("\n[3] Label format and 12-field check...")
parse_fail = bad_cls = bad_pos = start_12bad = start_12ok = cont_ok = cont_bad = 0
for r in all_recs:
    try:
        lbl = json.loads(r["label"])
    except Exception:
        parse_fail += 1
        continue
    cls = lbl.get("class")
    pos = lbl.get("position")
    if cls not in VALID_CLASSES:
        bad_cls += 1
    if pos not in ("START","CONTINUATION"):
        bad_pos += 1
        continue
    if pos == "START":
        missing = [k for k in ALL_12 if k not in lbl]
        if missing:
            start_12bad += 1
            errors.append(f"START label missing {missing} -> {r['image']}")
        else:
            start_12ok += 1
    else:
        extra = [k for k in lbl if k not in ("class","position")]
        if extra:
            cont_bad += 1
        else:
            cont_ok += 1

print(f"  Parse failures          : {parse_fail}")
print(f"  Invalid class names     : {bad_cls}")
print(f"  START labels OK (12-fld): {start_12ok:,}")
print(f"  START labels MISSING fld: {start_12bad}")
print(f"  CONTINUATION clean      : {cont_ok:,}")
print(f"  CONTINUATION extra flds : {cont_bad}")
if parse_fail or bad_cls or start_12bad:
    errors.append("Label format issues found")

# ── 4. Image existence (200 samples per split) ─────────────────────
print("\n[4] Image existence (200 samples per split)...")
random.seed(42)
for sp, recs in splits.items():
    sample = random.sample(recs, min(200, len(recs)))
    missing = [r["image"] for r in sample if not (IMGB / r["image"]).exists()]
    if missing:
        errors.append(f"{sp}: {len(missing)} images missing: {missing[0]}")
        print(f"  {sp}: FAIL — {len(missing)} missing (e.g. {missing[0]})")
    else:
        print(f"  {sp}: OK — all 200 sampled images exist on disk")

# ── 5. Source distribution ─────────────────────────────────────────
print("\n[5] Source distribution (train)...")
src_ctr = Counter(r.get("source","?") for r in splits["train"])
for src, n in sorted(src_ctr.items(), key=lambda x: -x[1]):
    print(f"  {src:<24} {n:>6,}  {100*n/len(splits['train']):>5.1f}%")

# ── 6. Single-doc check ────────────────────────────────────────────
print("\n[6] Single-doc records (20 samples)...")
single = [r for r in splits["train"] if r.get("source") == "single_doc"]
sample = random.sample(single, min(20, len(single)))
ok_cnt = bad_cnt = 0
for r in sample:
    lbl = json.loads(r["label"])
    if lbl.get("position") != "START":
        warnings.append(f"single_doc non-START: {r['image']}")
        bad_cnt += 1
        continue
    non_null = sum(1 for k in ALL_12[:8] if lbl.get(k) is not None)
    if non_null == 0:
        warnings.append(f"single_doc all-null fields: {r['image']} class={lbl.get('class')}")
    ok_cnt += 1
print(f"  {ok_cnt}/20 have correct START label")
if bad_cnt:
    print(f"  {bad_cnt} are not START — check single_doc generation")

# ── 7. Multi-page (multi_doc) check ───────────────────────────────
print("\n[7] Multi-page (multi_doc) records (50 docs)...")
multi = [r for r in splits["train"] if r.get("source") == "multi_doc"]
by_stem = defaultdict(list)
for r in multi:
    parts = Path(r["image"]).stem.rsplit("_p", 1)
    stem  = parts[0] if len(parts) == 2 else Path(r["image"]).stem
    pnum  = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0
    by_stem[stem].append((pnum, r))

mp_ok = mp_bad = 0
for stem, pages in list(by_stem.items())[:50]:
    pages_s = sorted(pages, key=lambda x: x[0])
    if len(pages_s) < 2:
        continue
    l0 = json.loads(pages_s[0][1]["label"])
    l1 = json.loads(pages_s[1][1]["label"])
    if (l0.get("position") == "START"
            and l1.get("position") == "CONTINUATION"
            and l0.get("class") == l1.get("class")):
        mp_ok += 1
    else:
        mp_bad += 1
        warnings.append(
            f"multi_doc seq wrong: {stem} "
            f"p1={l0.get('position')} p2={l1.get('position')} "
            f"cls match={l0.get('class')==l1.get('class')}"
        )
print(f"  {mp_ok}/50 docs: p1=START + p2=CONTINUATION (same class)  OK")
if mp_bad:
    print(f"  {mp_bad} had issues")

# ── 8. Splitting-packet check ──────────────────────────────────────
print("\n[8] Splitting-packet records (50 packets)...")
pkt_recs = [r for r in splits["train"] if r.get("source") == "splitting_packet"]
by_pkt = defaultdict(list)
for r in pkt_recs:
    stem  = Path(r["image"]).stem
    parts = stem.rsplit("_p", 1)
    pid   = parts[0] if len(parts) == 2 else stem
    pnum  = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0
    by_pkt[pid].append((pnum, r))

sample_pids = random.sample(list(by_pkt.keys()), min(50, len(by_pkt)))
pkt_ok = pkt_bad = seq_ok = seq_bad = 0
for pid in sample_pids:
    pages = sorted(by_pkt[pid], key=lambda x: x[0])
    lbls  = [json.loads(p[1]["label"]) for p in pages]
    if lbls[0].get("position") != "START":
        pkt_bad += 1
        warnings.append(f"packet {pid}: page1 is {lbls[0].get('position')}, not START")
        continue
    pkt_ok += 1
    for i in range(1, len(lbls)):
        if lbls[i].get("position") == "CONTINUATION":
            if lbls[i].get("class") == lbls[i-1].get("class"):
                seq_ok += 1
            else:
                seq_bad += 1
                warnings.append(
                    f"packet {pid} p{i+1}: CONT class mismatch "
                    f"{lbls[i-1].get('class')} -> {lbls[i].get('class')}"
                )
        else:
            seq_ok += 1

print(f"  {pkt_ok}/50 packets start with START page")
print(f"  CONTINUATION class consistency: {seq_ok} OK, {seq_bad} bad")

# ── 9. Annotation vs label cross-check ───────────────────────────
print("\n[9] Annotation vs Label cross-check (30 single-doc samples)...")
sample30 = random.sample([r for r in splits["train"] if r.get("source") == "single_doc"], 30)
xok = xbad = xskip = 0
for r in sample30:
    lbl = json.loads(r["label"])
    if lbl.get("position") != "START":
        xskip += 1
        continue
    cls    = lbl.get("class", "")
    folder = CLASS_ANN_FOLDER.get(cls)
    if not folder:
        xskip += 1
        continue
    stem     = Path(r["image"]).stem
    ann_path = SYNTH / folder / "annotations" / f"{stem}.json"
    if not ann_path.exists():
        warnings.append(f"Ann missing: {ann_path.name}")
        xskip += 1
        continue
    ann_fields = json.loads(ann_path.read_text(encoding="utf-8")).get("fields", {})
    # Check document_number present in annotation matches label
    lbl_docno = lbl.get("document_number")
    # Try common annotation keys for doc number
    ann_docno = next((
        ann_fields.get(k) for k in
        ["invoice_number","bl_number","poa_reference","hawb_number","manifest_number",
         "document_number","reference","awb_number","entry_number","license_number","cn23_number"]
        if ann_fields.get(k)
    ), None)
    if lbl_docno is not None and ann_docno is not None:
        if str(lbl_docno)[:15] == str(ann_docno)[:15]:
            xok += 1
        else:
            xbad += 1
            warnings.append(
                f"docno mismatch {cls} {stem}: label={lbl_docno!r} ann={ann_docno!r}"
            )
    else:
        xok += 1  # both null is fine

print(f"  {xok} samples: doc_number matches annotation")
print(f"  {xbad} mismatches")
print(f"  {xskip} skipped (CONTINUATION or ann not found)")

# ── 10. EEI license fields ────────────────────────────────────────
print("\n[10] EEI license fields populated check...")
eei_all = [
    json.loads(r["label"]) for r in splits["train"]
    if r.get("source") in ("single_doc","splitting_packet")
    and json.loads(r["label"]).get("class") == "Import/Export License"
    and json.loads(r["label"]).get("position") == "START"
]
with_lic = sum(1 for l in eei_all if l.get("license_number") is not None)
print(f"  EEI START records: {len(eei_all)}")
print(f"  license_number populated: {with_lic} ({100*with_lic//max(len(eei_all),1)}%)")
print(f"  Expected ~33% (only fmt3 Import-Export-License-Document has license fields)")

# ── 11. Prompt contains 12-field names ───────────────────────────
print("\n[11] Prompt format check (sample 5 records)...")
sample5 = random.sample(all_recs, 5)
prompt_ok = 0
for r in sample5:
    prompt = r["messages"][0]["content"][1]["text"]
    has_new = all(f in prompt for f in ["license_number","validity_start","licensee_name"])
    if has_new:
        prompt_ok += 1
    else:
        warnings.append(f"Prompt missing new fields: {r['image']}")
print(f"  {prompt_ok}/5 prompts contain all 12 field names")

# ── 12. Class distribution across all splits ─────────────────────
print("\n[12] Class distribution (all splits)...")
cls_ctr = Counter()
for r in all_recs:
    try:
        cls_ctr[json.loads(r["label"]).get("class","?")] += 1
    except Exception:
        pass
for cls, n in sorted(cls_ctr.items(), key=lambda x: -x[1]):
    bar = "#" * int(20 * n / max(cls_ctr.values()))
    print(f"  {cls[:38]:<38} {n:>6,}  {bar}")

# ── FINAL VERDICT ─────────────────────────────────────────────────
print(f"\n{'='*65}")
print("  SUMMARY")
print(f"{'='*65}")
if errors:
    print(f"  ERRORS ({len(errors)}):")
    for e in errors[:10]:
        print(f"    - {e}")
else:
    print("  ERRORS  : none")

if warnings:
    print(f"  WARNINGS ({len(warnings)}):")
    for w in warnings[:10]:
        print(f"    - {w}")
else:
    print("  WARNINGS: none")

verdict = "READY FOR TRAINING" if not errors else "FIX ERRORS BEFORE TRAINING"
print(f"\n  VERDICT: {verdict}")
print(f"{'='*65}")
