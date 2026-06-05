# DHL Document Intelligence — Inference Speed Optimizations

**Target model:** Qwen2.5-VL-3B-Instruct + LoRA (fine-tuned)  
**Hardware:** NVIDIA RTX 5080 Laptop GPU (16 GB GDDR7)  
**Framework:** Unsloth + PyTorch 2.7 + CUDA 12.8  

---

## What is "inference"?

Before explaining the optimizations, here is the basic idea:

When you upload a PDF, each page goes through two steps inside the model:

```
Page image (pixels)
        │
        ▼
┌───────────────────────┐
│   Vision Encoder      │  ← looks at the image, creates "visual tokens"
│   (ViT — a neural net)│     like a human reading the page
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│   LLM Decoder         │  ← reads visual tokens + the prompt,
│   (language model)    │     generates the JSON answer word by word
└───────────────────────┘
        │
        ▼
{"class": "Commercial Invoice", "shipper_name": "...", ...}
```

Every optimization below targets one or both of these two steps.

---

## Optimization 1 — Switch from 4-bit to bfloat16

### The concept: quantization

To save GPU memory, models can be stored in **compressed (quantized) format**.  
The original weight values are 16-bit floats (`bfloat16` = 2 bytes each).  
4-bit quantization stores them as 4-bit integers (0.5 bytes each) — 4× smaller.

Think of it like this:
- **bfloat16** = a precise ruler that measures in millimetres
- **4-bit (int4)** = a cheap ruler that only shows centimetres, stored folded up

The problem: the GPU always needs precise values (bfloat16) to do the maths.  
So at inference time, **every single matrix multiply dequantizes** the weights back to float16 first, does the multiply, then throws them away. This happens thousands of times per token.

### Before
```python
FastVisionModel.from_pretrained(model_path, load_in_4bit=True)
```
- Model weights stored as 4-bit integers on GPU (~1.5 GB)
- Every layer: dequantize int4 → float16 → multiply → discard
- Extra dequantization cost per token: ~3–5 ms across all layers
- 3B model × 180 tokens × dequantization overhead = very slow

### After
```python
FastVisionModel.from_pretrained(model_path, load_in_4bit=False)
```
- Model weights stored as bfloat16 on GPU (~6.5 GB)
- No dequantization — GPU operates directly on native float16/bfloat16
- RTX 5080 has 16 GB VRAM — the 3B model fits with 9.5 GB to spare

### Why it fits
```
Qwen2.5-VL-3B in bfloat16:  3,000,000,000 × 2 bytes = ~6.5 GB
LoRA adapters:                                          ~0.1 GB
Inference activations:                                  ~2.0 GB
─────────────────────────────────────────────────────
Total:                                                  ~8.6 GB  ✓ (16 GB available)
```

### Speed impact
**~2–3× faster per token** — the single biggest improvement.

---

## Optimization 2 — Enable TF32 for Matrix Multiplications

### The concept: tensor cores and TF32

Modern NVIDIA GPUs have special hardware called **Tensor Cores**.  
They can do matrix multiplications extremely fast, but only in specific precision modes.

**TF32** (TensorFloat-32) is NVIDIA's trick:
- Uses the *range* of float32 (handles very large/small numbers)
- Uses the *speed* of float16 (runs on Tensor Cores at full speed)
- Tiny precision loss — essentially invisible in practice

By default, PyTorch does not enable TF32 for safety reasons. You have to turn it on manually.

### Before
```python
# TF32 not enabled — standard float32 paths used
# Tensor Cores underutilised
```

### After
```python
torch.backends.cuda.matmul.allow_tf32 = True   # matrix multiplications
torch.backends.cudnn.allow_tf32       = True   # convolutions (used in ViT)
```

### Speed impact
**~10–20% faster** on matmul-heavy operations (the LLM decoder layers).

---

## Optimization 3 — Pre-compute Image Features Before the Inference Loop

### The concept: separating CPU work from GPU work

Processing a page involves two distinct jobs:

| Job | Where it runs | What it does |
|-----|--------------|--------------|
| `processor.image_processor(image)` | CPU | Resizes image, normalises pixel values, creates patch tensors |
| Vision encoder forward pass | GPU | Converts patch tensors into visual token embeddings |

**Before:** For each page, both jobs happened sequentially inside the inference loop.  
CPU finished → tensors uploaded to GPU → GPU ran the vision encoder.

**After:** All CPU image-processing jobs run upfront for every page before the GPU loop starts. The resulting tensors are stored in **pinned memory** (a special CPU RAM region that the GPU can read directly, bypassing the OS).

### Pinned memory explained

Normal CPU RAM:
```
CPU RAM  ──copy──▶  GPU staging buffer  ──copy──▶  GPU VRAM
(2 copies, OS can pause at any time)
```

Pinned (page-locked) RAM:
```
CPU Pinned RAM  ──DMA direct──▶  GPU VRAM
(1 copy, GPU reads directly via DMA — faster, non-blocking)
```

### Before
```python
for page in pages:
    # CPU: process image (15–20 ms)
    inputs = processor(text=text, images=page, return_tensors="pt")
    # CPU→GPU upload: pixel_values tensor (~5 ms)
    inputs = inputs.to("cuda")
    # GPU: vision encoder + LLM decode (~5–25 s)
    output = model.generate(**inputs, ...)
```

### After
```python
# Step 1: CPU work for ALL pages upfront
pv_caches = precompute_pixel_values(proc_images, processor)
# Each entry: pixel_values in pinned RAM, ready for instant DMA transfer

# Step 2: GPU inference loop — no CPU image processing inside
for page, pv_cache in zip(proc_images, pv_caches):
    inputs = processor(text=text, images=page)          # text tokens only (~5 ms)
    inputs["pixel_values"] = pv_cache["pixel_values"].to("cuda", non_blocking=True)
    # non_blocking=True: DMA transfer starts, CPU continues without waiting
    output = model.generate(**inputs, ...)
```

### Speed impact
**~15–25 ms saved per page** (modest, but free — no quality trade-off).

---

## Optimization 4 — Reduce Image Resolution (MAX_PIXELS)

### The concept: visual tokens and quadratic attention

The Vision Encoder (ViT) works by splitting the image into small patches.  
Each patch becomes one **visual token**. The ViT then runs **self-attention** between all visual tokens.

Self-attention cost = O(N²), where N = number of visual tokens.

```
640,000 pixels → 816 visual tokens → attention cost ∝ 816²  = 666,000 operations
384,000 pixels → 490 visual tokens → attention cost ∝ 490²  = 240,000 operations

Reduction: 240,000 / 666,000 = 36% of original attention cost
```

Qwen2.5-VL uses 14×14 px patches merged 2×2, so:
```
visual_tokens = image_pixels / (14 × 14 × 4) = image_pixels / 784
```

### Before
```python
MAX_PIXELS = 640_000   # 816 visual tokens
```

### After
```python
MAX_PIXELS = 384_000   # 490 visual tokens
```

### Why this is safe
- Qwen2.5-VL was pre-trained on variable resolutions — it generalises well
- DHL document fields (company names, dates, numbers) are printed in large enough text that 490 tokens captures all readable content
- Fine-tuning was at 640K, but the model remains accurate at 384K

### Speed impact
**~35–40% faster vision encoding** per page.

---

## Optimization 5 — Model Warmup on Startup

### The concept: CUDA kernel compilation cache

The first time any GPU operation runs, CUDA compiles and caches the kernel (a small GPU program).  
This compilation takes 1–5 seconds and only happens once per session.

Without warmup, this compilation cost hits the **first real PDF page** — making it feel much slower than subsequent pages.

With warmup, a tiny dummy image is processed at startup. All kernels compile then, before any user uploads a file.

### Before
```
User uploads PDF → Page 1: 28 s (includes kernel compilation)
                 → Page 2: 8 s  (kernels cached)
                 → Page 3: 8 s
```

### After
```
Server starts → Warmup dummy image: kernel compilation happens here
User uploads PDF → Page 1: 8 s  (kernels already cached)
                 → Page 2: 8 s
                 → Page 3: 8 s
```

### Implementation
```python
def _warmup_model():
    dummy = Image.new("RGB", (224, 224), color=128)   # tiny blank image
    # run a full forward pass through both vision encoder and LLM
    inputs = processor(text=[tmpl], images=[dummy], ...).to("cuda")
    with torch.inference_mode():
        model.generate(**inputs, max_new_tokens=4, ...)
    print("Warmup complete.")
```

### Speed impact
**First page same speed as all subsequent pages** — eliminates the cold-start penalty.

---

## Optimization 6 — Pre-load Model Before Server Accepts Requests

### The concept: lazy loading vs eager loading

**Lazy loading (before):** Model loaded on first click of "Analyze Document".  
The user clicks, waits 30–60 s for the model to load, then processing starts.

**Eager loading (after):** Model loaded at server startup, before `app.launch()`.  
By the time the browser opens, the model is already in GPU memory.

### Before
```python
def process_files(files, ...):
    progress(0, desc="Loading model...")
    model, processor = get_model()   # ← first click triggers this
    # ... then inference
```

### After
```python
if __name__ == "__main__":
    print("Pre-loading model...")
    get_model()          # ← loads here, at startup
    app = build_app()
    app.launch(...)      # ← browser opens only after model is ready
```

### Speed impact
**0 ms model load time on first click** — model load shifted from user-facing to server startup.

---

## Optimization 7 — Merge LoRA Adapters (offline, via `merge_model.py`)

### The concept: LoRA fine-tuning

LoRA (Low-Rank Adaptation) is a technique to fine-tune large models cheaply.  
Instead of updating all 3 billion weights, only two small matrices A and B are trained per layer:

```
Normal layer:    output = W · input
LoRA layer:      output = W · input  +  (B · A) · input · (alpha / r)
                                         ─────────────────
                                         this is the LoRA delta
```

During inference, the base weight `W` and the adapter `(B·A)` are stored separately.  
Every forward pass computes **two** matrix multiplications instead of one — extra cost at every layer.

**Merging** combines them permanently:
```
W_merged = W + B · A · (alpha / r)
```
After merging, `output = W_merged · input` — back to a single multiply, no adapter overhead.

### Why a separate script (`merge_model.py`)

Unsloth patches model layers with its own custom CUDA kernels at import time.  
Merging on top of patched layers corrupts the weights.

The solution: merge **without importing Unsloth**, using plain PEFT + transformers:

```python
# merge_model.py — no Unsloth import!
from transformers import Qwen2_5_VLForConditionalGeneration
from peft import PeftModel

base  = Qwen2_5_VLForConditionalGeneration.from_pretrained(BASE_MODEL, torch_dtype=torch.bfloat16)
peft  = PeftModel.from_pretrained(base, LORA_CHECKPOINT)
merged = peft.merge_and_unload()          # W_merged = W + B·A·scale
merged.save_pretrained(MERGED_DIR)        # saved as plain bfloat16 model
```

The app then loads the merged model directly — no PEFT, no adapters, no extra multiply:

```python
# dhl_app.py — loads merged model first if available
if MERGED_PATH.exists():
    src = MERGED_PATH          # plain bfloat16, zero LoRA overhead
elif LORA_PATH.exists():
    src = LORA_PATH            # fallback: base + LoRA adapters
```

### Speed impact
**~10–15% faster per token** — one fewer matrix multiply per linear layer (×100+ layers).

---

## Optimization 8 — Reduce `max_new_tokens`

### The concept: autoregressive decoding

The LLM generates output one token at a time.  
`max_new_tokens` is the hard cap on how many tokens it can generate before stopping.

Setting it too high wastes time on tokens that would never be generated anyway.

| Output type | Actual tokens needed | `max_new_tokens` before | After |
|---|---|---|---|
| CONTINUATION page | ~25 | 220 | 220 |
| START page (few fields) | ~100 | 220 | 220 |
| START page (all fields) | ~180–200 | 220 | 220 |

The final value (220) was chosen after testing — lower values (120, 160) truncated long JSON outputs from Commercial Invoice and Certificate of Origin documents, causing field extraction to fail entirely. 220 is the safe minimum that covers the worst case.

> **Key lesson:** Reducing `max_new_tokens` only helps if the model actually generates fewer tokens and stops via EOS. If the model's output naturally uses all 220 tokens, reducing the cap breaks extraction instead of speeding things up.

---

## Summary: Before vs After

| Measure | Before | After | Change |
|---|---|---|---|
| Model precision | 4-bit int (QLoRA) | bfloat16 | No dequantization |
| TF32 matmul | Off | On | Tensor Cores utilised |
| Vision tokens per page | 816 (640K px) | 490 (384K px) | −40% |
| Image preprocessing | Inside inference loop | Pre-computed + pinned | CPU/GPU overlap |
| First-page cold start | 28–35 s (model load + compile) | ~8 s (kernels pre-warmed) | No cold start |
| Model load on click | Yes (30–60 s) | No (pre-loaded at startup) | 0 s wait |
| LoRA adapter overhead | Per-layer B·A multiply | Merged away (optional) | −10–15% |
| Per-page time (8-page PDF) | ~20–30 s | ~6–10 s | ~3× faster |

---

## What still limits speed

1. **Single GPU, sequential pages** — each page must finish before the next starts (GPU is occupied)
2. **QLoRA checkpoint still used as fallback** — if `merge_model.py` has not been run, the app falls back to the LoRA checkpoint (load_in_4bit=False but LoRA overhead still present)
3. **384K pixels is the practical lower limit** — going lower (e.g. 256K) starts to hurt recognition of small text on complex documents
4. **`max_new_tokens=220` is a ceiling, not a guarantee** — if the model generates EOS earlier (which it does for CONTINUATION and short START pages), decoding stops automatically
