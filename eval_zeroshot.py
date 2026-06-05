"""
Zero-shot baseline evaluation — no fine-tuning, models used as-is.

Supports three model families:

  qwen    — Qwen2.5-VL (general VLM, our base model family)
  internvl2 — InternVL2 (document-understanding focused VLM, pre-trained on
               DocVQA / DocLayNet / OCR tasks — purpose-built for documents)

Computes four paper metrics:
  - Class Accuracy    : predicted class == ground-truth class
  - Position Accuracy : predicted position (START/CONTINUATION) matches GT
  - Field F1          : precision/recall/F1 over non-null fields on START pages
  - Split IoU         : Jaccard similarity of predicted vs true START boundaries
                        per splitting-packet, then macro-averaged

Usage
-----
# Zero-shot Qwen2.5-VL-3B  (model already on disk)
python eval_zeroshot.py --model-type qwen --model-path models/Qwen2.5-VL-3B-Instruct

# Zero-shot Qwen2.5-VL-7B  (download first)
python eval_zeroshot.py --model-type qwen --model-path models/Qwen2.5-VL-7B-Instruct --tag 7b

# Zero-shot InternVL2-2B  (document-understanding specific, downloads automatically)
python eval_zeroshot.py --model-type internvl2

# Quick smoke-test (20 samples)
python eval_zeroshot.py --model-type qwen --model-path models/Qwen2.5-VL-3B-Instruct --max-samples 20

Results are written to:
  eval_results/<tag>_results.json     — per-sample predictions
  eval_results/<tag>_metrics.json     — final metrics summary
"""

import argparse
import json
import os
import re
import time
from pathlib import Path
from collections import defaultdict

# ── Constants (must match prepare_dataset_v2.py) ─────────────────────────────

CLASSES = [
    "Commercial Invoice", "House Bill of Lading", "Certificate of Origin",
    "Shipper's Letter of Instruction", "Dangerous Goods Declaration",
    "Verified Gross Mass", "House Airway Bill", "Packing List",
    "Customs Declaration", "Cargo Manifest", "Import/Export License",
    "Power of Attorney",
]
CLASS_SET = set(CLASSES)

# Fields expected in a START response
START_FIELDS = [
    "shipper_name", "consignee_name", "document_date", "document_number",
    "country_of_origin", "country_of_destination", "description_of_goods",
    "gross_weight_kg", "net_weight_kg", "total_weight_kg",
    "license_number", "validity_start", "validity_end", "licensee_name",
]

# Same prompt template used during training
PROMPT = (
    "Analyze this DHL logistics document page.\n\n"
    "Previous page: {prev}\n\n"
    "Output a single JSON line.\n\n"
    "If this is the START (first page of a new document):\n"
    '  {{"class": "...", "position": "START", "shipper_name": "...", '
    '"consignee_name": "...", "document_date": "...", "document_number": "...", '
    '"country_of_origin": "...", "country_of_destination": "...", '
    '"description_of_goods": "...", '
    '"gross_weight_kg": ..., "net_weight_kg": ..., "total_weight_kg": ..., '
    '"license_number": "...", "validity_start": "...", '
    '"validity_end": "...", "licensee_name": "..."}}\n\n'
    "If this is a CONTINUATION (same document continues from previous page):\n"
    '  {{"class": "...", "position": "CONTINUATION"}}\n\n'
    "Document classes: " + ", ".join(CLASSES) + "\n\n"
    "Use null for weight fields not labeled as gross, net, or total on this page. "
    "Use null for all other fields not visible on this page."
)


# ── Argument parsing ──────────────────────────────────────────────────────────

_INTERNVL2_DEFAULT = "OpenGVLab/InternVL2-2B"

def parse_args():
    p = argparse.ArgumentParser(description="Zero-shot VLM evaluation (no fine-tuning)")
    p.add_argument("--model-type", default="qwen", choices=["qwen", "internvl2"],
                   help="Model family: qwen (Qwen2.5-VL) or internvl2 (document-focused VLM)")
    p.add_argument("--model-path", default="",
                   help="Path or HF repo to the model. "
                        "Defaults: qwen → models/Qwen2.5-VL-3B-Instruct, "
                        f"internvl2 → {_INTERNVL2_DEFAULT}")
    p.add_argument("--tag", default="",
                   help="Short label for output filenames (default: inferred)")
    p.add_argument("--max-samples", type=int, default=500,
                   help="Max samples (0 = all; default 500, stratified by class)")
    p.add_argument("--max-new-tokens", type=int, default=220,
                   help="Max tokens to generate per page (default 220)")
    p.add_argument("--test-jsonl", default="Training_Data_v2/test.jsonl")
    p.add_argument("--image-base", default="Training_Data",
                   help="Base dir for image paths in JSONL")
    p.add_argument("--resume", action="store_true",
                   help="Skip already-evaluated samples if output file exists")
    p.add_argument("--no-cuda", action="store_true",
                   help="Force CPU (debug only)")
    return p.parse_args()


# ── Model loading ─────────────────────────────────────────────────────────────

def load_model(model_path: str, model_type: str, use_cuda: bool = True):
    """Load a VLM for zero-shot inference. Supports qwen and internvl2."""
    import torch
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32       = True

    device = "cuda" if (use_cuda and torch.cuda.is_available()) else "cpu"
    print(f"Loading {model_type} model from: {model_path}")
    print("  Zero-shot — no fine-tuning applied.")

    if model_type == "internvl2":
        return _load_internvl2(model_path, device)
    else:
        return _load_qwen(model_path, device)


def _load_qwen(model_path: str, device: str):
    import torch
    from transformers import AutoProcessor
    try:
        from transformers import Qwen2_5_VLForConditionalGeneration as ModelClass
    except ImportError:
        try:
            from transformers import Qwen2VLForConditionalGeneration as ModelClass
        except ImportError:
            from transformers import AutoModelForVision2Seq as ModelClass

    model = ModelClass.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map=device,
    )
    model.eval()
    processor = AutoProcessor.from_pretrained(model_path)
    print(f"  Params: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B  |  Device: {device}")
    return model, processor


def _load_internvl2(model_path: str, device: str):
    """
    Load InternVL2 — document-understanding focused VLM from OpenGVLab.
    Pre-trained on: DocVQA, DocLayNet, TextVQA, OCR-related tasks.
    Recommended: OpenGVLab/InternVL2-2B  (~2B params, ~4 GB VRAM bfloat16)
    """
    import torch
    from transformers import AutoModel, AutoTokenizer

    model = AutoModel.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map=device,
        trust_remote_code=True,
    )
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    print(f"  Params: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B  |  Device: {device}")
    # Return tokenizer as "processor" slot — internvl2 path uses it differently
    return model, tokenizer


# ── Prompt building ───────────────────────────────────────────────────────────

_PROMPT_TMPL_CACHE = None

def _qwen_prompt(processor, prev: str) -> str:
    global _PROMPT_TMPL_CACHE
    if _PROMPT_TMPL_CACHE is None:
        _PROMPT_TMPL_CACHE = processor.apply_chat_template(
            [{"role": "user", "content": [
                {"type": "image"},
                {"type": "text", "text": "PLACEHOLDER"},
            ]}],
            tokenize=False, add_generation_prompt=True,
        )
    return _PROMPT_TMPL_CACHE.replace("PLACEHOLDER", PROMPT.format(prev=prev))


# ── Inference ─────────────────────────────────────────────────────────────────

def run_inference(model, processor, image, prev_label: str,
                  max_new_tokens: int, model_type: str) -> str:
    if model_type == "internvl2":
        return _infer_internvl2(model, processor, image, prev_label, max_new_tokens)
    else:
        return _infer_qwen(model, processor, image, prev_label, max_new_tokens)


def _infer_qwen(model, processor, image, prev_label: str, max_new_tokens: int) -> str:
    import torch
    text   = _qwen_prompt(processor, prev_label)
    inputs = processor(text=[text], images=[image], return_tensors="pt", padding=False)
    inputs = inputs.to(next(model.parameters()).device)
    with torch.inference_mode():
        output = model.generate(
            **inputs, max_new_tokens=max_new_tokens, do_sample=False, use_cache=True,
        )
    n_input = inputs["input_ids"].shape[1]
    raw = processor.decode(output[0][n_input:], skip_special_tokens=True)
    return raw.replace("<|im_end|>", "").strip()


def _internvl2_pixel_values(pil_image):
    """
    Preprocess a PIL image for InternVL2.
    Uses 4-tile dynamic split (2×2) so the model sees the full page at higher resolution.
    Each tile: 448×448, normalized with ImageNet stats.
    """
    import torch
    import torchvision.transforms as T
    from torchvision.transforms.functional import InterpolationMode

    MEAN = (0.485, 0.456, 0.406)
    STD  = (0.229, 0.224, 0.225)
    SIZE = 448

    transform = T.Compose([
        T.Resize((SIZE, SIZE), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=MEAN, std=STD),
    ])

    img = pil_image.convert("RGB")
    w, h = img.size

    # Split into 2×2 tiles for better resolution on A4-sized documents
    tiles = []
    for row in range(2):
        for col in range(2):
            left  = col * w // 2
            upper = row * h // 2
            right = (col + 1) * w // 2
            lower = (row + 1) * h // 2
            tiles.append(transform(img.crop((left, upper, right, lower))))

    # Also add a thumbnail of the full image (InternVL2 "global" tile)
    tiles.append(transform(img))

    return torch.stack(tiles)  # (5, 3, 448, 448)


def _infer_internvl2(model, tokenizer, image, prev_label: str, max_new_tokens: int) -> str:
    import torch
    device = next(model.parameters()).device
    pixel_values = _internvl2_pixel_values(image).to(torch.bfloat16).to(device)

    prompt_text = PROMPT.format(prev=prev_label)
    generation_config = dict(
        max_new_tokens=max_new_tokens,
        do_sample=False,
        use_cache=True,
    )
    with torch.inference_mode():
        response = model.chat(tokenizer, pixel_values, prompt_text, generation_config)
    return response.strip() if isinstance(response, str) else str(response).strip()


# ── Response parsing ──────────────────────────────────────────────────────────

def parse_response(raw: str) -> dict:
    """Parse model output into a dict. Mirrors dhl_app.py logic."""
    raw = raw.strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            if obj.get("class") not in CLASS_SET:
                obj["class"] = None
            if obj.get("position") not in ("START", "CONTINUATION"):
                obj["position"] = None
            return obj
    except Exception:
        pass

    # Try to extract first {...} block
    m = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group())
            if isinstance(obj, dict):
                if obj.get("class") not in CLASS_SET:
                    obj["class"] = None
                if obj.get("position") not in ("START", "CONTINUATION"):
                    obj["position"] = None
                return obj
        except Exception:
            pass

    # Last resort: keyword scan
    found_cls = None
    for c in sorted(CLASS_SET, key=len, reverse=True):
        if c.lower() in raw.lower():
            found_cls = c
            break

    found_pos = None
    if re.search(r"\bCONTINUATION\b", raw, re.IGNORECASE):
        found_pos = "CONTINUATION"
    elif re.search(r"\bSTART\b", raw, re.IGNORECASE):
        found_pos = "START"

    return {"class": found_cls, "position": found_pos}


# ── Metric helpers ────────────────────────────────────────────────────────────

def _norm(val) -> str:
    """Normalize a field value to a lowercase string for comparison."""
    if val is None:
        return ""
    return str(val).lower().strip()


def _token_f1(pred_str: str, true_str: str) -> float:
    """Token-level F1 (like SQuAD) between two strings."""
    pred_tokens = pred_str.lower().split()
    true_tokens = true_str.lower().split()
    if not pred_tokens or not true_tokens:
        return 1.0 if pred_tokens == true_tokens else 0.0
    common = set(pred_tokens) & set(true_tokens)
    tp = sum(min(pred_tokens.count(t), true_tokens.count(t)) for t in common)
    if tp == 0:
        return 0.0
    precision = tp / len(pred_tokens)
    recall    = tp / len(true_tokens)
    return 2 * precision * recall / (precision + recall)


def compute_field_metrics(pred: dict, true: dict):
    """
    Compute TP, FP, FN counts for fields on a START page.

    Strategy:
      - For each field in START_FIELDS:
        - GT non-null + pred non-null + token_f1 >= 0.5  → TP (weighted by f1)
        - GT non-null + pred null                         → FN
        - GT null     + pred non-null                     → FP
        - GT null     + pred null                         → TN (ignored)
    """
    tp = fp = fn = 0.0

    for field in START_FIELDS:
        gt_val   = true.get(field)
        pred_val = pred.get(field)

        gt_has   = gt_val is not None and _norm(gt_val) != ""
        pred_has = pred_val is not None and _norm(pred_val) != ""

        if gt_has and pred_has:
            f1 = _token_f1(_norm(pred_val), _norm(gt_val))
            tp += f1
            fn += (1.0 - f1)   # partial miss
        elif gt_has and not pred_has:
            fn += 1.0
        elif not gt_has and pred_has:
            fp += 1.0
        # else: TN — both null, ignore

    return tp, fp, fn


# ── Stratified sampling ───────────────────────────────────────────────────────

def stratified_sample(samples: list, n: int) -> list:
    """
    Return up to n samples, balanced across (class, position) combinations.
    Preserves packet ordering within each group for Split IoU accuracy.
    """
    if n <= 0:
        return samples

    # Group by class
    by_class = defaultdict(list)
    for s in samples:
        label = json.loads(s["label"])
        cls   = label.get("class", "Unknown")
        by_class[cls].append(s)

    n_classes  = len(by_class)
    per_class  = max(1, n // n_classes)
    result     = []

    for cls, group in sorted(by_class.items()):
        # Within each class, keep balanced START/CONTINUATION
        starts = [s for s in group if json.loads(s["label"]).get("position") == "START"]
        conts  = [s for s in group if json.loads(s["label"]).get("position") != "START"]
        half   = per_class // 2
        result.extend(starts[:half])
        result.extend(conts[:per_class - half])

    # Pad / trim to exactly n
    if len(result) < n:
        remaining = [s for s in samples if s not in set(id(x) for x in result)]
        result.extend(remaining[:n - len(result)])
    return result[:n]


# ── Main evaluation loop ──────────────────────────────────────────────────────

def main():
    args  = parse_args()
    base  = Path(__file__).parent
    out_dir = base / "eval_results"
    out_dir.mkdir(exist_ok=True)

    # Derive output tag
    tag = args.tag or (Path(model_path).name.replace(" ", "_") + f"_{args.model_type}")
    results_path = out_dir / f"{tag}_results.json"
    metrics_path = out_dir / f"{tag}_metrics.json"

    # ── Load test data ────────────────────────────────────────────────────────
    test_path = base / args.test_jsonl
    print(f"Loading test data from: {test_path}")
    with open(test_path) as f:
        all_samples = [json.loads(line) for line in f]
    print(f"  Total samples in test split: {len(all_samples)}")

    # ── Stratified sampling ───────────────────────────────────────────────────
    samples = stratified_sample(all_samples, args.max_samples)
    print(f"  Evaluating: {len(samples)} samples"
          + (" (stratified)" if args.max_samples > 0 else " (full set)"))

    # ── Resume support ────────────────────────────────────────────────────────
    done_images = set()
    existing_results = []
    if args.resume and results_path.exists():
        with open(results_path) as f:
            existing_results = json.load(f)
        done_images = {r["image"] for r in existing_results}
        print(f"  Resuming: {len(done_images)} samples already done")

    to_eval = [s for s in samples if s["image"] not in done_images]
    print(f"  Remaining: {len(to_eval)} samples to evaluate")

    if not to_eval:
        print("All samples already evaluated. Computing metrics only.")
        compute_and_save_metrics(existing_results, metrics_path, tag)
        return

    # ── Resolve model path ────────────────────────────────────────────────────
    if args.model_path:
        model_path = args.model_path
        local = base / model_path
        if local.exists():
            model_path = str(local)
    else:
        if args.model_type == "internvl2":
            model_path = _INTERNVL2_DEFAULT   # downloads from HuggingFace Hub
        else:
            model_path = str(base / "models" / "Qwen2.5-VL-3B-Instruct")

    # For local paths, verify they exist
    if not model_path.startswith("OpenGVLab/") and not Path(model_path).exists():
        print(f"\nERROR: Model not found at {model_path}")
        if args.model_type == "qwen":
            print("For 7B: huggingface-cli download Qwen/Qwen2.5-VL-7B-Instruct "
                  "--local-dir models/Qwen2.5-VL-7B-Instruct")
        return

    model, processor = load_model(model_path, args.model_type, use_cuda=not args.no_cuda)
    image_base = base / args.image_base

    # ── Evaluation loop ───────────────────────────────────────────────────────
    results    = list(existing_results)
    save_every = 50
    t_start    = time.time()

    print(f"\n{'─'*60}")
    print(f"  Model  : {tag}  (zero-shot, no fine-tuning)")
    print(f"  Type   : {args.model_type}")
    print(f"  Samples: {len(to_eval)}")
    print(f"{'─'*60}")

    for i, sample in enumerate(to_eval):
        from PIL import Image

        img_path   = image_base / sample["image"]
        label_str  = sample["label"]
        prev_label = sample.get("prev_label", "none (first page of batch)")
        true_label = json.loads(label_str)

        # Load image
        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"  [SKIP] Cannot open image {img_path}: {e}")
            continue

        # Run inference
        t0 = time.time()
        try:
            raw_output = run_inference(model, processor, image, prev_label,
                                       args.max_new_tokens, args.model_type)
        except Exception as e:
            print(f"  [ERROR] Inference failed for {img_path}: {e}")
            raw_output = ""

        elapsed_s = time.time() - t0
        pred = parse_response(raw_output)

        # Compute per-sample metrics
        true_cls  = true_label.get("class")
        pred_cls  = pred.get("class")
        true_pos  = true_label.get("position")
        pred_pos  = pred.get("position")

        class_correct = (pred_cls == true_cls)
        pos_correct   = (pred_pos == true_pos)

        # Field metrics only for START pages
        tp = fp = fn = 0.0
        if true_pos == "START":
            tp, fp, fn = compute_field_metrics(pred, true_label)

        results.append({
            "image":         sample["image"],
            "source":        sample.get("source", ""),
            "true_class":    true_cls,
            "pred_class":    pred_cls,
            "true_position": true_pos,
            "pred_position": pred_pos,
            "class_correct": class_correct,
            "pos_correct":   pos_correct,
            "is_start":      (true_pos == "START"),
            "field_tp":      tp,
            "field_fp":      fp,
            "field_fn":      fn,
            "raw_output":    raw_output,
            "inference_s":   round(elapsed_s, 2),
        })

        # Progress log
        done    = i + 1
        elapsed = time.time() - t_start
        eta_s   = (elapsed / done) * (len(to_eval) - done) if done > 0 else 0
        print(
            f"  [{done:>4}/{len(to_eval)}] "
            f"cls={'✓' if class_correct else '✗'}  "
            f"pos={'✓' if pos_correct else '✗'}  "
            f"tp={tp:.1f} fp={fp:.1f} fn={fn:.1f}  "
            f"{elapsed_s:.1f}s  ETA {eta_s/60:.0f}m  "
            f"{Path(sample['image']).name}"
        )

        # Save progress
        if done % save_every == 0:
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2)
            print(f"  → Saved {len(results)} results to {results_path}")

    # Final save
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: {results_path}")

    compute_and_save_metrics(results, metrics_path, tag)


# ── Metrics computation ───────────────────────────────────────────────────────

def compute_and_save_metrics(results: list, metrics_path: Path, tag: str):
    """Compute the four paper metrics and save to JSON."""

    # ── 1. Class Accuracy ────────────────────────────────────────────────────
    class_correct = [r["class_correct"] for r in results]
    class_acc = sum(class_correct) / len(class_correct) * 100 if class_correct else 0.0

    # ── 2. Position Accuracy ─────────────────────────────────────────────────
    pos_correct = [r["pos_correct"] for r in results]
    pos_acc = sum(pos_correct) / len(pos_correct) * 100 if pos_correct else 0.0

    # ── 3. Field F1 (START pages only) ───────────────────────────────────────
    start_results = [r for r in results if r["is_start"]]
    if start_results:
        total_tp = sum(r["field_tp"] for r in start_results)
        total_fp = sum(r["field_fp"] for r in start_results)
        total_fn = sum(r["field_fn"] for r in start_results)
        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        recall    = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        field_f1  = 2 * precision * recall / (precision + recall) * 100 \
                    if (precision + recall) > 0 else 0.0
    else:
        precision = recall = field_f1 = 0.0

    # ── 4. Split IoU ─────────────────────────────────────────────────────────
    # Group pages by splitting packet (e.g. "packet_1788_p9.png" → "packet_1788")
    packets = defaultdict(list)
    for r in results:
        img = r["image"]
        m = re.search(r"(packet_\d+)", img)
        key = m.group(1) if m else img
        packets[key].append(r)

    iou_scores = []
    for key, pages in packets.items():
        # Stable ordering by page number suffix (p1, p2, ...)
        def page_num(r):
            m = re.search(r"_p(\d+)", r["image"])
            return int(m.group(1)) if m else 0
        pages = sorted(pages, key=page_num)

        true_starts = set(j for j, r in enumerate(pages) if r["true_position"] == "START")
        pred_starts = set(j for j, r in enumerate(pages) if r["pred_position"] == "START")

        intersection = len(true_starts & pred_starts)
        union        = len(true_starts | pred_starts)
        iou_scores.append(intersection / union if union > 0 else 1.0)

    split_iou = (sum(iou_scores) / len(iou_scores) * 100) if iou_scores else 0.0

    # ── Per-class breakdown ───────────────────────────────────────────────────
    per_class = defaultdict(lambda: {"total": 0, "class_correct": 0, "pos_correct": 0})
    for r in results:
        cls = r["true_class"] or "Unknown"
        per_class[cls]["total"]         += 1
        per_class[cls]["class_correct"] += int(r["class_correct"])
        per_class[cls]["pos_correct"]   += int(r["pos_correct"])

    per_class_acc = {
        cls: {
            "n": v["total"],
            "class_acc": v["class_correct"] / v["total"] * 100,
            "pos_acc":   v["pos_correct"]   / v["total"] * 100,
        }
        for cls, v in sorted(per_class.items())
    }

    # ── Print summary ─────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  RESULTS — {tag}  (zero-shot)")
    print("=" * 60)
    print(f"  Samples evaluated : {len(results)}")
    print(f"  START pages       : {len(start_results)}")
    print()
    print(f"  Class Accuracy    : {class_acc:.1f}%")
    print(f"  Position Accuracy : {pos_acc:.1f}%")
    print(f"  Field F1          : {field_f1:.1f}%  "
          f"(P={precision*100:.1f}% R={recall*100:.1f}%)")
    print(f"  Split IoU         : {split_iou:.1f}%  "
          f"(over {len(iou_scores)} packets)")
    print()
    print("  Per-class accuracy:")
    for cls, v in per_class_acc.items():
        print(f"    {cls:<40} n={v['n']:>4}  "
              f"cls={v['class_acc']:>5.1f}%  pos={v['pos_acc']:>5.1f}%")
    print("=" * 60)

    # ── Save metrics ──────────────────────────────────────────────────────────
    metrics = {
        "model":              tag,
        "mode":               "zero-shot (no fine-tuning)",
        "samples_evaluated":  len(results),
        "start_pages":        len(start_results),
        "class_accuracy":     round(class_acc,   2),
        "position_accuracy":  round(pos_acc,     2),
        "field_f1":           round(field_f1,    2),
        "field_precision":    round(precision * 100, 2),
        "field_recall":       round(recall * 100,    2),
        "split_iou":          round(split_iou,   2),
        "packets_evaluated":  len(iou_scores),
        "per_class":          per_class_acc,
    }

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved: {metrics_path}")
    return metrics


if __name__ == "__main__":
    main()
