"""
Freight Document Intelligence — Gradio App (V3)
Capgemini Theme | Fine-tuned V3 Model | Classification + Extraction + Splitting

Accepts any of:
  • PDF files (digital or scanned)
  • Images  — JPG, PNG, TIFF, BMP, WebP (screenshots, phone photos, scans)
  • Multiple images — uploaded together, treated as ordered pages

Run:
    python dhl_app.py
    Opens at http://localhost:7860
"""

import os
os.environ["TORCHDYNAMO_DISABLE"] = "1"  # triton 3.6 incompatible with torch 2.7 inductor on Windows

import gradio as gr
import json, io, re, time
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

BASE_DIR     = Path(__file__).parent
MODEL_PATH   = BASE_DIR / "models" / "Qwen2.5-VL-3B-Instruct"
LORA_PATH    = BASE_DIR / "model_output_v3" / "checkpoint-2000"
MERGED_PATH  = BASE_DIR / "model_output_v3" / "merged"
MAX_PIXELS = 384_000   # ~490 visual tokens — faster vision encoding (~45% fewer tokens vs 640K)
FIRST_PREV = "none (first page of batch)"
MODEL_DISPLAY_NAME = "Capgemini DocIntel V3"

CLASSES = [
    "Commercial Invoice", "House Bill of Lading", "Certificate of Origin",
    "Shipper's Letter of Instruction", "Dangerous Goods Declaration",
    "Verified Gross Mass", "House Airway Bill", "Packing List",
    "Customs Declaration", "Cargo Manifest", "Import/Export License",
    "Power of Attorney",
]
CLASS_SET = set(CLASSES)

CLASS_ICONS = {
    "Commercial Invoice":              "🧾",
    "House Bill of Lading":            "🚢",
    "Certificate of Origin":           "📜",
    "Shipper's Letter of Instruction": "✉️",
    "Dangerous Goods Declaration":     "⚠️",
    "Verified Gross Mass":             "⚖️",
    "House Airway Bill":               "✈️",
    "Packing List":                    "📦",
    "Customs Declaration":             "🛃",
    "Cargo Manifest":                  "📋",
    "Import/Export License":           "🏛️",
    "Power of Attorney":               "📝",
}

FIELD_LABELS = {
    "shipper_name":           "Shipper",
    "consignee_name":         "Consignee",
    "document_date":          "Date",
    "document_number":        "Doc. Number",
    "country_of_origin":      "Origin",
    "country_of_destination": "Destination",
    "description_of_goods":   "Goods Description",
    "license_number":         "License Number",
    "validity_start":         "Valid From",
    "validity_end":           "Valid Until",
    "licensee_name":          "Licensee",
}

# V3 prompt — matches Training_Data_v3 format (no weight fields)
PROMPT = (
    "Analyze this freight logistics document page.\n\n"
    "Previous page: {prev}\n\n"
    "Output a single JSON line.\n\n"
    "If this is the START (first page of a new document):\n"
    '  {{"class": "...", "position": "START", "shipper_name": "...", '
    '"consignee_name": "...", "document_date": "...", "document_number": "...", '
    '"country_of_origin": "...", "country_of_destination": "...", '
    '"description_of_goods": "...", '
    '"license_number": "...", "validity_start": "...", '
    '"validity_end": "...", "licensee_name": "..."}}\n\n'
    "If this is a CONTINUATION (same document continues from previous page):\n"
    '  {{"class": "...", "position": "CONTINUATION"}}\n\n'
    "Document classes: " + ", ".join(CLASSES) + "\n\n"
    "Rules:\n"
    "- Output ONLY values that are clearly printed and readable on this page.\n"
    "- If a field is blank, empty, missing, or you cannot read it, output null.\n"
    "- Do NOT invent, guess, or fill in values from memory.\n"
    "- Use null for all fields not visible on this page."
)



# ── Model (loaded once at startup, cached) ────────────────────────────────────
_model = _processor = None

def get_model():
    global _model, _processor
    if _model is not None:
        return _model, _processor

    import torch
    # TF32: faster matmul on Ampere/Ada with negligible precision loss
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32       = True

    from unsloth import FastVisionModel

    # Priority: merged (fastest) → LoRA checkpoint → base model
    if MERGED_PATH.exists():
        src, label = str(MERGED_PATH), "merged (bfloat16, no LoRA overhead)"
    elif LORA_PATH.exists():
        src, label = str(LORA_PATH), "LoRA checkpoint (bfloat16)"
    else:
        src, label = str(MODEL_PATH), "base model"
    print(f"Loading {label} ...")

    # load_in_4bit=False → bfloat16 (matches training precision).
    # 3B model ≈ 6.5 GB, fits in 16 GB VRAM — no int4 dequantisation tax.
    _model, _processor = FastVisionModel.from_pretrained(
        src, load_in_4bit=False,
    )

    FastVisionModel.for_inference(_model)
    _model.eval()

    _warmup_model()
    print("Model ready.")
    return _model, _processor


def _warmup_model():
    """Single dummy forward pass to initialise CUDA kernel caches."""
    import torch
    dummy = Image.new("RGB", (224, 224), color=128)
    tmpl  = _processor.apply_chat_template(
        [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "x"}]}],
        tokenize=False, add_generation_prompt=True,
    )
    inputs = _processor(text=[tmpl], images=[dummy], return_tensors="pt",
                        padding=False).to("cuda")
    with torch.inference_mode():
        _model.generate(**inputs, max_new_tokens=4, do_sample=False, use_cache=True)
    print("Warmup complete.")


# ── Inference helpers ─────────────────────────────────────────────────────────
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp", ".gif"}


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", image.size, (255, 255, 255))
        bg.paste(image, mask=image.split()[-1])
        return bg
    return image.convert("RGB")


def _preprocess(image: Image.Image, is_scan: bool = False) -> Image.Image:
    image = _to_rgb(image)
    image = ImageOps.exif_transpose(image)

    if is_scan:
        image = image.filter(ImageFilter.SHARPEN)
        image = ImageEnhance.Contrast(image).enhance(1.25)
        image = ImageEnhance.Sharpness(image).enhance(1.4)

    w, h = image.size
    if w * h > MAX_PIXELS:
        s = (MAX_PIXELS / (w * h)) ** 0.5
        image = image.resize((int(w * s), int(h * s)), Image.LANCZOS)

    return image


_PROMPT_TMPL = None

def _get_prompt(processor, prev: str) -> str:
    global _PROMPT_TMPL
    if _PROMPT_TMPL is None:
        _PROMPT_TMPL = processor.apply_chat_template(
            [{"role": "user", "content": [
                {"type": "image"}, {"type": "text", "text": "PLACEHOLDER"},
            ]}],
            tokenize=False, add_generation_prompt=True,
        )
    return _PROMPT_TMPL.replace("PLACEHOLDER", PROMPT.format(prev=prev))


def precompute_pixel_values(proc_images: list, processor) -> list[dict]:
    """
    Pre-compute pixel_values for every page using the image processor only.
    Result is independent of the text/prev prompt — safe to compute upfront.
    Tensors are pinned (page-locked RAM) for fastest possible PCIe transfer to CUDA.
    """
    cache = []
    for img in proc_images:
        img_out = processor.image_processor(images=[img], return_tensors="pt")
        cache.append({
            "pixel_values":   img_out["pixel_values"].pin_memory(),
            "image_grid_thw": img_out.get("image_grid_thw"),
        })
    return cache


def analyze_page(model, processor, prev: str,
                 preprocessed: Image.Image,
                 pv_cache: dict | None = None) -> str:
    """
    Run model inference on one page.

    pv_cache: pre-computed dict from precompute_pixel_values().
      If provided, pixel_values are NOT re-computed from the PIL image — only
      the text tokens are re-built (fast, ~5ms). The cached tensor is moved to
      CUDA with non_blocking=True, overlapping the PCIe transfer with any
      preceding CPU work.
    """
    import torch
    text   = _get_prompt(processor, prev)
    inputs = processor(text=[text], images=[preprocessed], return_tensors="pt",
                       padding=False)

    if pv_cache is not None:
        # Replace processor-computed pixel_values with pre-computed version.
        # non_blocking=True: starts the PCIe transfer without stalling the CPU.
        inputs["pixel_values"] = pv_cache["pixel_values"].to("cuda", non_blocking=True)
        if pv_cache.get("image_grid_thw") is not None:
            inputs["image_grid_thw"] = pv_cache["image_grid_thw"]
        # Move remaining (small) tensors synchronously
        inputs = {k: (v.to("cuda") if hasattr(v, "to") and k != "pixel_values" else v)
                  for k, v in inputs.items()}
    else:
        inputs = inputs.to("cuda")

    with torch.inference_mode():
        out = model.generate(
            **inputs,
            max_new_tokens=220,   # worst-case START JSON (CI/CoO, all fields) ≈ 185-200 tokens; CONTINUATION ≈ 25
            do_sample=False,
            use_cache=True,
        )

    n_input = inputs["input_ids"].shape[1]
    return processor.decode(out[0][n_input:], skip_special_tokens=True).replace("<|im_end|>", "").strip()


def parse_response(raw: str) -> dict:
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


# ── Post-processing ───────────────────────────────────────────────────────────
def group_into_documents(page_results: list) -> list:
    documents, current = [], None
    for r in page_results:
        cls = r["cls"]
        pos = r["pos"]
        pg  = r["page"]

        if cls is None:
            cls = r["raw"][:40]
            pos = "START"

        is_new = (pos == "START") or (current is not None and cls != current["class"])
        if is_new:
            if current:
                documents.append(current)
            current = {
                "class":      cls,
                "page_start": pg,
                "page_end":   pg,
                "icon":       CLASS_ICONS.get(cls, "📄"),
                "fields":     r.get("fields", {}),
            }
        else:
            if current:
                current["page_end"] = pg
            else:
                current = {
                    "class": cls, "page_start": pg, "page_end": pg,
                    "icon":  CLASS_ICONS.get(cls, "📄"), "fields": {},
                }

    if current:
        documents.append(current)

    for d in documents:
        d["n_pages"] = d["page_end"] - d["page_start"] + 1

    return documents


# ── HTML output builders ──────────────────────────────────────────────────────
def _field_cell(key: str, val) -> str:
    """Render a single extracted field as a styled card cell."""
    label     = FIELD_LABELS.get(key, key)
    val_str   = str(val)
    truncated = (val_str[:55] + "…") if len(val_str) > 55 else val_str
    return (
        f"<div style='background:#f8fafc;border-radius:6px;padding:6px 10px;min-width:0'>"
        f"<div style='font-size:9px;font-weight:700;color:#94a3b8;"
        f"letter-spacing:0.5px;margin-bottom:2px'>{label.upper()}</div>"
        f"<div style='font-size:12px;color:#1e293b;font-weight:600;"
        f"word-break:break-word' title='{val_str}'>{truncated}</div>"
        f"</div>"
    )


def _field_grid(fields: dict) -> str:
    """
    Build a field display for a document card.
    Null fields are already absent from the dict (filtered at parse time).
    Pairs are rendered 2-column only when both sides are present;
    a lone field from a pair falls back to full-width.
    """
    if not fields:
        return (
            "<div style='font-size:11px;color:#94a3b8;font-style:italic;"
            "margin-top:10px'>No fields extracted for this document</div>"
        )

    pair_groups = [
        ("shipper_name",      "consignee_name"),
        ("document_date",     "document_number"),
        ("country_of_origin", "country_of_destination"),
        ("license_number",    "licensee_name"),
        ("validity_start",    "validity_end"),
    ]
    # description + any weight fields present in the model output
    full_width_keys = ["description_of_goods"]

    html = (
        "<div style='margin-top:12px;padding-top:12px;border-top:1px solid #e2e8f0'>"
        "<div style='font-size:10px;font-weight:700;color:#94a3b8;"
        "letter-spacing:0.8px;margin-bottom:8px'>EXTRACTED FIELDS</div>"
    )

    rendered = set()

    for left_key, right_key in pair_groups:
        left_val  = fields.get(left_key)
        right_val = fields.get(right_key)

        if left_val is not None and right_val is not None:
            html += (
                "<div style='display:grid;grid-template-columns:1fr 1fr;"
                "gap:10px;margin-bottom:8px'>"
                + _field_cell(left_key, left_val)
                + _field_cell(right_key, right_val)
                + "</div>"
            )
            rendered.update([left_key, right_key])
        elif left_val is not None:
            html += (
                f"<div style='margin-bottom:8px'>{_field_cell(left_key, left_val)}</div>"
            )
            rendered.add(left_key)
        elif right_val is not None:
            html += (
                f"<div style='margin-bottom:8px'>{_field_cell(right_key, right_val)}</div>"
            )
            rendered.add(right_key)

    for key in full_width_keys:
        val = fields.get(key)
        if val is None:
            continue
        label     = FIELD_LABELS.get(key, key)
        val_str   = str(val)
        truncated = (val_str[:120] + "…") if len(val_str) > 120 else val_str
        html += (
            f"<div style='background:#f8fafc;border-radius:6px;"
            f"padding:6px 10px;margin-bottom:8px'>"
            f"<div style='font-size:9px;font-weight:700;color:#94a3b8;"
            f"letter-spacing:0.5px;margin-bottom:2px'>{label.upper()}</div>"
            f"<div style='font-size:12px;color:#1e293b;word-break:break-word'"
            f" title='{val_str}'>{truncated}</div>"
            f"</div>"
        )

    html += "</div>"
    return html


def build_summary_html(documents: list, page_results: list, elapsed: float,
                       pdf_name: str, input_type: str = "PDF") -> str:
    n_pages = len(page_results)
    n_docs  = len(documents)
    ft_ready = MERGED_PATH.exists() or LORA_PATH.exists()

    # Header card
    html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif">

    <div style="background:linear-gradient(135deg,#002E5E,#0070AD);
                border-radius:12px;padding:20px 24px;margin-bottom:20px;
                display:flex;justify-content:space-between;align-items:center">
      <div>
        <div style="color:white;font-size:18px;font-weight:700">✅ Analysis Complete</div>
        <div style="color:rgba(255,255,255,0.8);font-size:13px;margin-top:4px">
          {pdf_name} &nbsp;·&nbsp; {input_type} &nbsp;·&nbsp; {n_pages} page(s) &nbsp;·&nbsp;
          {n_docs} document(s) identified &nbsp;·&nbsp; ⏱ {elapsed:.1f}s
        </div>
      </div>
      <div style="background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);
                  border-radius:8px;padding:8px 16px;color:white;font-size:13px;font-weight:600">
        {MODEL_DISPLAY_NAME if ft_ready else 'Base Model'}
      </div>
    </div>

    <div style="font-size:13px;font-weight:700;color:#003F7D;
                border-left:4px solid #00B1C1;padding-left:10px;margin-bottom:14px">
      📂 IDENTIFIED DOCUMENTS
    </div>"""

    for i, doc in enumerate(documents, 1):
        pages_label = (
            f"Page {doc['page_start']}"
            if doc["n_pages"] == 1
            else f"Pages {doc['page_start']} – {doc['page_end']}"
        )
        fields_html = _field_grid(doc.get("fields", {}))
        doc_fields  = doc.get("fields", {})
        badge_color = "#0070AD" if doc_fields else "#94a3b8"
        badge_text  = f"{len(doc_fields)} field(s) extracted" if doc_fields else "no fields"

        html += f"""
    <div style="background:white;border:1px solid #e2e8f0;border-radius:10px;
                padding:16px 20px;margin-bottom:14px;
                box-shadow:0 1px 4px rgba(0,0,0,0.06);
                border-left:5px solid #0070AD">
      <!-- Document header row -->
      <div style="display:flex;align-items:center;gap:12px">
        <div style="background:#003F7D;color:white;border-radius:50%;
                    width:32px;height:32px;display:flex;align-items:center;
                    justify-content:center;font-size:12px;font-weight:700;flex-shrink:0">{i}</div>
        <div style="font-size:22px">{doc['icon']}</div>
        <div style="flex:1">
          <div style="font-size:15px;font-weight:700;color:#1e293b">{doc['class']}</div>
          <div style="font-size:12px;color:#64748b;margin-top:2px">
            {pages_label} &nbsp;·&nbsp; {doc['n_pages']} page(s)
          </div>
        </div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
          <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:20px;
                      padding:3px 12px;font-size:11px;font-weight:600;color:#166534">
            Doc {i} of {n_docs}
          </div>
          <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:20px;
                      padding:3px 12px;font-size:10px;color:{badge_color}">
            {badge_text}
          </div>
        </div>
      </div>
      <!-- Extracted fields -->
      {fields_html}
    </div>"""

    html += "</div>"
    return html




# ── Page extraction helpers ────────────────────────────────────────────────────
def _pages_from_pdf(pdf_path: str) -> list[tuple[Image.Image, str]]:
    import fitz
    pdf   = fitz.open(pdf_path)
    mat   = fitz.Matrix(150 / 72, 150 / 72)
    pages = []
    for pg in pdf:
        img = Image.open(io.BytesIO(pg.get_pixmap(matrix=mat).tobytes("png")))
        pages.append((img, Path(pdf_path).name))
    pdf.close()
    return pages


def _pages_from_images(file_list: list) -> list[tuple[Image.Image, str]]:
    files_sorted = sorted(file_list, key=lambda f: Path(f.name).name)
    pages = []
    for f in files_sorted:
        ext = Path(f.name).suffix.lower()
        if ext not in IMAGE_EXTS:
            continue
        try:
            img = Image.open(f.name)
            if hasattr(img, "n_frames") and img.n_frames > 1:
                for i in range(img.n_frames):
                    img.seek(i)
                    pages.append((img.copy(), Path(f.name).name))
            else:
                pages.append((img.copy(), Path(f.name).name))
        except Exception as e:
            print(f"  Warning: could not open {f.name}: {e}")
    return pages


# ── Main processing function ───────────────────────────────────────────────────
def process_files(files, progress=gr.Progress(track_tqdm=True)):
    if not files:
        return (
            "<p style='color:#ef4444;padding:20px;font-family:Segoe UI'>Please upload a file first.</p>",
            [],
            "{}",
        )

    files  = files if isinstance(files, list) else [files]
    t0     = time.time()

    first_ext = Path(files[0].name).suffix.lower()
    is_pdf    = first_ext == ".pdf"
    is_scan   = not is_pdf

    # Model is pre-loaded at startup — this is instant
    model, processor = get_model()

    # Extract pages
    progress(0.02, desc="Extracting pages...")
    if is_pdf:
        raw_pages  = _pages_from_pdf(files[0].name)
        input_name = Path(files[0].name).name
    else:
        raw_pages  = _pages_from_images(files)
        names      = sorted(set(Path(f.name).name for f in files))
        input_name = names[0] if len(names) == 1 else f"{names[0]} (+{len(names)-1} more)"

    if not raw_pages:
        return (
            "<p style='color:#ef4444;padding:20px;font-family:Segoe UI'>No readable pages found.</p>",
            [],
            "{}",
        )

    n_pages    = len(raw_pages)
    input_type = "PDF" if is_pdf else ("Photo/Scan" if is_scan else "Image")

    # Pre-process all images once (reused for inference + gallery)
    progress(0.05, desc="Preprocessing images...")
    proc_images = [_preprocess(img, is_scan=is_scan) for img, _ in raw_pages]

    # Pre-compute pixel_values for all pages using image processor only.
    # Keeps tensors in pinned RAM so GPU transfers are non-blocking.
    # Vision encoder still runs per-page on GPU — but pixel_values are
    # never re-computed or re-uploaded after this point.
    progress(0.10, desc="Pre-encoding images...")
    pv_caches = precompute_pixel_values(proc_images, processor)

    # Inference page by page
    page_results = []
    prev_label   = FIRST_PREV

    for pg_num, (proc_img, pv_cache) in enumerate(zip(proc_images, pv_caches), 1):
        progress(0.10 + 0.87 * (pg_num / n_pages),
                 desc=f"Analysing page {pg_num} of {n_pages}...")

        raw  = analyze_page(model, processor, prev_label, proc_img, pv_cache=pv_cache)
        pred = parse_response(raw)
        cls  = pred.get("class")
        pos  = pred.get("position")

        fields = {
            k: v for k, v in pred.items()
            if k not in ("class", "position") and v is not None
        }

        page_results.append({
            "page":   pg_num,
            "raw":    raw,
            "cls":    cls,
            "pos":    pos,
            "prev":   prev_label,
            "fields": fields,
        })

        if cls and pos:
            prev_label = f"{cls} | {pos}"

    # Build outputs
    documents    = group_into_documents(page_results)
    elapsed      = time.time() - t0
    summary_html = build_summary_html(documents, page_results, elapsed,
                                      input_name, input_type=input_type)

    # Gallery
    gallery = []
    for r, proc_img in zip(page_results, proc_images):
        cls_name = r["cls"] or r["raw"][:30]
        caption  = f"Page {r['page']}: {CLASS_ICONS.get(cls_name,'📄')} {cls_name} | {r['pos'] or '?'}"
        gallery.append((proc_img, caption))

    # JSON export
    export = {
        "input":           input_name,
        "input_type":      input_type,
        "model":           MODEL_DISPLAY_NAME if (MERGED_PATH.exists() or LORA_PATH.exists()) else "base",
        "n_pages":         n_pages,
        "elapsed_seconds": round(elapsed, 1),
        "documents": [
            {
                "document_number":  i,
                "class":            d["class"],
                "page_start":       d["page_start"],
                "page_end":         d["page_end"],
                "n_pages":          d["n_pages"],
                "extracted_fields": d.get("fields", {}),
            }
            for i, d in enumerate(documents, 1)
        ],
        "page_details": [
            {"page": r["page"], "class": r["cls"], "position": r["pos"],
             "fields": r.get("fields", {}),
             "raw": r["raw"]}
            for r in page_results
        ],
    }

    return summary_html, gallery, json.dumps(export, indent=2)



# ── Capgemini CSS ─────────────────────────────────────────────────────────────
CSS = """
body, .gradio-container {
    background: #F5F7FA !important;
    font-family: 'Segoe UI', Arial, sans-serif !important;
}
.upload-zone {
    border: 2px dashed #0070AD !important;
    border-radius: 12px !important;
    background: white !important;
}
.btn-analyze {
    background: linear-gradient(135deg, #002E5E, #0070AD) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    padding: 14px 32px !important;
    width: 100% !important;
    box-shadow: 0 3px 12px rgba(0,63,125,0.35) !important;
    transition: all 0.2s !important;
    cursor: pointer !important;
}
.btn-analyze:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 5px 18px rgba(0,63,125,0.45) !important;
}
.btn-clear {
    background: white !important;
    color: #64748b !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    padding: 10px !important;
    width: 100% !important;
}
.gallery-container { background: white; border-radius: 12px; padding: 12px; }
.json-output textarea { font-size: 11px !important; }
.gr-accordion { background: white !important; border-radius: 10px !important; }
"""

EMPTY_UPLOAD_HTML = (
    "<div style='background:white;border:1px solid #e2e8f0;border-radius:12px;"
    "padding:32px;text-align:center;color:#94a3b8;font-family:Segoe UI'>"
    "<div style='font-size:40px;margin-bottom:12px'>📄</div>"
    "<div style='font-size:14px;font-weight:600'>Upload a PDF to begin</div>"
    "<div style='font-size:12px;margin-top:6px'>Classification, extraction "
    "&amp; splitting results will appear here</div>"
    "</div>"
)


# ── Gradio UI ─────────────────────────────────────────────────────────────────
def build_app():
    ft_ready     = MERGED_PATH.exists() or LORA_PATH.exists()
    model_label  = MODEL_DISPLAY_NAME if ft_ready else "Base Model (fine-tuned not found)"
    model_color  = "#166534" if ft_ready else "#92400e"
    model_bg     = "#f0fdf4"  if ft_ready else "#fffbeb"
    model_border = "#86efac"  if ft_ready else "#fcd34d"

    with gr.Blocks(css=CSS, title="Freight Document Intelligence | Capgemini") as app:

        # ── Header ────────────────────────────────────────────────────────────
        gr.HTML(f"""
        <div style="background:linear-gradient(135deg,#002E5E 0%,#003F7D 55%,#0070AD 100%);
                    border-radius:14px;padding:22px 28px;margin-bottom:18px;
                    display:flex;align-items:center;justify-content:space-between;
                    box-shadow:0 6px 24px rgba(0,63,125,0.3)">
          <div>
            <div style="font-size:26px;font-weight:800;color:white;letter-spacing:-0.5px">
              cap<span style="color:#00B1C1">gemini</span>
            </div>
            <div style="font-size:16px;font-weight:600;color:white;margin-top:4px">
              Freight Document Intelligence
            </div>
            <div style="font-size:12px;color:rgba(255,255,255,0.75);margin-top:2px">
              Automatic Classification · Field Extraction · Document Splitting
            </div>
          </div>
          <div style="text-align:right">
            <div style="background:{model_bg};border:1px solid {model_border};
                        color:{model_color};border-radius:8px;padding:8px 16px;
                        font-size:12px;font-weight:600">
              {model_label}
            </div>
            <div style="color:rgba(255,255,255,0.6);font-size:11px;margin-top:6px">
              Qwen2.5-VL-3B-Instruct + LoRA (V2)
            </div>
          </div>
        </div>
        """)

        # ── Upload & Controls ──────────────────────────────────────────────────
        with gr.Row():
            with gr.Column(scale=3):
                gr.HTML("""
                <div style="font-size:13px;font-weight:600;color:#003F7D;margin-bottom:6px">
                  📄 Upload Document(s)
                </div>
                <div style="font-size:11px;color:#64748b;margin-bottom:8px">
                  <b>PDF</b> (digital or scanned) &nbsp;·&nbsp;
                  <b>Images</b>: JPG, PNG, TIFF, BMP, WebP<br>
                  Upload multiple images together for multi-page documents.<br>
                  Photos &amp; screenshots are auto-enhanced before analysis.
                </div>
                """)
                pdf_input = gr.File(
                    label="",
                    file_types=[".pdf", ".jpg", ".jpeg", ".png",
                                ".tiff", ".tif", ".bmp", ".webp"],
                    file_count="multiple",
                    elem_classes=["upload-zone"],
                )

            with gr.Column(scale=1):
                gr.HTML("<div style='height:46px'></div>")
                analyze_btn = gr.Button(
                    "🔍  Analyze Document",
                    elem_classes=["btn-analyze"],
                )
                gr.HTML("<div style='height:8px'></div>")
                clear_btn = gr.Button("✕  Clear", elem_classes=["btn-clear"])


        # ── Results ───────────────────────────────────────────────────────────
        gr.HTML("""
        <div style="font-size:14px;font-weight:700;color:#003F7D;
                    border-left:4px solid #00B1C1;padding-left:10px;margin:16px 0 10px">
          Results
        </div>
        """)

        with gr.Row():
            with gr.Column(scale=3):
                result_html = gr.HTML(EMPTY_UPLOAD_HTML)
            with gr.Column(scale=2):
                gr.HTML("""
                <div style="font-size:12px;font-weight:600;color:#003F7D;margin-bottom:8px">
                  Page Thumbnails
                </div>""")
                gallery = gr.Gallery(
                    label="",
                    show_label=False,
                    columns=3,
                    rows=3,
                    height=380,
                    object_fit="contain",
                    elem_classes=["gallery-container"],
                )

        # ── JSON Export ────────────────────────────────────────────────────────
        with gr.Accordion("⬇️  Export Results as JSON", open=False):
            json_output = gr.Code(language="json", label="", value="", lines=15)

        # ── Footer ─────────────────────────────────────────────────────────────
        gr.HTML("""
        <div style="text-align:center;color:#94a3b8;font-size:11px;
                    margin-top:20px;padding-top:16px;border-top:1px solid #e2e8f0">
          Capgemini &nbsp;·&nbsp; Freight Document Intelligence &nbsp;·&nbsp;
          Classification · Extraction · Splitting &nbsp;·&nbsp;
          Qwen2.5-VL-3B + LoRA V2
        </div>
        """)

        # ── Event handlers ─────────────────────────────────────────────────────
        analyze_btn.click(
            fn=process_files,
            inputs=[pdf_input],
            outputs=[result_html, gallery, json_output],
        )

        clear_btn.click(
            fn=lambda: (EMPTY_UPLOAD_HTML, [], "", None),
            inputs=[],
            outputs=[result_html, gallery, json_output, pdf_input],
        )

    return app


if __name__ == "__main__":
    print("=" * 60)
    print("  Freight Document Intelligence — Capgemini (V3)")
    print("=" * 60)
    print(f"  LoRA    : {LORA_PATH}")
    print(f"  Pixels  : {MAX_PIXELS:,} max (~490 visual tokens)")
    print(f"  URL     : http://localhost:7860")
    print("=" * 60)

    # Pre-load model before the server opens — first inference will be instant
    print("\nPre-loading model...")
    get_model()

    # Find a free port starting from 7860
    import socket
    port = 7860
    while port < 7880:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                break  # port is free
        port += 1

    print("\n" + "=" * 60)
    print("  Model ready. Starting server...")
    print(f"  Local  : http://localhost:{port}")
    print(f"  Network: http://0.0.0.0:{port}")
    print("=" * 60 + "\n")

    app = build_app()
    app.launch(server_name="0.0.0.0", server_port=port,
               share=False, show_error=True, inbrowser=True)
