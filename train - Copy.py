"""
DHL Document Fine-tuning Training Script
Model  : Qwen3-VL-4B-Instruct  (DocVQA 94.9 — better than Qwen2.5-VL-3B's 93.9)
Method : QLoRA (4-bit) on 16 GB VRAM (RTX 5080) OR LoRA (16-bit) on 20+ GB
Library: Unsloth (2x faster training, 60% less VRAM than HuggingFace vanilla)

Hardware: RTX 5080 16 GB GDDR7
  → Auto-selects QLoRA. Effective batch = 1 × 16 = 16.
  → Estimated training time: ~45-60 min for 3 epochs on 30K examples.

Run:
    python train.py                      # auto-detects VRAM, picks LoRA or QLoRA
    python train.py --method qlora       # force 4-bit QLoRA (RTX 5080 / 16 GB)
    python train.py --method lora        # force 16-bit LoRA (A100 / 24+ GB)
    python train.py --epochs 1 --debug   # quick smoke test (100 samples)

Model choice rationale (Qwen3-VL-4B vs Qwen2.5-VL-3B):
    Qwen3-VL-4B  DocVQA=94.9  TextVQA=81.8  — better document understanding
    Qwen2.5-VL-3B DocVQA=93.9  TextVQA=84.9  — better text reading
    Winner for our task: Qwen3-VL-4B (DocVQA is more representative of invoice/BL forms)
    Fallback: change MODEL_NAME below to 'Qwen/Qwen2.5-VL-3B-Instruct'
"""

import os, json, argparse, random

# torch 2.7 + triton 3.6 on Windows: inductor backend has multiple breaking changes
# (triton_key removed, launch_enter_hook removed, etc.). Disable compile entirely —
# Unsloth's QLoRA CUDA kernels still run at full speed without it.
# Speed gap is recovered by xformers attention (install: pip install xformers).
os.environ["TORCHDYNAMO_DISABLE"] = "1"
from pathlib import Path
from PIL import Image
from dataclasses import dataclass, field

# ── Load YAML config ───────────────────────────────────────────────────────
def load_config(config_path: Path) -> dict:
    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        print("WARNING: pyyaml not installed. Run: pip install pyyaml")
        print("Falling back to defaults in TrainingConfig.")
        return {}
    except FileNotFoundError:
        print(f"WARNING: {config_path} not found. Using defaults.")
        return {}

BASE_DIR    = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "train_config.yaml"
CFG         = load_config(CONFIG_PATH)

def cfg_get(keys: str, default):
    """Dot-path lookup into CFG dict, e.g. 'lora.r' → CFG['lora']['r']"""
    obj = CFG
    for k in keys.split("."):
        if not isinstance(obj, dict) or k not in obj:
            return default
        obj = obj[k]
    return obj

# ── Paths (from config or defaults) ───────────────────────────────────────
TRAIN_DATA = BASE_DIR / cfg_get("paths.train_data", "Training_Data/train.jsonl")
VAL_DATA   = BASE_DIR / cfg_get("paths.val_data",   "Training_Data/val.jsonl")
IMG_DIR    = BASE_DIR / cfg_get("paths.image_base",  "Training_Data")
OUTPUT_DIR = BASE_DIR / cfg_get("paths.output_dir",  "model_output")

MODEL_NAME = cfg_get("model.name", "Qwen/Qwen3-VL-4B-Instruct")
# Override in train_config.yaml → model.name
# Fallback: "Qwen/Qwen2.5-VL-3B-Instruct" (3B, slightly better TextVQA, less VRAM)

# ── Check GPU memory to auto-select LoRA vs QLoRA ─────────────────────────
def get_gpu_vram_gb():
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory / 1e9
    except: pass
    return 0.0

# ═══════════════════════════════════════════════════════════════════════════
# HYPERPARAMETERS — with explanation for every single one
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class TrainingConfig:

    # ── LoRA architecture ─────────────────────────────────────────────────

    # All defaults read from train_config.yaml via cfg_get().
    # Change any value in the YAML — no need to edit this file.

    # ── LoRA ──────────────────────────────────────────────────────────────────
    lora_r:       int   = field(default_factory=lambda: cfg_get("lora.r",       32))
    lora_alpha:   int   = field(default_factory=lambda: cfg_get("lora.alpha",   32))
    lora_dropout: float = field(default_factory=lambda: cfg_get("lora.dropout", 0.0))
    target_modules: list = field(default_factory=lambda:
        cfg_get("lora.target_modules",
                ["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"]))

    # ── Training schedule ─────────────────────────────────────────────────────
    num_train_epochs:    int   = field(default_factory=lambda: cfg_get("training.num_train_epochs",    1))
    learning_rate:       float = field(default_factory=lambda: cfg_get("training.learning_rate",       2e-4))
    warmup_ratio:        float = field(default_factory=lambda: cfg_get("training.warmup_ratio",        0.03))
    lr_scheduler_type:   str   = field(default_factory=lambda: cfg_get("training.lr_scheduler_type",   "cosine"))
    max_seq_length:      int   = field(default_factory=lambda: cfg_get("training.max_seq_length",      2048))

    # ── Batch & memory ────────────────────────────────────────────────────────
    per_device_train_batch_size: int = field(default_factory=lambda: cfg_get("batch.per_device_train_batch_size", 1))
    gradient_accumulation_steps: int = field(default_factory=lambda: cfg_get("batch.gradient_accumulation_steps", 16))
    dataloader_num_workers:      int = field(default_factory=lambda: cfg_get("batch.dataloader_num_workers",       0))

    # ── Logging & checkpointing ───────────────────────────────────────────────
    output_dir:       str  = field(default_factory=lambda: str(BASE_DIR / cfg_get("paths.output_dir", "model_output")))
    logging_steps:    int  = field(default_factory=lambda: cfg_get("logging.logging_steps",    50))
    eval_steps:       int  = field(default_factory=lambda: cfg_get("logging.eval_steps",       500))
    save_steps:       int  = field(default_factory=lambda: cfg_get("logging.save_steps",       500))
    save_total_limit: int  = field(default_factory=lambda: cfg_get("logging.save_total_limit", 5))

    # ── Precision & tracking ──────────────────────────────────────────────────
    bf16:      bool = field(default_factory=lambda: cfg_get("precision.bf16",     True))
    fp16:      bool = field(default_factory=lambda: cfg_get("precision.fp16",     False))
    report_to: str  = field(default_factory=lambda: cfg_get("tracking.report_to", "none"))


# ═══════════════════════════════════════════════════════════════════════════
# DATASET LOADING
# ═══════════════════════════════════════════════════════════════════════════

def load_jsonl(path: Path) -> list[dict]:
    examples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            examples.append(json.loads(line.strip()))
    return examples

def _is_continuation(example: dict) -> bool:
    """Works with both label formats: 'Class | CONTINUATION' and JSON."""
    label = example.get("label", "")
    if label.startswith("{"):
        try:
            import json as _json
            return _json.loads(label).get("position") == "CONTINUATION"
        except Exception:
            return False
    return "| CONTINUATION" in label


def balance_continuation(examples: list[dict], oversample_factor: int = 2) -> list[dict]:
    """
    Dataset is 72%/28% START/CONTINUATION.
    Oversample CONTINUATION by 2x to bring it to ~44% during training.
    Supports both v1 ('Class | START') and v2 (JSON) label formats.

    Factor guide:
      1 = no oversampling (use natural 28% distribution)
      2 = mild boost -> ~44% CONTINUATION  (our choice)
      3 = aggressive -> ~54% CONTINUATION
    """
    starts = [e for e in examples if not _is_continuation(e)]
    conts  = [e for e in examples if _is_continuation(e)]
    print(f"  Before balance: {len(starts)} START, {len(conts)} CONTINUATION")
    oversampled = conts * oversample_factor
    balanced    = starts + oversampled
    random.shuffle(balanced)
    conts2 = [e for e in balanced if _is_continuation(e)]
    print(f"  After balance:  {len(balanced)-len(conts2)} START, {len(conts2)} CONTINUATION ({100*len(conts2)/len(balanced):.0f}%)")
    return balanced

def prepare_conversation(example: dict, img_base: Path):
    """
    Stores image path + prompt text + label as plain strings.
    PIL images are NOT loaded here — loaded in VLMCollator at batch time.
    """
    img_path = img_base / example["image"]
    if not img_path.exists():
        print(f"  WARNING: image not found: {img_path}")
        return None
    return {
        "image_path": str(img_path),
        "prompt":     example["messages"][0]["content"][1]["text"],
        "label":      example["label"],
    }


class VLMDataset:
    """Minimal torch-compatible dataset. Bypasses PyArrow/HuggingFace serialization."""
    def __init__(self, records): self.records = records
    def __len__(self):           return len(self.records)
    def __getitem__(self, i):    return self.records[i]


class VLMCollator:
    """
    Top-level picklable collator — required for DataLoader workers.
    Loads images from disk, resizes to cap image token count, tokenizes, pads.

    Why resize instead of truncate:
      A4 at 150 DPI = 1241×1754 px → ~2835 image tokens alone (Qwen2.5-VL uses
      one token per 28×28 px block). Truncation then cuts image tokens mid-way,
      causing a "Mismatch in image token count" error. Resizing before processing
      keeps the image intact and within max_seq_length.
    """
    def __init__(self, processor, max_seq_length: int, max_pixels: int = 1_000_000):
        self.processor      = processor
        self.max_seq_length = max_seq_length
        self.max_pixels     = max_pixels   # default ~1000×1000 → ~1300 image tokens

    def _resize(self, image: Image.Image) -> Image.Image:
        w, h = image.size
        if w * h > self.max_pixels:
            scale = (self.max_pixels / (w * h)) ** 0.5
            image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        return image

    def __call__(self, examples):
        texts  = []
        images = []
        for ex in examples:
            img = Image.open(ex["image_path"]).convert("RGB")
            images.append(self._resize(img))
            messages = [
                {"role": "user", "content": [
                    {"type": "image"},
                    {"type": "text", "text": ex["prompt"]},
                ]},
                {"role": "assistant", "content": ex["label"]},
            ]
            texts.append(self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False,
            ))

        # No truncation — image size is controlled by _resize() above
        batch = self.processor(
            text=texts, images=images,
            return_tensors="pt", padding=True,
        )

        # Mask everything except the assistant's answer tokens.
        import torch
        labels = batch["input_ids"].clone()
        labels[:] = -100

        # Encode the assistant turn header once (cached after first call)
        if not hasattr(self, "_asst_tokens"):
            self._asst_tokens = self.processor.tokenizer.encode(
                "<|im_start|>assistant\n", add_special_tokens=False
            )
            self._asst_t   = torch.tensor(self._asst_tokens)
            self._asst_len = len(self._asst_tokens)

        asst_t   = self._asst_t
        asst_len = self._asst_len
        found_count = 0

        for i, row in enumerate(batch["input_ids"]):
            asst_start = None
            for pos in range(len(row) - asst_len):
                if torch.equal(row[pos : pos + asst_len], asst_t):
                    asst_start = pos + asst_len
                    break
            if asst_start is not None:
                found_count += 1
                end = len(row)
                while end > asst_start and row[end - 1] == self.processor.tokenizer.pad_token_id:
                    end -= 1
                labels[i, asst_start:end] = batch["input_ids"][i, asst_start:end]

        # ── One-time debug: printed for the very first batch only ─────────────
        if not hasattr(self, "_debug_printed"):
            self._debug_printed = True
            n_unmasked = (labels != -100).sum().item()
            total      = labels.numel()
            print(f"\n{'='*55}")
            print(f"LABEL MASK DEBUG (first batch only)")
            print(f"  Batch size        : {len(examples)}")
            print(f"  Assistant headers : {found_count}/{len(examples)} found")
            print(f"  Tokens unmasked   : {n_unmasked}/{total} ({100*n_unmasked/total:.2f}%)")
            for i in range(min(len(examples), 3)):
                ids = labels[i][labels[i] != -100]
                if len(ids) > 0:
                    decoded = self.processor.tokenizer.decode(ids.tolist())
                    print(f"  Example {i} ({len(ids)} tokens): '{decoded}'")
                else:
                    print(f"  Example {i}: 0 unmasked — HEADER NOT FOUND (search failed!)")
            print(f"  Encoded header tokens: {self._asst_tokens}")
            print(f"{'='*55}\n")

        batch["labels"] = labels
        return batch


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TRAINING FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

def train(method: str = "auto", debug: bool = False, epochs: int = None, config_path: str = None):
    # If a different config file was passed via CLI, reload CFG before TrainingConfig is used
    if config_path:
        global CFG
        CFG = load_config(Path(config_path))
        print(f"Loaded config: {config_path}")
    from unsloth import FastVisionModel, is_bf16_supported
    from transformers import Trainer, TrainingArguments
    import torch

    # ── Step 1: Decide LoRA vs QLoRA ──────────────────────────────────────
    vram = get_gpu_vram_gb()
    # CLI --method overrides YAML model.method
    if method == "auto":
        method = cfg_get("model.method", "auto")
    if method == "auto":
        # 4B model in 16-bit LoRA needs ~20 GB — require 20 GB threshold.
        # RTX 5080 (16 GB) → QLoRA. A100/RTX 4090 24GB+ → LoRA.
        method = "lora" if vram >= 20.0 else "qlora"
        print(f"Auto-selected: {method.upper()} (detected {vram:.1f} GB VRAM)")
    else:
        print(f"Using: {method.upper()} (forced)")

    load_in_4bit = (method == "qlora")
    # LoRA:  base model in 16-bit + LoRA adapters — best quality, needs 20+ GB
    # QLoRA: base model in 4-bit  + LoRA adapters — saves ~8 GB VRAM, tiny quality trade-off
    # RTX 5080 16 GB → always QLoRA unless overridden with --method lora

    # ── Step 2: Load model ─────────────────────────────────────────────────
    print(f"\nLoading {MODEL_NAME} ({'4-bit QLoRA' if load_in_4bit else '16-bit LoRA'})...")
    model, processor = FastVisionModel.from_pretrained(
        MODEL_NAME,
        load_in_4bit=load_in_4bit,
        # max_seq_length is set here so the model prepares KV cache correctly
    )
    print("Model loaded.")

    # ── Step 3: Apply LoRA adapters ────────────────────────────────────────
    cfg = TrainingConfig()
    if epochs: cfg.num_train_epochs = epochs

    print(f"\nApplying LoRA (r={cfg.lora_r}, alpha={cfg.lora_alpha}, dropout={cfg.lora_dropout})...")
    model = FastVisionModel.get_peft_model(
        model,
        r               = cfg.lora_r,
        target_modules  = cfg.target_modules,
        lora_alpha      = cfg.lora_alpha,
        lora_dropout    = cfg.lora_dropout,
        bias            = "none",
        # use_gradient_checkpointing: unsloth's version is smarter than standard.
        # It recomputes activations during backward pass to save memory.
        # Trades slightly more compute for significantly less VRAM.
        use_gradient_checkpointing = "unsloth",
        random_state    = 42,
        use_rslora      = False,   # RSLoRA scales alpha differently; False = standard
    )
    model.print_trainable_parameters()
    # Expected output: ~0.1-0.5% of parameters are trainable

    # ── Step 4: Load datasets ──────────────────────────────────────────────
    print("\nLoading datasets...")
    train_raw = load_jsonl(TRAIN_DATA)
    val_raw   = load_jsonl(VAL_DATA)

    if debug:
        # Quick smoke test: use only 100 training + 20 val examples
        train_raw = random.sample(train_raw, 100)
        val_raw   = random.sample(val_raw, 20)
        cfg.num_train_epochs = 1
        cfg.eval_steps  = 50
        cfg.save_steps  = 50
        cfg.logging_steps = 10
        print("  DEBUG MODE: using 100 train + 20 val examples")

    # Balance CONTINUATION vs START — factor from YAML dataset.continuation_oversample_factor
    oversample = cfg_get("dataset.continuation_oversample_factor", 2)
    train_raw = balance_continuation(train_raw, oversample_factor=oversample)

    # Convert to conversation format
    print("Converting to conversation format...")
    train_data, val_data = [], []
    for ex in train_raw:
        conv = prepare_conversation(ex, IMG_DIR)
        if conv: train_data.append(conv)
    for ex in val_raw:
        conv = prepare_conversation(ex, IMG_DIR)
        if conv: val_data.append(conv)
    print(f"  Train: {len(train_data):,} examples")
    print(f"  Val:   {len(val_data):,} examples")

    # ── Step 5: Collator — instantiated here with processor & image size cap ──
    max_pixels = cfg_get("batch.max_pixels", 1_000_000)
    collator = VLMCollator(processor, cfg.max_seq_length, max_pixels=max_pixels)

    # ── Step 6: Training configuration ────────────────────────────────────
    # Uses standard TrainingArguments + Trainer (not SFTTrainer).
    # Reason: Unsloth's SFTTrainer wraps the training loop via _unsloth_get_batch_samples
    # which intercepts items BEFORE the collate_fn, then applies the default Transformers
    # collator — completely bypassing any custom data_collator we pass.
    # Standard Trainer passes data_collator directly to the DataLoader — guaranteed to work.
    print("\nSetting up training configuration...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Compute step counts for eval/save scheduling
    effective_batch  = cfg.per_device_train_batch_size * cfg.gradient_accumulation_steps
    steps_per_epoch  = len(train_data) // effective_batch
    half_epoch_steps = max(1, steps_per_epoch // 2)
    total_steps_calc = steps_per_epoch * cfg.num_train_epochs
    warmup_steps_val = max(1, int(cfg.warmup_ratio * total_steps_calc))

    # Eval and save at half-epoch and end-of-epoch boundaries.
    # With eval_steps = half_epoch_steps the Trainer fires at:
    #   step half_epoch_steps  → 50% of epoch 1
    #   step steps_per_epoch   → 100% of epoch 1  (end of epoch)
    #   (repeats for each additional epoch if num_epochs > 1)
    print(f"  Steps per epoch  : {steps_per_epoch}")
    print(f"  Eval/save at     : step {half_epoch_steps} (50%) and {steps_per_epoch} (100%)")

    training_args = TrainingArguments(
        output_dir                  = cfg.output_dir,
        num_train_epochs            = cfg.num_train_epochs,
        per_device_train_batch_size = cfg.per_device_train_batch_size,
        gradient_accumulation_steps = cfg.gradient_accumulation_steps,

        learning_rate               = cfg.learning_rate,
        lr_scheduler_type           = cfg.lr_scheduler_type,
        warmup_steps                = warmup_steps_val,

        bf16                        = cfg.bf16 and is_bf16_supported(),
        fp16                        = cfg.fp16 and not is_bf16_supported(),

        logging_steps               = cfg.logging_steps,
        eval_strategy               = "steps",
        eval_steps                  = half_epoch_steps,   # fires at 50% and 100% of each epoch
        save_strategy               = "steps",
        save_steps                  = half_epoch_steps,   # checkpoint saved at same points
        save_total_limit            = cfg.save_total_limit,

        load_best_model_at_end      = False,

        dataloader_num_workers      = 0,     # 0 = main process only (no multiprocessing)
        dataloader_pin_memory       = False, # Unsloth patches Qwen2_5_VLProcessor at runtime,
        # making it unpicklable — any num_workers > 0 fails on Windows with a PicklingError.
        remove_unused_columns       = False,
        report_to                   = cfg.report_to,
        seed                        = 42,
    )

    # ── Step 7: Create trainer ─────────────────────────────────────────────
    train_dataset = VLMDataset(train_data)
    val_dataset   = VLMDataset(val_data)

    trainer = Trainer(
        model              = model,
        processing_class   = processor,   # replaces deprecated tokenizer= param
        args               = training_args,
        train_dataset      = train_dataset,
        eval_dataset       = val_dataset,
        data_collator      = collator,    # VLMCollator — top-level class, fully picklable
    )

    # ── Step 8: Print summary before training ─────────────────────────────
    print(f"\n{'='*60}")
    print("TRAINING SUMMARY")
    print(f"{'='*60}")
    print(f"  Model            : {MODEL_NAME}")
    print(f"  Method           : {'QLoRA (4-bit)' if load_in_4bit else 'LoRA (16-bit)'}")
    print(f"  LoRA rank        : r={cfg.lora_r}  alpha={cfg.lora_alpha}  scale={cfg.lora_alpha/cfg.lora_r:.1f}  dropout={cfg.lora_dropout}")
    print(f"  Train examples   : {len(train_data):,}")
    print(f"  Val examples     : {len(val_data):,}")
    print(f"  Epochs           : {cfg.num_train_epochs}")
    print(f"  Batch size       : {cfg.per_device_train_batch_size} × {cfg.gradient_accumulation_steps} accum = {effective_batch} effective")
    print(f"  Steps per epoch  : {steps_per_epoch:,}")
    print(f"  Total steps      : {total_steps_calc:,}")
    print(f"  Learning rate    : {cfg.learning_rate} ({cfg.lr_scheduler_type} schedule)")
    print(f"  Warmup steps     : {warmup_steps_val} ({cfg.warmup_ratio:.0%} of total)")
    print(f"  Eval / save at   : step {half_epoch_steps} (50%) and {steps_per_epoch} (end of epoch)")
    print(f"  Output dir       : {cfg.output_dir}")
    print(f"{'='*60}\n")

    # ── Step 9: TRAIN ─────────────────────────────────────────────────────
    print("Starting training...")
    trainer.train()

    # ── Step 10: Save final model ──────────────────────────────────────────
    print("\nSaving final model and LoRA adapters...")
    final_dir = OUTPUT_DIR / "final"
    final_dir.mkdir(exist_ok=True)

    # Save LoRA adapters only (small — only the ~74M trained parameters)
    # This is all that's needed for inference — load base model + apply these adapters
    model.save_pretrained(str(final_dir))
    processor.save_pretrained(str(final_dir))
    print(f"  LoRA adapters saved to: {final_dir}")
    # NOTE: merged model save (save_pretrained_merged) is skipped intentionally.
    # It can fail when base model was loaded from a local path. Use evaluate_baseline.py
    # with --finetuned flag instead — it loads base + adapters correctly.

    # ── Step 11: Quick evaluation ──────────────────────────────────────────
    print("\nRunning quick evaluation on val set (first 50 examples)...")
    model.eval()
    FastVisionModel.for_inference(model)

    import torch, json as _json
    correct = 0; cls_correct = {}; cls_total = {}
    pos_correct = {"START": 0, "CONTINUATION": 0}
    pos_total   = {"START": 0, "CONTINUATION": 0}
    field_keys  = ["shipper_name","consignee_name","document_date","document_number",
                   "country_of_origin","country_of_destination","description_of_goods","gross_weight_kg",
                   "license_number","validity_start","validity_end","licensee_name"]
    field_hits  = {k: 0 for k in field_keys}
    field_seen  = {k: 0 for k in field_keys}
    total = 0

    # v2 labels are JSON — need 200 tokens; v1 labels need only 30
    first_label = val_data[0]["label"] if val_data else ""
    max_new_tok = 200 if first_label.startswith("{") else 30

    for ex in val_data[:50]:
        true_label = ex["label"]
        image = Image.open(ex["image_path"]).convert("RGB")
        image = collator._resize(image)

        messages_for_gen = [{"role": "user", "content": [
            {"type": "image"}, {"type": "text", "text": ex["prompt"]},
        ]}]
        text   = processor.apply_chat_template(messages_for_gen, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[image], return_tensors="pt").to("cuda")

        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=max_new_tok, do_sample=False)
        pred = processor.decode(outputs[0], skip_special_tokens=True).strip()
        pred = pred.split("assistant")[-1].strip() if "assistant" in pred else pred
        pred = pred.replace("<|im_end|>", "").strip()

        total += 1

        # Parse both true and predicted labels (handles v1 string and v2 JSON)
        def parse_label(lbl):
            if lbl.startswith("{"):
                try:
                    obj = _json.loads(lbl)
                    return obj.get("class"), obj.get("position"), obj
                except Exception:
                    return None, None, {}
            if " | " in lbl:
                c, p = lbl.split(" | ", 1)
                return c.strip(), p.strip(), {}
            return None, None, {}

        true_cls, true_pos, true_obj = parse_label(true_label)
        pred_cls, pred_pos, pred_obj = parse_label(pred)

        # Exact match (class + position both correct)
        if true_cls == pred_cls and true_pos == pred_pos:
            correct += 1

        if true_cls:
            cls_total[true_cls]   = cls_total.get(true_cls, 0) + 1
            cls_correct[true_cls] = cls_correct.get(true_cls, 0) + (pred_cls == true_cls)

        if true_pos in pos_total:
            pos_total[true_pos]   += 1
            pos_correct[true_pos] += (pred_pos == true_pos)

        # Field extraction accuracy (v2 only, START pages)
        if true_pos == "START" and true_obj:
            for k in field_keys:
                tv = true_obj.get(k)
                if tv is None:
                    continue
                field_seen[k] += 1
                pv = pred_obj.get(k, "")
                # Partial match: predicted value contains the true value substring
                if pv and str(tv).lower()[:20] in str(pv).lower():
                    field_hits[k] += 1

    print(f"\n  Quick eval (50 examples):")
    print(f"  Exact match (class+position): {correct}/{total} = {100*correct/max(total,1):.0f}%")
    print(f"  START accuracy     : {pos_correct['START']}/{pos_total['START']} = "
          f"{100*pos_correct['START']//max(pos_total['START'],1)}%")
    print(f"  CONTINUATION accur.: {pos_correct['CONTINUATION']}/{pos_total['CONTINUATION']} = "
          f"{100*pos_correct['CONTINUATION']//max(pos_total['CONTINUATION'],1)}%")
    print(f"\n  Per-class accuracy:")
    for c in sorted(cls_total):
        ok = cls_correct.get(c,0); t = cls_total[c]
        print(f"    {c:<42} {ok}/{t} = {100*ok//max(t,1)}%")

    if any(field_seen[k] > 0 for k in field_keys):
        print(f"\n  Field extraction accuracy (partial match, START pages):")
        for k in field_keys:
            s = field_seen[k]
            if s == 0: continue
            h = field_hits[k]
            print(f"    {k:<28} {h}/{s} = {100*h//s}%")

    print("\nTraining complete.")


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Fine-tune Qwen VLM on DHL documents (config-driven)")
    p.add_argument("--config",  default=None,
                   help="Path to YAML config (default: train_config.yaml next to this script)")
    p.add_argument("--method",  choices=["auto","lora","qlora"], default="auto",
                   help="Override model.method in config: auto/lora/qlora")
    p.add_argument("--epochs",  type=int, default=None,
                   help="Override training.num_train_epochs in config")
    p.add_argument("--debug",   action="store_true",
                   help="Smoke test: 100 examples, 1 epoch")
    args = p.parse_args()
    train(method=args.method, debug=args.debug, epochs=args.epochs, config_path=args.config)
