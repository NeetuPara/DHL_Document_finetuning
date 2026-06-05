"""
Evaluation — Base model vs Fine-tuned model (v2: classification + splitting + extraction)

Three evaluation dimensions:
  1. Classification  — exact match on document class
  2. Splitting       — exact match on START / CONTINUATION
  3. Extraction      — field-level scoring (START pages only, GT non-null fields):
       • Text fields  (shipper_name, consignee_name, description_of_goods,
                       licensee_name): token F1
       • Structured   (document_date, document_number, country_of_origin,
                       country_of_destination, license_number,
                       validity_start, validity_end): normalized exact match
       • Numeric      (gross_weight_kg): within ±5% tolerance

Usage:
    python evaluate_baseline.py --test                            # base model, 200 samples
    python evaluate_baseline.py --test --finetuned                # base + fine-tuned side by side
    python evaluate_baseline.py --test --n 500 --show 5          # 500 samples, show 5
    python evaluate_baseline.py --test --source splitting_packet  # filter by source type
    python evaluate_baseline.py --test --save results.json        # dump summary to JSON
    python evaluate_baseline.py --pdf file.pdf                    # classify + split a real PDF
    python evaluate_baseline.py --pdf file.pdf --finetuned
"""

import argparse, json, random, sys, re
from pathlib import Path
from collections import Counter, defaultdict
from PIL import Image

BASE_DIR   = Path(__file__).parent
TEST_JSONL = BASE_DIR / "Training_Data_v2" / "test.jsonl"
IMG_BASE   = BASE_DIR / "Training_Data"          # images live here (packets/multi/single)
MODEL_PATH = BASE_DIR / "models" / "Qwen2.5-VL-3B-Instruct"
LORA_PATH  = BASE_DIR / "model_output_v2" / "final"
MAX_PIXELS = 1_000_000
FIRST_PREV = "none (first page of batch)"

CLASSES = [
    "Commercial Invoice", "House Bill of Lading", "Certificate of Origin",
    "Shipper's Letter of Instruction", "Dangerous Goods Declaration",
    "Verified Gross Mass", "House Airway Bill", "Packing List",
    "Customs Declaration", "Cargo Manifest", "Import/Export License",
    "Power of Attorney",
]
CLASS_SET = set(CLASSES)

# Extraction field → evaluation method
EXTRACTION_FIELDS = {
    "shipper_name":           "token_f1",
    "consignee_name":         "token_f1",
    "description_of_goods":   "token_f1",
    "licensee_name":          "token_f1",
    "document_date":          "exact",
    "document_number":        "exact",
    "country_of_origin":      "exact",
    "country_of_destination": "exact",
    "license_number":         "exact",
    "validity_start":         "exact",
    "validity_end":           "exact",
    "gross_weight_kg":        "numeric",
}


# ─────────────────────────────────────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

# Fine-tuned model: exact training format
PROMPT_FINETUNED = (
    "Analyze this DHL logistics document page.\n\n"
    "Previous page: {prev}\n\n"
    "Output a single JSON line.\n\n"
    "If this is the START (first page of a new document):\n"
    '  {{"class": "...", "position": "START", "shipper_name": "...", '
    '"consignee_name": "...", "document_date": "...", "document_number": "...", '
    '"country_of_origin": "...", "country_of_destination": "...", '
    '"description_of_goods": "...", "gross_weight_kg": ..., '
    '"license_number": "...", "validity_start": "...", '
    '"validity_end": "...", "licensee_name": "..."}}\n\n'
    "If this is a CONTINUATION (same document continues from previous page):\n"
    '  {{"class": "...", "position": "CONTINUATION"}}\n\n'
    "Document classes: " + ", ".join(CLASSES) + "\n\n"
    "Use null for fields not visible on this page."
)

# Base model: fair natural-language prompt — no angle-bracket placeholders,
# concrete example, same JSON structure so extraction is comparable.
PROMPT_BASE = (
    "You are a DHL logistics document analyst.\n\n"
    "Examine this document page and output a single JSON line.\n\n"
    "Previous page in this batch: {prev}\n\n"
    "STEP 1 — Classify: identify the document type (choose exactly one):\n"
    + "\n".join(f"  {c}" for c in CLASSES)
    + "\n\n"
    "STEP 2 — Position: is this the START (first page of a new document) "
    "or a CONTINUATION (same document as the previous page)?\n\n"
    "STEP 3 — If START, extract these fields (use null if not visible on this page):\n"
    "  shipper_name, consignee_name, document_date (YYYY-MM-DD format),\n"
    "  document_number, country_of_origin, country_of_destination,\n"
    "  description_of_goods (brief), gross_weight_kg (number only)\n\n"
    "Example output for a START page:\n"
    '{{"class": "Commercial Invoice", "position": "START", "shipper_name": "Acme Corp", '
    '"consignee_name": "Beta Ltd", "document_date": "2025-01-15", '
    '"document_number": "INV-001", "country_of_origin": "China", '
    '"country_of_destination": "USA", "description_of_goods": "Electronic parts", '
    '"gross_weight_kg": 125.5}}\n\n'
    "Example output for a CONTINUATION page:\n"
    '{{"class": "Commercial Invoice", "position": "CONTINUATION"}}'
)


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTION SCORING
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(s) -> str:
    if s is None:
        return ""
    s = re.sub(r"[^\w\s]", " ", str(s).lower())
    return re.sub(r"\s+", " ", s).strip()


def token_f1(pred, gt) -> float | None:
    """Word-level F1 (SQuAD-style). Returns None when GT is null (skip)."""
    if gt is None:
        return None
    gt_toks = _normalize(gt).split()
    if not gt_toks:
        return None
    if pred is None:
        return 0.0
    pred_toks = _normalize(str(pred)).split()
    if not pred_toks:
        return 0.0
    common = sum((Counter(pred_toks) & Counter(gt_toks)).values())
    if common == 0:
        return 0.0
    p = common / len(pred_toks)
    r = common / len(gt_toks)
    return 2 * p * r / (p + r)


def exact_match(pred, gt) -> float | None:
    """Normalized exact match (lowercase, punctuation-stripped). None when GT is null."""
    if gt is None:
        return None
    if pred is None:
        return 0.0
    return 1.0 if _normalize(str(pred)) == _normalize(str(gt)) else 0.0


def numeric_match(pred, gt, tol: float = 0.05) -> float | None:
    """1.0 if |pred - gt| / |gt| <= tol. None when GT is null."""
    if gt is None:
        return None
    try:
        p, g = float(pred), float(gt)
    except (TypeError, ValueError):
        return 0.0
    if g == 0:
        return 1.0 if p == 0 else 0.0
    return 1.0 if abs(p - g) / abs(g) <= tol else 0.0


def score_extraction(pred: dict, gt: dict) -> dict[str, float | None]:
    """
    Returns per-field scores for all extraction fields.
    A None score means GT was null → field is excluded from averages.
    """
    scores = {}
    for field, method in EXTRACTION_FIELDS.items():
        gt_val   = gt.get(field)
        pred_val = pred.get(field)
        if method == "token_f1":
            scores[field] = token_f1(pred_val, gt_val)
        elif method == "exact":
            scores[field] = exact_match(pred_val, gt_val)
        else:  # numeric
            scores[field] = numeric_match(pred_val, gt_val)
    return scores


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE PARSING
# ─────────────────────────────────────────────────────────────────────────────

def parse_json_response(raw: str) -> dict | None:
    """Try to extract the first JSON object from model output."""
    raw = raw.strip()
    # Direct parse
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    # Find first {...} block (handles leading/trailing prose)
    m = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group())
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None


def _find_class_pos(text: str):
    """Fallback keyword search for class name and START/CONTINUATION."""
    found_cls = None
    for c in sorted(CLASS_SET, key=len, reverse=True):  # longest first avoids partial match
        if c.lower() in text.lower():
            found_cls = c
            break
    found_pos = None
    if re.search(r"\bCONTINUATION\b", text, re.IGNORECASE):
        found_pos = "CONTINUATION"
    elif re.search(r"\bSTART\b", text, re.IGNORECASE):
        found_pos = "START"
    return found_cls, found_pos


def parse_response(raw: str, strict: bool = False) -> dict:
    """
    Parse model output into a structured dict with at least 'class' and 'position'.
    strict=True → prefer JSON only (fine-tuned model); None if JSON fails.
    strict=False → fallback to keyword search (base model).
    """
    obj = parse_json_response(raw)
    if obj is not None:
        # Validate class and position
        if obj.get("class") not in CLASS_SET:
            obj["class"] = None
        if obj.get("position") not in ("START", "CONTINUATION"):
            obj["position"] = None
        return obj

    if strict:
        return {"class": None, "position": None}

    # Flexible fallback for base model
    cls, pos = _find_class_pos(raw)
    return {"class": cls, "position": pos}


# ─────────────────────────────────────────────────────────────────────────────
# MODEL LOADING AND INFERENCE
# ─────────────────────────────────────────────────────────────────────────────

_models: dict = {}


def load_model(model_type: str):
    if model_type in _models:
        return _models[model_type]
    from unsloth import FastVisionModel

    if model_type == "finetuned":
        if not LORA_PATH.exists():
            print(f"ERROR: Fine-tuned adapter not found at {LORA_PATH}")
            return None, None
        print(f"Loading FINE-TUNED model from {LORA_PATH} ...")
        model, proc = FastVisionModel.from_pretrained(str(LORA_PATH), load_in_4bit=True)
    else:
        print(f"Loading BASE model from {MODEL_PATH} ...")
        model, proc = FastVisionModel.from_pretrained(str(MODEL_PATH), load_in_4bit=True)

    FastVisionModel.for_inference(model)
    model.eval()
    _models[model_type] = (model, proc)
    return model, proc


def _resize(image):
    w, h = image.size
    if w * h > MAX_PIXELS:
        s = (MAX_PIXELS / (w * h)) ** 0.5
        image = image.resize((int(w * s), int(h * s)), Image.LANCZOS)
    return image


def run_inference(model, processor, image, prompt_text: str, max_new_tokens: int = 300) -> str:
    import torch
    img  = _resize(image)
    msgs = [{"role": "user", "content": [
        {"type": "image"}, {"type": "text", "text": prompt_text},
    ]}]
    text   = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[img], return_tensors="pt", padding=True).to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    full   = processor.decode(out[0], skip_special_tokens=True)
    answer = full.split("assistant")[-1].strip() if "assistant" in full else full.strip()
    return answer.replace("<|im_end|>", "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# STATS ACCUMULATORS
# ─────────────────────────────────────────────────────────────────────────────

def _empty_stats() -> dict:
    return {
        "cls_ok": 0, "cls_total": 0,
        "pos_ok": 0, "pos_total": 0,
        "both_ok": 0,
        "parse_fail": 0,
        "cls_by_class":  defaultdict(lambda: {"ok": 0, "total": 0}),
        "pos_by_pos":    defaultdict(lambda: {"ok": 0, "total": 0}),
        "by_source":     defaultdict(lambda: {"cls_ok": 0, "pos_ok": 0, "both_ok": 0, "total": 0}),
        "ext_sum":       defaultdict(float),   # field → sum of scores
        "ext_count":     defaultdict(int),     # field → count of non-null GT
    }


def _update(stats: dict, gt: dict, pred: dict, source: str) -> None:
    true_cls = gt.get("class")
    true_pos = gt.get("position")
    pred_cls = pred.get("class")
    pred_pos = pred.get("position")

    if pred_cls is None and pred_pos is None:
        stats["parse_fail"] += 1

    cls_ok  = (pred_cls == true_cls)
    pos_ok  = (pred_pos == true_pos)
    both_ok = cls_ok and pos_ok

    # Classification
    if true_cls:
        stats["cls_total"] += 1
        stats["cls_ok"]    += cls_ok
        stats["cls_by_class"][true_cls]["total"] += 1
        stats["cls_by_class"][true_cls]["ok"]    += cls_ok

    # Splitting
    if true_pos:
        stats["pos_total"] += 1
        stats["pos_ok"]    += pos_ok
        stats["pos_by_pos"][true_pos]["total"] += 1
        stats["pos_by_pos"][true_pos]["ok"]    += pos_ok

    stats["both_ok"] += both_ok

    # Extraction — only for START GT pages (CONTINUATION pages have no extraction fields)
    if true_pos == "START":
        for field, score in score_extraction(pred, gt).items():
            if score is not None:          # skip null GT fields
                stats["ext_sum"][field]   += score
                stats["ext_count"][field] += 1

    # By source
    src = stats["by_source"][source]
    src["total"]   += 1
    src["cls_ok"]  += cls_ok
    src["pos_ok"]  += pos_ok
    src["both_ok"] += both_ok


# ─────────────────────────────────────────────────────────────────────────────
# PRETTY PRINTING
# ─────────────────────────────────────────────────────────────────────────────

def _pct(n: int, d: int) -> str:
    return "—" if d == 0 else f"{n}/{d} ({100*n/d:.1f}%)"


def _fpct(s: float, d: int) -> str:
    return "—" if d == 0 else f"{s/d:.3f}  ({100*s/d:.1f}%)"


def _print_stats(stats: dict, total: int, label: str) -> None:
    print(f"\n  {'─'*70}")
    print(f"  {label}")
    print(f"  {'─'*70}")
    print(f"  Samples evaluated   : {total}")
    print(f"  Parse failures      : {stats['parse_fail']}")
    print(f"  Classification acc  : {_pct(stats['cls_ok'], stats['cls_total'])}")
    print(f"  Splitting acc       : {_pct(stats['pos_ok'], stats['pos_total'])}")
    print(f"  Both correct        : {_pct(stats['both_ok'], total)}")
    print(f"    START accuracy    : {_pct(stats['pos_by_pos']['START']['ok'], stats['pos_by_pos']['START']['total'])}")
    print(f"    CONTINUATION acc  : {_pct(stats['pos_by_pos']['CONTINUATION']['ok'], stats['pos_by_pos']['CONTINUATION']['total'])}")

    # Extraction
    if stats["ext_count"]:
        print(f"\n  Extraction (START pages, GT non-null fields only):")
        METHOD_TAG = {"token_f1": "token-F1", "exact": "   exact", "numeric": "    ±5%"}
        total_s = 0.0; total_c = 0
        for field, method in EXTRACTION_FIELDS.items():
            cnt = stats["ext_count"][field]
            s   = stats["ext_sum"][field]
            tag = METHOD_TAG[method]
            print(f"    {field:<28} [{tag}] : {_fpct(s, cnt)}")
            total_s += s; total_c += cnt
        print(f"    {'Overall avg':<28}           : {_fpct(total_s, total_c)}")

    # Per-class classification
    print(f"\n  Per-class classification accuracy:")
    for cls in sorted(CLASS_SET, key=lambda x: -stats["cls_by_class"][x]["total"]):
        d = stats["cls_by_class"][cls]
        t, ok = d["total"], d["ok"]
        if t == 0:
            continue
        bar = "█" * int(20 * ok / max(t, 1))
        print(f"    {cls:<42} {_pct(ok, t):>16}   {bar}")

    # By source
    print(f"\n  By source type:")
    for src in ("splitting_packet", "multi_doc", "single_doc"):
        d = stats["by_source"].get(src)
        if not d or d["total"] == 0:
            continue
        t = d["total"]
        print(f"    {src:<20}  cls={_pct(d['cls_ok'], t):>16}  "
              f"pos={_pct(d['pos_ok'], t):>16}  both={_pct(d['both_ok'], t):>16}")


def _mark(pred: dict, gt: dict) -> str:
    c = pred.get("class") == gt.get("class")
    p = pred.get("position") == gt.get("position")
    if c and p:  return "✅"
    if c:        return "🟡 cls✓ pos✗"
    if p:        return "🔴 cls✗ pos✓"
    return              "❌"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EVALUATION LOOP
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_on_test(
    n: int = 200,
    show_n: int = 10,
    run_finetuned: bool = False,
    source_filter: str | None = None,
    save_path: str | None = None,
) -> None:
    examples = [json.loads(l) for l in open(TEST_JSONL, encoding="utf-8")]
    if source_filter:
        examples = [e for e in examples if e.get("source") == source_filter]
    random.seed(42)
    random.shuffle(examples)
    examples = [e for e in examples if (IMG_BASE / e["image"]).exists()][:n]

    src_note = f" (source={source_filter})" if source_filter else ""
    print(f"\nEvaluating {len(examples)} examples from {TEST_JSONL.name}{src_note}")

    base_model, base_proc = load_model("base")
    ft_model,   ft_proc   = (load_model("finetuned") if run_finetuned else (None, None))

    base_stats = _empty_stats()
    ft_stats   = _empty_stats()
    sample_rows: list[dict] = []

    for i, ex in enumerate(examples):
        image    = Image.open(str(IMG_BASE / ex["image"])).convert("RGB")
        gt       = json.loads(ex["label"])
        prev_lbl = ex.get("prev_label", FIRST_PREV)
        source   = ex.get("source", "unknown")

        # Per-example progress line (overwritten each step)
        tag = f"[{i+1:>4}/{len(examples)}]"
        print(f"{tag}  base ...", end="\r", flush=True)

        # Base model — fair natural prompt + flexible JSON/keyword parsing
        base_raw  = run_inference(base_model, base_proc, image,
                                  PROMPT_BASE.format(prev=prev_lbl))
        base_pred = parse_response(base_raw, strict=False)
        _update(base_stats, gt, base_pred, source)

        # Fine-tuned — training prompt + prefer-JSON parsing
        ft_raw = ft_pred = None
        if ft_model:
            print(f"{tag}  ft  ...", end="\r", flush=True)
            ft_raw  = run_inference(ft_model, ft_proc, image,
                                    PROMPT_FINETUNED.format(prev=prev_lbl))
            ft_pred = parse_response(ft_raw, strict=True)
            _update(ft_stats, gt, ft_pred, source)

        if len(sample_rows) < show_n:
            sample_rows.append({
                "i": i + 1,
                "image": ex["image"].split("/")[-1],
                "prev": prev_lbl,
                "source": source,
                "gt": gt,
                "base_raw": base_raw[:150],
                "base_pred": base_pred,
                "ft_raw": (ft_raw or "")[:150],
                "ft_pred": ft_pred,
            })

        # Summary line every 10 examples (kept on screen)
        if (i + 1) % 10 == 0 or (i + 1) == len(examples):
            cls_acc = 100 * base_stats["cls_ok"] / max(base_stats["cls_total"], 1)
            pos_acc = 100 * base_stats["pos_ok"] / max(base_stats["pos_total"], 1)
            line = f"{tag}  base cls={cls_acc:.1f}%  pos={pos_acc:.1f}%"
            if ft_model:
                ft_cls = 100 * ft_stats["cls_ok"] / max(ft_stats["cls_total"], 1)
                ft_pos = 100 * ft_stats["pos_ok"] / max(ft_stats["pos_total"], 1)
                line += f"  |  ft cls={ft_cls:.1f}%  pos={ft_pos:.1f}%"
            print(line, flush=True)

    # ── Sample predictions ────────────────────────────────────────────────────
    total = len(examples)
    print(f"\n{'='*100}")
    print(f"SAMPLE PREDICTIONS  ({min(show_n, len(sample_rows))} of {total})")
    print(f"  Base model    → fair natural-language prompt + flexible JSON/keyword parsing")
    print(f"  Fine-tuned    → exact training prompt + strict JSON parsing")
    print(f"{'='*100}")

    for r in sample_rows:
        gt = r["gt"]
        ext_gt = {k: v for k, v in gt.items() if k not in ("class", "position") and v is not None}
        print(f"\n  ── #{r['i']:>3}  [{r['source']}]  {r['image']}")
        print(f"  prev         : {r['prev']}")
        print(f"  GT           : class={gt.get('class')}  pos={gt.get('position')}")
        if ext_gt:
            for k, v in list(ext_gt.items())[:3]:
                print(f"    gt {k:<22}: {str(v)[:80]}")

        bp = r["base_pred"]
        print(f"  BASE raw     : {r['base_raw']}")
        print(f"  BASE parsed  : class={bp.get('class')}  pos={bp.get('position')}  {_mark(bp, gt)}")
        if ext_gt and bp.get("position") == "START":
            for k in list(ext_gt.keys())[:3]:
                print(f"    base {k:<20}: {str(bp.get(k))[:80]}")

        if r["ft_pred"] is not None:
            fp = r["ft_pred"]
            print(f"  FT raw       : {r['ft_raw']}")
            print(f"  FT parsed    : class={fp.get('class')}  pos={fp.get('position')}  {_mark(fp, gt)}")
            if ext_gt and fp.get("position") == "START":
                for k in list(ext_gt.keys())[:3]:
                    print(f"    ft   {k:<20}: {str(fp.get(k))[:80]}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*100}")
    print("ACCURACY SUMMARY")
    print(f"{'='*100}")
    _print_stats(base_stats, total, "BASE MODEL (Qwen2.5-VL-3B — natural prompt + flexible parsing)")
    if ft_model:
        _print_stats(ft_stats, total, "FINE-TUNED MODEL (v2 adapter — training prompt + strict parsing)")

        # Delta row
        cls_d = (ft_stats["cls_ok"] - base_stats["cls_ok"]) / max(base_stats["cls_total"], 1) * 100
        pos_d = (ft_stats["pos_ok"] - base_stats["pos_ok"]) / max(base_stats["pos_total"], 1) * 100
        both_d = (ft_stats["both_ok"] - base_stats["both_ok"]) / max(total, 1) * 100

        # Extraction delta
        def _ext_avg(s):
            t = sum(s["ext_count"].values())
            v = sum(s["ext_sum"].values())
            return v / t if t else None

        base_ext = _ext_avg(base_stats)
        ft_ext   = _ext_avg(ft_stats)
        ext_d_str = "—"
        if base_ext is not None and ft_ext is not None:
            ext_d_str = f"{(ft_ext - base_ext)*100:+.1f}pp"

        print(f"\n  {'─'*70}")
        print(f"  DELTA  (fine-tuned − base)")
        print(f"  {'─'*70}")
        print(f"  Classification  : {cls_d:+.1f}pp")
        print(f"  Splitting       : {pos_d:+.1f}pp")
        print(f"  Both correct    : {both_d:+.1f}pp")
        print(f"  Extraction avg  : {ext_d_str}")

    # ── Optional JSON save ────────────────────────────────────────────────────
    if save_path:
        def _serialize(stats: dict) -> dict:
            s = {k: v for k, v in stats.items()}
            for key in ("cls_by_class", "pos_by_pos", "by_source"):
                s[key] = {k: dict(v) for k, v in s[key].items()}
            s["ext_sum"]   = dict(s["ext_sum"])
            s["ext_count"] = dict(s["ext_count"])
            return s

        out: dict = {"total": total, "base": _serialize(base_stats)}
        if ft_model:
            out["finetuned"] = _serialize(ft_stats)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"\n  Results saved → {save_path}")


# ─────────────────────────────────────────────────────────────────────────────
# PDF MODE
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_on_pdf(model_type: str, pdf_path: str) -> None:
    import fitz, io
    model, proc = load_model(model_type)
    if model is None:
        print("Model not available.")
        return

    prompt_tmpl = PROMPT_FINETUNED if model_type == "finetuned" else PROMPT_BASE
    strict      = (model_type == "finetuned")

    pdf     = fitz.open(pdf_path)
    prev    = FIRST_PREV
    results = []

    for pg_num, page in enumerate(pdf, 1):
        mat  = fitz.Matrix(150 / 72, 150 / 72)
        img  = Image.open(io.BytesIO(page.get_pixmap(matrix=mat).tobytes("png")))
        raw  = run_inference(model, proc, img, prompt_tmpl.format(prev=prev))
        pred = parse_response(raw, strict=strict)
        cls, pos = pred.get("class"), pred.get("position")
        label = f"{cls} | {pos}" if cls and pos else raw[:60]
        results.append({"page": pg_num, "pred": pred, "label": label})
        print(f"  Page {pg_num:>2}: {label}")
        if cls and pos:
            prev = label  # keep "ClassName | POSITION" format for context

    pdf.close()

    # Segment into documents by START boundaries
    docs, current = [], None
    for r in results:
        cls, pos = r["pred"].get("class"), r["pred"].get("position")
        pg = r["page"]
        if pos == "START" or current is None:
            if current:
                docs.append(current)
            fields = {k: v for k, v in r["pred"].items()
                      if k not in ("class", "position") and v is not None}
            current = {"class": cls or "Unknown", "page_start": pg, "page_end": pg,
                       "fields": fields}
        else:
            if current:
                current["page_end"] = pg

    if current:
        docs.append(current)

    print(f"\n  IDENTIFIED DOCUMENTS ({len(docs)}):")
    for i, d in enumerate(docs, 1):
        n_pages = d["page_end"] - d["page_start"] + 1
        pg_str  = f"p{d['page_start']}" if n_pages == 1 else f"p{d['page_start']}–{d['page_end']}"
        print(f"  {i}. {d['class']} ({n_pages} page(s), {pg_str})")
        for k, v in d.get("fields", {}).items():
            print(f"       {k}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Evaluate base vs fine-tuned model on DHL document classification, splitting, and extraction."
    )
    ap.add_argument("--test",      action="store_true", help="Run evaluation on test set")
    ap.add_argument("--pdf",       type=str,  default=None,  help="Run on a PDF file")
    ap.add_argument("--n",         type=int,  default=200,   help="Number of test examples (default 200)")
    ap.add_argument("--show",      type=int,  default=10,    help="Number of sample predictions to print")
    ap.add_argument("--finetuned", action="store_true",      help="Also evaluate the fine-tuned model")
    ap.add_argument("--source",    type=str,  default=None,
                    choices=["single_doc", "multi_doc", "splitting_packet"],
                    help="Filter test examples by source type")
    ap.add_argument("--save",      type=str,  default=None,  help="Save summary statistics to a JSON file")
    args = ap.parse_args()

    if not args.test and not args.pdf:
        ap.print_help()
        sys.exit(0)

    if args.test:
        evaluate_on_test(
            n=args.n,
            show_n=args.show,
            run_finetuned=args.finetuned,
            source_filter=args.source,
            save_path=args.save,
        )

    if args.pdf:
        model_type = "finetuned" if args.finetuned else "base"
        evaluate_on_pdf(model_type, args.pdf)
