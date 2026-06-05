"""
Merge LoRA adapters into base model and save as standalone bfloat16 models.

Merges both v3 models in one run:
  model_output_v3/final          → model_output_v3/merged        (eval + dhl_app)
  model_output_v3/checkpoint-2000 → model_output_v3/ck2000_merged (eval comparison)

Uses plain PEFT + transformers — no Unsloth — to avoid Unsloth's save bug
when the base model comes from a local directory.

Run ONCE before eval or inference:
    python merge_model.py

Each output is ~6.5 GB bfloat16. Loads as a plain HuggingFace model with
zero PEFT/adapter overhead — same speed as the base model.
"""

import os, shutil
os.environ["TORCHDYNAMO_DISABLE"] = "1"

import torch
from pathlib import Path
from transformers import AutoProcessor

BASE_DIR   = Path(__file__).parent
MODEL_PATH = BASE_DIR / "models" / "Qwen2.5-VL-3B-Instruct"

MERGE_JOBS = [
    (BASE_DIR / "model_output_v3" / "final",           BASE_DIR / "model_output_v3" / "merged"),
    (BASE_DIR / "model_output_v3" / "checkpoint-2000", BASE_DIR / "model_output_v3" / "ck2000_merged"),
    (BASE_DIR / "model_output_v3" / "checkpoint-2250", BASE_DIR / "model_output_v3" / "ck2250_merged"),
]

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Base model not found: {MODEL_PATH}")

try:
    from transformers import Qwen2_5_VLForConditionalGeneration as ModelClass
except ImportError:
    try:
        from transformers import Qwen2VLForConditionalGeneration as ModelClass
    except ImportError:
        from transformers import AutoModelForVision2Seq as ModelClass

from peft import PeftModel

for LORA_PATH, MERGED_DIR in MERGE_JOBS:
    print()
    print("=" * 60)
    print(f"  LoRA   : {LORA_PATH.name}")
    print(f"  Output : {MERGED_DIR.name}")
    print("=" * 60)

    if not LORA_PATH.exists():
        print(f"  SKIP — {LORA_PATH} not found")
        continue

    if MERGED_DIR.exists():
        print(f"  Removing previous output at {MERGED_DIR} ...")
        shutil.rmtree(MERGED_DIR)

    print("\nLoading base model (bfloat16) ...")
    base_model = ModelClass.from_pretrained(
        str(MODEL_PATH), torch_dtype=torch.bfloat16, device_map="cuda")
    print(f"  {sum(p.numel() for p in base_model.parameters()) / 1e9:.2f}B params")

    print("Loading LoRA adapters ...")
    peft_model = PeftModel.from_pretrained(
        base_model, str(LORA_PATH), torch_dtype=torch.bfloat16)

    print("Merging ...")
    merged = peft_model.merge_and_unload()
    print("  Merge complete.")

    print(f"Saving to {MERGED_DIR} ...")
    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(MERGED_DIR), safe_serialization=True)
    AutoProcessor.from_pretrained(str(LORA_PATH)).save_pretrained(str(MERGED_DIR))

    total_mb = sum(f.stat().st_size for f in MERGED_DIR.rglob("*") if f.is_file()) / 1e6
    print(f"  Done.  {total_mb:.0f} MB")

    # Free GPU memory before next merge
    del merged, peft_model, base_model
    torch.cuda.empty_cache()

print()
print("=" * 60)
print("  All merges complete.")
print("  model_output_v3/merged        → dhl_app.py + eval (ours)")
print("  model_output_v3/ck2000_merged → eval (ours_ck2000)")
print("  model_output_v3/ck2250_merged → eval (ours_ck2250)")
print("=" * 60)
