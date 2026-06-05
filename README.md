# FFDoc_3B — Freight Forward Document Intelligence

Fine-tuning **Qwen2.5-VL-3B-Instruct** on 12 freight logistics document classes.  
The model classifies each page, detects document boundaries (START / CONTINUATION), and extracts universal fields — all in a single forward pass.

**Developed by Capgemini** | Model: `FFDoc_3B`

---

## Table of Contents

1. [What the Model Does](#what-the-model-does)
2. [Document Classes](#document-classes)
3. [Hardware Requirements](#hardware-requirements)
4. [Environment Setup](#environment-setup)
5. [Step-by-Step: Full Pipeline](#step-by-step-full-pipeline)
   - [Step 1 — Download Base Model](#step-1--download-base-model)
   - [Step 2 — Generate Synthetic Data](#step-2--generate-synthetic-data)
   - [Step 3 — Prepare Training Dataset](#step-3--prepare-training-dataset)
   - [Step 4 — Train](#step-4--train)
   - [Step 5 — Merge LoRA Adapters](#step-5--merge-lora-adapters)
   - [Step 6 — Evaluate](#step-6--evaluate)
   - [Step 7 — Run the App](#step-7--run-the-app)
6. [V2 vs V3 — What Changed](#v2-vs-v3--what-changed)
7. [Project Structure](#project-structure)
8. [Configuration Reference](#configuration-reference)

---

## What the Model Does

Given a page image (PDF page or photo), the model outputs a single JSON line:

```json
// START page — first page of a new document
{
  "class": "Commercial Invoice",
  "position": "START",
  "shipper_name": "Acme Corp",
  "consignee_name": "Global Imports Ltd",
  "document_date": "2024-03-15",
  "document_number": "INV-2024-0042",
  "country_of_origin": "Germany",
  "country_of_destination": "United States",
  "description_of_goods": "Electronic components, PCB assemblies",
  "license_number": null,
  "validity_start": null,
  "validity_end": null,
  "licensee_name": null
}

// CONTINUATION page — same document continues
{
  "class": "Commercial Invoice",
  "position": "CONTINUATION"
}
```

---

## Document Classes

| # | Class | Target Samples |
|---|-------|---------------|
| 01 | Commercial Invoice | 900 |
| 02 | House Bill of Lading | 900 |
| 03 | Certificate of Origin | 1,000 (500 General + 500 FTA) |
| 04 | Shipper's Letter of Instruction | 900 |
| 05 | Dangerous Goods Declaration | 900 |
| 06 | Verified Gross Mass | 900 |
| 07 | House Airway Bill | 900 |
| 08 | Packing List | 900 |
| 09 | Customs Declaration (CN23) | 900 |
| 10 | Cargo Manifest | 900 |
| 11 | Import/Export License (EEI) | 900 |
| 12 | Power of Attorney | 900 |

**Total: ~11,700 synthetic documents**

---

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | 16 GB VRAM (RTX 5080) | 24+ GB (A100 / RTX 4090) |
| RAM | 32 GB | 64 GB |
| Disk | 80 GB free | 150 GB |
| OS | Windows 11 / Ubuntu 22.04 | Ubuntu 22.04 |
| CUDA | 12.x | 12.8 |
| Python | 3.11 | 3.11 |

> **16 GB VRAM** → QLoRA (4-bit) is selected automatically  
> **20+ GB VRAM** → LoRA (16-bit bfloat16) is selected automatically

---

## Environment Setup

```powershell
# Windows PowerShell — run once
cd D:\finetuning\DHL_Document_finetuning
.\setup_env.ps1

# Activate the environment every session
.\.training\Scripts\Activate.ps1
```

```bash
# Linux / WSL — manual setup
python -m venv .training
source .training/bin/activate
pip install unsloth torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install reportlab faker Pillow PyMuPDF transformers peft accelerate
pip install gradio openpyxl matplotlib numpy pyyaml
```

---

## Step-by-Step: Full Pipeline

### Step 1 — Download Base Model

```bash
python download_model.py
# Downloads Qwen2.5-VL-3B-Instruct (~7 GB) into models/

# Alternative: larger model (needs 20+ GB VRAM)
python download_model.py --model Qwen/Qwen2.5-VL-7B-Instruct
```

Model is saved to `models/Qwen2.5-VL-3B-Instruct/`.  
Update `train_config.yaml → model.name` if you use a different path.

---

### Step 2 — Generate Synthetic Data

Generates PDF documents programmatically using ReportLab + Faker with realistic freight data.

```bash
# Full run — all 12 classes (~11,700 docs, takes 20–40 min)
python synthetic/generate_all.py

# Quick smoke test — 5 docs per class
python synthetic/generate_all.py --test

# Single class only
python synthetic/generate_all.py --class commercial_invoice

# Custom count per class
python synthetic/generate_all.py --count 200
```

**Output folders created:**

| Folder | Contents |
|--------|----------|
| `Synthetic_Data/` | Single-page documents |
| `Synthetic_Data_MultiPage/` | 2-page docs (START + CONTINUATION) |
| `Synthetic_Data_Splitting_v2/` | Multi-doc packets for splitting training |
| `Synthetic_Data_Blank/` | Blank form templates (v3 only) |

---

### Step 3 — Prepare Training Dataset

Converts synthetic PDFs + real annotated documents into JSONL training format with page images.

```bash
# Prepare v3 dataset (recommended)
python prepare_dataset_v3.py

# Re-process all images from scratch
python prepare_dataset_v3.py --no-skip
```

**What it does internally (5 steps):**

| Step | Description |
|------|-------------|
| `step1` | Single-page synthetic PDFs → images + JSONL labels |
| `step2` | Multi-page PDFs → START / CONTINUATION pairs |
| `step3` | Multi-doc splitting packets |
| `step4` | Real blank PDFs from `Documents/` |
| `step5` | Synthetic blank forms via ReportLab |

**Output:** `Training_Data_v3/` containing:
- `train.jsonl`, `val.jsonl`, `test.jsonl`
- `images/` — page images at 150 DPI PNG

---

### Step 4 — Train

```bash
# Auto mode — detects VRAM and selects QLoRA or LoRA
python train.py

# Force QLoRA — 4-bit quantization (safe on 16 GB VRAM)
python train.py --method qlora

# Force LoRA — 16-bit bfloat16 (A100 / 24+ GB VRAM)
python train.py --method lora

# Smoke test — 1 epoch, 100 samples
python train.py --epochs 1 --debug

# Custom epoch count
python train.py --epochs 3
```

**Key config** (`train_config.yaml`):

```yaml
model:
  name: "models/Qwen2.5-VL-3B-Instruct"
  method: "auto"       # auto | qlora | lora

lora:
  r: 32                # LoRA rank
  alpha: 32            # scale = alpha/r = 1.0

training:
  epochs: 3
  batch_size: 1
  grad_accum: 16       # effective batch = 16
  lr: 2e-4

paths:
  train_data: "Training_Data_v3/train.jsonl"
  output_dir: "model_output_v3"
```

Checkpoints are saved to `model_output_v3/checkpoint-XXXX/` every 500 steps.  
Expected time: **~45–60 min** for 3 epochs on RTX 5080 (16 GB).

---

### Step 5 — Merge LoRA Adapters

Fuses LoRA weights into the base model for faster inference (no adapter overhead at runtime).

```bash
python merge_model.py
# Creates model_output_v3/merged   (~6.5 GB bfloat16)
# Also creates model_output_v3/ck2000_merged
```

> Run this **once** before evaluation or launching the app.  
> `dhl_app.py` automatically uses `merged/` if it exists, otherwise falls back to the raw checkpoint.

---

### Step 6 — Evaluate

#### Quick check on a single document
```bash
python final_check.py
```

#### Compare our model vs baselines
```bash
# Full run — all 5 models, 500 stratified test samples each
python eval_all_models.py

# Specific models only
python eval_all_models.py --models qwen3b ours

# Quick smoke test
python eval_all_models.py --models qwen3b ours --max-samples 50

# Point to a specific checkpoint
python eval_all_models.py --our-checkpoint model_output_v3/checkpoint-2000
```

**Baselines compared:**

| ID | Model | Notes |
|----|-------|-------|
| `qwen3b` | Qwen2.5-VL-3B-Instruct | Our base model, zero-shot |
| `qwen7b` | Qwen2.5-VL-7B-Instruct | Larger zero-shot baseline |
| `internvl2` | InternVL2-2B | Document-focused VLM |
| `donut` | Donut DocVQA | Document specialist |
| `ours` | Qwen2.5-VL-3B + LoRA v3 | **Our fine-tuned FFDoc_3B** |

**Metrics reported:**

| Metric | Description |
|--------|-------------|
| Class Accuracy | Predicted class == ground-truth class |
| Position Accuracy | START / CONTINUATION prediction |
| Field F1 | Token-level F1 over non-null extracted fields |
| Split IoU | Jaccard similarity of document boundary detection |

Results saved to `eval_results/comparison_<timestamp>/`.

---

### Step 7 — Run the App

```bash
python dhl_app.py
# Opens at http://localhost:7860
```

The app auto-selects the best available model:
1. `model_output_v3/merged` — merged bfloat16 (fastest)
2. `model_output_v3/checkpoint-2000` — LoRA checkpoint
3. `models/Qwen2.5-VL-3B-Instruct` — base model (no fine-tuning)

**Supported inputs:** PDF (digital or scanned), JPG, PNG, TIFF, BMP, WebP  
Upload multiple images together to process as an ordered multi-page document.

---

## V2 vs V3 — What Changed

### Dataset Differences

| Aspect | V2 | V3 |
|--------|----|----|
| Universal fields | **12 fields** | **9 fields** |
| Weight fields | `gross_weight_kg`, `net_weight_kg`, `total_weight_kg` included | **Removed** |
| Blank forms | Not included | Added (real + synthetic) |
| Processing steps | 3 | 5 |
| Output directory | `Training_Data_v2/` | `Training_Data_v3/` |

### Why weight fields were removed in V3

Weight fields were in V2 but removed in V3 because:
- Not all 12 document classes contain weight data
- Values appear in inconsistent units and formats across document types
- Extraction accuracy was low, adding noise to the training signal
- Removing them improved overall Field F1 by giving the model a cleaner, more consistent target

### Model Differences

| Aspect | V2 | V3 |
|--------|----|----|
| Base model | Qwen2.5-VL-3B-Instruct | Qwen2.5-VL-3B-Instruct |
| Fields extracted | 12 | 9 (no weight fields) |
| Blank form training | No | Yes |
| Checkpoint directory | `model_output_v2/` | `model_output_v3/` |
| Merged model path | `model_output_v2/merged` | `model_output_v3/merged` |

---

## Project Structure

```
DHL_Document_finetuning/
│
├── synthetic/                         # Data generation scripts
│   ├── generate_all.py                # Master runner — all 12 classes
│   ├── data_generators.py             # Shared Faker + domain table helpers
│   ├── generate_commercial_invoice.py
│   ├── generate_house_bol.py
│   ├── generate_coo_general.py / generate_coo_fta.py
│   ├── generate_sli.py / generate_dgd.py / generate_hawb.py
│   ├── generate_packing_list.py / generate_cn23.py
│   ├── generate_cargo_manifest.py / generate_eei.py
│   └── generate_poa_multiformat.py
│
├── prepare_dataset_v3.py              # Build Training_Data_v3/ (recommended)
├── prepare_dataset_v2.py              # Build Training_Data_v2/ (legacy)
│
├── train.py                           # Fine-tuning with Unsloth (QLoRA / LoRA)
├── train_config.yaml                  # All hyperparameters — edit this
│
├── merge_model.py                     # Merge LoRA into base → standalone model
│
├── eval_all_models.py                 # Full comparison vs baselines
├── final_check.py                     # Quick single-doc sanity check
│
├── dhl_app.py                         # Gradio web UI (FFDoc_3B)
├── download_model.py                  # Download base model from HuggingFace
├── setup_env.ps1                      # Windows environment setup
│
├── models/                            # Downloaded base model weights
│   └── Qwen2.5-VL-3B-Instruct/
│
├── Training_Data_v3/                  # Dataset built by prepare_dataset_v3.py
│   ├── train.jsonl / val.jsonl / test.jsonl
│   └── images/
│
├── model_output_v3/                   # Training outputs
│   ├── checkpoint-2000/               # LoRA adapter (mid-training)
│   ├── final/                         # LoRA adapter (end of training)
│   └── merged/                        # Merged bfloat16 model (used by app)
│
├── eval_results/                      # Evaluation reports (CSV, charts, JSON)
├── Documents/                         # Real blank PDFs for v3 dataset
└── test_documents/                    # Sample docs for manual testing
```

---

## Configuration Reference

All training hyperparameters are in `train_config.yaml`. Edit this file — no need to touch `train.py`.

```yaml
model:
  name: "models/Qwen2.5-VL-3B-Instruct"
  # Alternatives:
  #   "Qwen/Qwen3-VL-4B-Instruct"     — 4B, better DocVQA, tight on 16 GB
  #   "Qwen/Qwen2.5-VL-7B-Instruct"   — 7B, needs 20+ GB VRAM
  method: "auto"                        # auto | qlora | lora

lora:
  r: 32           # rank — higher = more capacity
  alpha: 32       # scaling (alpha/r = 1.0 = conservative)
  dropout: 0.0    # must be 0.0 for Unsloth fast kernels

training:
  epochs: 3
  batch_size: 1
  grad_accum: 16  # effective batch = 16
  lr: 2e-4
  warmup_ratio: 0.03
  save_steps: 500

paths:
  train_data: "Training_Data_v3/train.jsonl"
  val_data:   "Training_Data_v3/val.jsonl"
  output_dir: "model_output_v3"
```

---

## Quick Reference — Full Pipeline

```bash
# 1. Download base model
python download_model.py

# 2. Generate synthetic data
python synthetic/generate_all.py

# 3. Build training dataset
python prepare_dataset_v3.py

# 4. Train
python train.py

# 5. Merge LoRA into base model
python merge_model.py

# 6. Evaluate
python eval_all_models.py --models qwen3b ours

# 7. Run the app
python dhl_app.py
```
