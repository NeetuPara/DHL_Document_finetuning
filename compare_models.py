"""
Side-by-side comparison: Ground Truth vs Base Model vs Fine-tuned Model

Tests two different prompts for the base model:
  Prompt A: Our fine-tuned format (Previous page: ... | Output: Class | START/CONT)
  Prompt B: Natural prompt better suited for the base model

Run:
    python compare_models.py            # 10 examples, both models
    python compare_models.py --n 50     # 50 examples
    python compare_models.py --skip-ft  # skip fine-tuned (if not trained yet)
"""

import argparse, json, random, sys
from pathlib import Path
from PIL import Image

BASE_DIR   = Path(__file__).parent
TEST_JSONL = BASE_DIR / "Training_Data" / "test.jsonl"
IMG_BASE   = BASE_DIR / "Training_Data"
MODEL_PATH = BASE_DIR / "models" / "Qwen2.5-VL-3B-Instruct"
LORA_PATH  = BASE_DIR / "model_output" / "final"
MAX_PIXELS = 1_000_000

CLASSES = [
    "Commercial Invoice", "House Bill of Lading", "Certificate of Origin",
    "Shipper's Letter of Instruction", "Dangerous Goods Declaration",
    "Verified Gross Mass", "House Airway Bill", "Packing List",
    "Customs Declaration", "Cargo Manifest", "Import/Export License",
    "Power of Attorney",
]
CLASS_LIST = "\n".join(f"  - {c}" for c in CLASSES)

# ── Prompt A: fine-tuned format (what we trained on) ──────────────────────────
PROMPT_A = (
    "Analyze this DHL logistics document page.\n\n"
    "Previous page: {prev}\n\n"
    "Output format: <document_class> | <START or CONTINUATION>\n\n"
    "Document classes: " + ", ".join(CLASSES) + "\n\n"
    "START = first page of a new document\n"
    "CONTINUATION = this page continues the same document as the previous page"
)

# ── Prompt B: natural prompt better suited to the base model ──────────────────
PROMPT_B = (
    "Look at this logistics document image and answer two questions:\n\n"
    "1. DOCUMENT TYPE — which of these is it?\n"
    + CLASS_LIST + "\n\n"
    "2. PAGE POSITION — is this page:\n"
    "   START: the first page of a new document\n"
    "   CONTINUATION: this page continues from the previous page\n"
    "   (Previous page context: {prev})\n\n"
    "Reply in this exact format on one line:\n"
    "<Document Type> | <START or CONTINUATION>\n\n"
    "Example: Commercial Invoice | START"
)

FIRST_PREV = "none (first page of batch)"

# ── Model helpers ──────────────────────────────────────────────────────────────
_models = {}

def load_model(model_type: str):
    if model_type in _models:
        return _models[model_type]
    from unsloth import FastVisionModel
    if model_type == "finetuned":
        if not LORA_PATH.exists():
            print(f"  Fine-tuned model not found at {LORA_PATH}")
            return None, None
        print(f"\nLoading FINE-TUNED from {LORA_PATH} ...")
        model, proc = FastVisionModel.from_pretrained(str(LORA_PATH), load_in_4bit=True)
    else:
        print(f"\nLoading BASE model from {MODEL_PATH} ...")
        model, proc = FastVisionModel.from_pretrained(str(MODEL_PATH), load_in_4bit=True)
    FastVisionModel.for_inference(model); model.eval()
    _models[model_type] = (model, proc)
    return model, proc


def resize(image):
    w, h = image.size
    if w * h > MAX_PIXELS:
        s = (MAX_PIXELS / (w * h)) ** 0.5
        image = image.resize((int(w*s), int(h*s)), Image.LANCZOS)
    return image


def predict(model, processor, image, prompt_text):
    import torch
    img = resize(image)
    msgs = [{"role": "user", "content": [
        {"type": "image"},
        {"type": "text", "text": prompt_text},
    ]}]
    text   = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[img], return_tensors="pt", padding=True).to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=30, do_sample=False)
    full   = processor.decode(out[0], skip_special_tokens=True)
    answer = full.split("assistant")[-1].strip() if "assistant" in full else full.strip()
    return answer.replace("<|im_end|>", "").strip()


def parse(pred):
    if " | " not in pred:
        return None, None
    cls, pos = pred.split(" | ", 1)
    cls, pos = cls.strip(), pos.strip()
    if cls not in CLASSES or pos not in ("START", "CONTINUATION"):
        return cls.strip(), pos.strip()
    return cls, pos


def match(pred, truth):
    p = pred.strip().lower().replace("<","").replace(">","")
    t = truth.strip().lower()
    return p == t


# ── Scoring helpers ────────────────────────────────────────────────────────────
def score_prediction(pred: str, truth: str):
    """Returns (exact_match, class_match, pos_match)"""
    exact = pred.strip() == truth.strip()
    pc, pp = parse(pred)
    tc, tp = parse(truth)
    cls_ok = (pc is not None and pc == tc)
    pos_ok = (pp is not None and pp == tp)
    return exact, cls_ok, pos_ok


# ── Main comparison ────────────────────────────────────────────────────────────
def run_comparison(n: int = 10, skip_ft: bool = False):
    examples = [json.loads(l) for l in open(TEST_JSONL, encoding="utf-8")]
    random.seed(42)
    random.shuffle(examples)
    sample = [e for e in examples if (BASE_DIR / "Training_Data" / e["image"]).exists()][:n]

    base_model, base_proc = load_model("base")
    ft_model, ft_proc = (None, None) if skip_ft else load_model("finetuned")

    results = []
    for i, ex in enumerate(sample):
        image      = Image.open(str(BASE_DIR / "Training_Data" / ex["image"])).convert("RGB")
        truth      = ex["label"]
        prev_label = ex.get("prev_label", FIRST_PREV)

        pA = predict(base_model, base_proc, image, PROMPT_A.format(prev=prev_label))
        pB = predict(base_model, base_proc, image, PROMPT_B.format(prev=prev_label))
        pFT = predict(ft_model, ft_proc, image, PROMPT_A.format(prev=prev_label)) if ft_model else "N/A"

        results.append({
            "idx":     i + 1,
            "image":   ex["image"].split("/")[-1],
            "prev":    prev_label,
            "truth":   truth,
            "base_A":  pA,
            "base_B":  pB,
            "ft":      pFT,
        })
        print(f"  [{i+1:>3}/{n}] done", end="\r")

    # ── Print comparison table ────────────────────────────────────────────────
    print(f"\n\n{'='*90}")
    print(f"SIDE-BY-SIDE COMPARISON  (n={n})")
    print(f"{'='*90}")
    print(f"{'#':<3}  {'Ground Truth':<46} {'Base (trained fmt)':<46} {'Base (natural fmt)':<46} {'Fine-tuned':<46}")
    print(f"{'─'*3}  {'─'*45} {'─'*45} {'─'*45} {'─'*45}")

    for r in results:
        eA,  cA,  pA  = score_prediction(r["base_A"], r["truth"])
        eB,  cB,  pB  = score_prediction(r["base_B"], r["truth"])
        eFT, cFT, pFT = score_prediction(r["ft"], r["truth"]) if r["ft"] != "N/A" else (False, False, False)

        def tag(exact, cls_ok, pos_ok):
            if exact:   return "✅"
            if cls_ok and pos_ok: return "✅"
            if cls_ok:  return "🟡"  # class right, position wrong
            return "❌"

        print(f"{r['idx']:<3}  {r['truth']:<46} "
              f"{tag(eA,cA,pA)} {r['base_A'][:42]:<44} "
              f"{tag(eB,cB,pB)} {r['base_B'][:42]:<44} "
              f"{tag(eFT,cFT,pFT)} {r['ft'][:42]:<44}")
        print(f"     prev: {r['prev'][:80]}")
        print()

    # ── Accuracy summary ──────────────────────────────────────────────────────
    print(f"\n{'='*90}")
    print("ACCURACY SUMMARY")
    print(f"{'='*90}")

    def summarise(key, label):
        exact = cls_ok = pos_ok = 0
        for r in results:
            e, c, p = score_prediction(r[key], r["truth"])
            if e: exact += 1
            if c: cls_ok += 1
            if p: pos_ok += 1
        total = len(results)
        print(f"  {label:<35} Exact={exact}/{total} ({100*exact//total}%)  "
              f"Class={cls_ok}/{total} ({100*cls_ok//total}%)  "
              f"Position={pos_ok}/{total} ({100*pos_ok//total}%)")

    summarise("base_A", "Base model — trained prompt (A)")
    summarise("base_B", "Base model — natural prompt  (B)")
    if ft_model:
        summarise("ft",    "Fine-tuned model — trained prompt")

    print()
    print("Legend: ✅ exact match  🟡 class correct, position wrong  ❌ wrong")
    print()
    print("Key insight: Compare Base(A) vs Base(B) — if (B) is much better,")
    print("the base model knows the documents but struggles with our format.")
    print("Compare Base(B) vs Fine-tuned — shows pure learning gain.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n",        type=int,  default=10,    help="Number of examples (default 10)")
    p.add_argument("--skip-ft",  action="store_true",      help="Skip fine-tuned model")
    p.add_argument("--seed",     type=int,  default=42,    help="Random seed")
    args = p.parse_args()
    random.seed(args.seed)
    run_comparison(n=args.n, skip_ft=args.skip_ft)
