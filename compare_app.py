"""
DHL Document Intelligence — Model Comparison App
Capgemini Theme | Base Model vs V2 Fine-tuned | Side-by-Side

Upload a PDF → both models analyse every page → results shown side by side:
  • Agreement stats (how often models agree on class / position)
  • Document summary cards — Base (left) vs Fine-tuned (right)
  • Per-page comparison table with colour-coded agreement rows
  • Extracted fields comparison (Fine-tuned extracts; Base shown where possible)
  • JSON export for both models

Run:
    python compare_app.py
    Opens at http://localhost:7860
"""

import gradio as gr
import json, io, re, time
from pathlib import Path
from PIL import Image

BASE_DIR    = Path(__file__).parent
MODEL_PATH  = BASE_DIR / "models" / "Qwen2.5-VL-3B-Instruct"
LORA_PATH   = BASE_DIR / "model_output_v2" / "final"
MAX_PIXELS  = 1_000_000
FIRST_PREV  = "none (first page of batch)"

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
    "description_of_goods":   "Goods",
    "gross_weight_kg":        "Weight (kg)",
    "license_number":         "License No.",
    "validity_start":         "Valid From",
    "validity_end":           "Valid Until",
    "licensee_name":          "Licensee",
}

# ── Prompts ───────────────────────────────────────────────────────────────────

# Fine-tuned: exact training format
PROMPT_FT = (
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

# Base: fair natural-language JSON prompt (no angle-bracket placeholders)
PROMPT_BASE = (
    "You are a DHL logistics document analyst.\n\n"
    "Examine this document page and output a single JSON line.\n\n"
    "Previous page in this batch: {prev}\n\n"
    "STEP 1 — Classify: identify the document type (choose exactly one):\n"
    + "\n".join(f"  {c}" for c in CLASSES)
    + "\n\n"
    "STEP 2 — Position: is this the START (first page of a new document) "
    "or a CONTINUATION (same document as the previous page)?\n\n"
    "STEP 3 — If START, extract these fields (use null if not visible):\n"
    "  shipper_name, consignee_name, document_date (YYYY-MM-DD),\n"
    "  document_number, country_of_origin, country_of_destination,\n"
    "  description_of_goods, gross_weight_kg (number),\n"
    "  license_number, validity_start, validity_end, licensee_name\n\n"
    "Example — START:\n"
    '{{"class": "Commercial Invoice", "position": "START", "shipper_name": "Acme Corp", '
    '"consignee_name": "Beta Ltd", "document_date": "2025-01-15", '
    '"document_number": "INV-001", "country_of_origin": "China", '
    '"country_of_destination": "USA", "description_of_goods": "Electronic parts", '
    '"gross_weight_kg": 125.5, "license_number": null, "validity_start": null, '
    '"validity_end": null, "licensee_name": null}}\n\n'
    "Example — CONTINUATION:\n"
    '{{"class": "Commercial Invoice", "position": "CONTINUATION"}}'
)


# ── Model loading (both cached) ───────────────────────────────────────────────
_models: dict = {}

def _load(model_type: str):
    if model_type in _models:
        return _models[model_type]
    from unsloth import FastVisionModel
    if model_type == "finetuned":
        print(f"Loading FINE-TUNED model from {LORA_PATH} ...")
        m, p = FastVisionModel.from_pretrained(str(LORA_PATH), load_in_4bit=True)
    else:
        print(f"Loading BASE model from {MODEL_PATH} ...")
        m, p = FastVisionModel.from_pretrained(str(MODEL_PATH), load_in_4bit=True)
    FastVisionModel.for_inference(m)
    m.eval()
    _models[model_type] = (m, p)
    return m, p

def get_models():
    base_model, base_proc = _load("base")
    ft_model,   ft_proc   = _load("finetuned") if LORA_PATH.exists() else (None, None)
    return base_model, base_proc, ft_model, ft_proc


# ── Inference ─────────────────────────────────────────────────────────────────
def _resize(img: Image.Image) -> Image.Image:
    w, h = img.size
    if w * h > MAX_PIXELS:
        s = (MAX_PIXELS / (w * h)) ** 0.5
        img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
    return img

def _infer(model, processor, image: Image.Image, prompt: str, max_new_tokens: int = 300) -> str:
    import torch
    img    = _resize(image)
    msgs   = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
    text   = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[img], return_tensors="pt", padding=True).to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    full   = processor.decode(out[0], skip_special_tokens=True)
    answer = full.split("assistant")[-1].strip() if "assistant" in full else full.strip()
    return answer.replace("<|im_end|>", "").strip()


# ── Parsing ───────────────────────────────────────────────────────────────────
def _parse(raw: str) -> dict:
    """Extract JSON dict from model output; fallback to keyword search."""
    for candidate in [raw.strip(), *re.findall(r"\{[^{}]+\}", raw, re.DOTALL)]:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                if obj.get("class") not in CLASS_SET:
                    obj["class"] = None
                if obj.get("position") not in ("START", "CONTINUATION"):
                    obj["position"] = None
                return obj
        except Exception:
            pass
    # Keyword fallback
    found_cls = next(
        (c for c in sorted(CLASS_SET, key=len, reverse=True) if c.lower() in raw.lower()),
        None
    )
    found_pos = (
        "CONTINUATION" if re.search(r"\bCONTINUATION\b", raw, re.IGNORECASE)
        else "START"    if re.search(r"\bSTART\b",        raw, re.IGNORECASE)
        else None
    )
    return {"class": found_cls, "position": found_pos}


# ── Post-processing ───────────────────────────────────────────────────────────
def _group(page_results: list) -> list:
    docs, cur = [], None
    for r in page_results:
        cls, pos, pg = r["cls"], r["pos"], r["page"]
        if cls is None:
            cls, pos = r["raw"][:40], "START"
        is_new = (pos == "START") or (cur is not None and cls != cur["class"])
        if is_new:
            if cur:
                docs.append(cur)
            cur = {"class": cls, "page_start": pg, "page_end": pg,
                   "icon": CLASS_ICONS.get(cls, "📄"),
                   "fields": r.get("fields", {})}
        else:
            if cur:
                cur["page_end"] = pg
            else:
                cur = {"class": cls, "page_start": pg, "page_end": pg,
                       "icon": CLASS_ICONS.get(cls, "📄"), "fields": {}}
    if cur:
        docs.append(cur)
    for d in docs:
        d["n_pages"] = d["page_end"] - d["page_start"] + 1
    return docs


# ── HTML helpers ──────────────────────────────────────────────────────────────
def _mini_doc_card(doc: dict, idx: int, total: int, accent: str) -> str:
    pages = (f"Page {doc['page_start']}" if doc["n_pages"] == 1
             else f"pp. {doc['page_start']}–{doc['page_end']}")
    fields = doc.get("fields", {})
    fields_html = ""
    if fields:
        rows = []
        for k, v in list(fields.items())[:4]:   # show up to 4 fields
            label = FIELD_LABELS.get(k, k)
            rows.append(
                f"<div style='display:flex;gap:6px;font-size:10px;margin-bottom:2px'>"
                f"<span style='color:#94a3b8;min-width:70px'>{label}:</span>"
                f"<span style='color:#1e293b;font-weight:600;word-break:break-word'>"
                f"{str(v)[:45]}{'…' if len(str(v))>45 else ''}</span></div>"
            )
        fields_html = (
            "<div style='margin-top:8px;padding-top:8px;border-top:1px solid #f1f5f9'>"
            + "".join(rows) + "</div>"
        )
    return f"""
    <div style="background:white;border:1px solid #e2e8f0;border-radius:8px;
                padding:12px 14px;margin-bottom:10px;
                border-left:4px solid {accent}">
      <div style="display:flex;align-items:center;gap:8px">
        <div style="background:{accent};color:white;border-radius:50%;
                    width:24px;height:24px;display:flex;align-items:center;
                    justify-content:center;font-size:10px;font-weight:700;flex-shrink:0">{idx}</div>
        <div style="font-size:13px">{doc['icon']}</div>
        <div style="flex:1;min-width:0">
          <div style="font-size:12px;font-weight:700;color:#1e293b;
                      white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{doc['class']}</div>
          <div style="font-size:10px;color:#64748b">{pages} · {doc['n_pages']} page(s)</div>
        </div>
        <div style="font-size:10px;color:{accent};font-weight:600;flex-shrink:0">
          {idx}/{total}
        </div>
      </div>
      {fields_html}
    </div>"""


def _doc_column(docs: list, label: str, accent: str, elapsed: float) -> str:
    header = (
        f"<div style='font-size:11px;font-weight:700;color:{accent};"
        f"margin-bottom:10px;padding:6px 10px;background:{accent}18;"
        f"border-radius:6px;display:flex;justify-content:space-between'>"
        f"<span>{label}</span>"
        f"<span style='font-weight:400;color:#64748b'>{len(docs)} doc(s) · ⏱ {elapsed:.1f}s</span>"
        f"</div>"
    )
    if not docs:
        return (
            header
            + "<div style='color:#94a3b8;font-size:11px;font-style:italic;"
            "padding:10px'>No documents identified</div>"
        )
    cards = "".join(_mini_doc_card(d, i, len(docs), accent) for i, d in enumerate(docs, 1))
    return header + cards


def _comparison_table(base_pages: list, ft_pages: list) -> str:
    """Per-page table with colour-coded agreement rows."""
    html = """
    <div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin-top:4px">
    <table style="width:100%;border-collapse:collapse;font-size:11px">
      <thead>
        <tr style="background:#1e293b;color:white">
          <th style="padding:9px 10px;text-align:center;width:45px">Page</th>
          <th style="padding:9px 10px;text-align:left;width:50%">
            🔵 Base Model
          </th>
          <th style="padding:9px 10px;text-align:left;width:50%">
            🟢 Fine-tuned V2
          </th>
          <th style="padding:9px 10px;text-align:center;width:70px">Match</th>
        </tr>
      </thead>
      <tbody>"""

    ft_map = {r["page"]: r for r in ft_pages}

    for r_base in base_pages:
        pg     = r_base["page"]
        r_ft   = ft_map.get(pg, {})

        b_cls  = r_base.get("cls") or "?"
        b_pos  = r_base.get("pos") or "?"
        f_cls  = r_ft.get("cls")   or "?"
        f_pos  = r_ft.get("pos")   or "?"

        cls_ok = (b_cls == f_cls) and b_cls != "?"
        pos_ok = (b_pos == f_pos) and b_pos != "?"

        # Row colour
        if cls_ok and pos_ok:
            row_bg    = "#f0fdf4"   # green  — full agreement
            match_ico = "✅"
        elif cls_ok:
            row_bg    = "#fefce8"   # yellow — class agrees, position differs
            match_ico = "🟡"
        elif pos_ok:
            row_bg    = "#fff7ed"   # orange — position agrees, class differs
            match_ico = "🟠"
        else:
            row_bg    = "#fef2f2"   # red    — both differ
            match_ico = "❌"

        # Position badge
        def pos_badge(pos):
            color = "#22c55e" if pos == "START" else "#f59e0b" if pos == "CONTINUATION" else "#94a3b8"
            return (
                f"<span style='background:{color};color:white;padding:2px 7px;"
                f"border-radius:10px;font-size:9px;font-weight:700'>{pos}</span>"
            )

        # Fine-tuned fields (top 2)
        ft_fields = r_ft.get("fields", {})
        ft_field_html = ""
        if ft_fields and f_pos == "START":
            items = []
            for k in ("shipper_name", "consignee_name"):
                v = ft_fields.get(k)
                if v:
                    items.append(
                        f"<span style='color:#64748b'>{FIELD_LABELS[k]}:</span> "
                        f"<b>{str(v)[:30]}</b>"
                    )
            if items:
                ft_field_html = (
                    "<div style='margin-top:3px;font-size:10px;color:#475569'>"
                    + " &nbsp;·&nbsp; ".join(items) + "</div>"
                )

        # Base fields (top 2, if extracted)
        base_fields = r_base.get("fields", {})
        base_field_html = ""
        if base_fields and b_pos == "START":
            items = []
            for k in ("shipper_name", "consignee_name"):
                v = base_fields.get(k)
                if v:
                    items.append(
                        f"<span style='color:#64748b'>{FIELD_LABELS[k]}:</span> "
                        f"<b>{str(v)[:30]}</b>"
                    )
            if items:
                base_field_html = (
                    "<div style='margin-top:3px;font-size:10px;color:#475569'>"
                    + " &nbsp;·&nbsp; ".join(items) + "</div>"
                )

        b_icon = CLASS_ICONS.get(b_cls, "📄") if b_cls != "?" else "❓"
        f_icon = CLASS_ICONS.get(f_cls, "📄") if f_cls != "?" else "❓"

        html += f"""
        <tr style="background:{row_bg};border-bottom:1px solid #e2e8f0">
          <td style="padding:8px 10px;text-align:center;font-weight:700;
                     color:#003F7D;font-size:12px">{pg}</td>
          <td style="padding:8px 10px">
            <div style="font-weight:600;color:#1e293b">{b_icon} {b_cls}</div>
            <div style="margin-top:3px">{pos_badge(b_pos)}</div>
            {base_field_html}
          </td>
          <td style="padding:8px 10px">
            <div style="font-weight:600;color:#1e293b">{f_icon} {f_cls}</div>
            <div style="margin-top:3px">{pos_badge(f_pos)}</div>
            {ft_field_html}
          </td>
          <td style="padding:8px 10px;text-align:center;font-size:16px">{match_ico}</td>
        </tr>"""

    html += "</tbody></table></div>"
    return html


def _agreement_stats(base_pages: list, ft_pages: list) -> str:
    ft_map   = {r["page"]: r for r in ft_pages}
    n        = len(base_pages)
    cls_ok   = sum(1 for r in base_pages if r.get("cls") == ft_map.get(r["page"], {}).get("cls") and r.get("cls"))
    pos_ok   = sum(1 for r in base_pages if r.get("pos") == ft_map.get(r["page"], {}).get("pos") and r.get("pos"))
    both_ok  = sum(1 for r in base_pages
                   if r.get("cls") == ft_map.get(r["page"], {}).get("cls")
                   and r.get("pos") == ft_map.get(r["page"], {}).get("pos")
                   and r.get("cls"))

    def bar(v, d, color):
        pct = int(100 * v / max(d, 1))
        return (
            f"<div style='font-size:22px;font-weight:800;color:{color}'>{pct}%</div>"
            f"<div style='background:#e2e8f0;border-radius:4px;height:6px;margin:4px 0'>"
            f"<div style='background:{color};width:{pct}%;height:6px;border-radius:4px'></div></div>"
            f"<div style='font-size:10px;color:#64748b'>{v}/{d} pages</div>"
        )

    return f"""
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;
                margin-bottom:16px">
      <div style="background:white;border:1px solid #e2e8f0;border-radius:10px;
                  padding:14px 16px;text-align:center">
        <div style="font-size:10px;font-weight:700;color:#64748b;
                    letter-spacing:0.5px;margin-bottom:6px">CLASS AGREEMENT</div>
        {bar(cls_ok, n, '#0070AD')}
      </div>
      <div style="background:white;border:1px solid #e2e8f0;border-radius:10px;
                  padding:14px 16px;text-align:center">
        <div style="font-size:10px;font-weight:700;color:#64748b;
                    letter-spacing:0.5px;margin-bottom:6px">POSITION AGREEMENT</div>
        {bar(pos_ok, n, '#7c3aed')}
      </div>
      <div style="background:white;border:1px solid #e2e8f0;border-radius:10px;
                  padding:14px 16px;text-align:center">
        <div style="font-size:10px;font-weight:700;color:#64748b;
                    letter-spacing:0.5px;margin-bottom:6px">FULL AGREEMENT</div>
        {bar(both_ok, n, '#16a34a')}
      </div>
    </div>"""


# ── Main processing function ───────────────────────────────────────────────────
def process_pdf(pdf_file, progress=gr.Progress(track_tqdm=True)):
    if pdf_file is None:
        empty = (
            "<p style='color:#ef4444;padding:20px;font-family:Segoe UI'>"
            "Please upload a PDF file first.</p>"
        )
        return empty, empty, empty, "{}"

    import fitz
    pdf_path = pdf_file.name
    pdf_name = Path(pdf_path).name

    progress(0, desc="Loading models...")
    base_model, base_proc, ft_model, ft_proc = get_models()

    pdf     = fitz.open(pdf_path)
    n_pages = len(pdf)
    pdf.close()

    base_pages: list = []
    ft_pages:   list = []

    # ── Run BASE model ────────────────────────────────────────────────────────
    prev_base = FIRST_PREV
    pdf = fitz.open(pdf_path)
    t_base = time.time()
    for pg_num, page in enumerate(pdf, 1):
        progress(
            pg_num / (n_pages * 2),
            desc=f"Base model — page {pg_num}/{n_pages}..."
        )
        mat = fitz.Matrix(150 / 72, 150 / 72)
        img = Image.open(io.BytesIO(page.get_pixmap(matrix=mat).tobytes("png")))
        raw  = _infer(base_model, base_proc, img, PROMPT_BASE.format(prev=prev_base))
        pred = _parse(raw)
        cls, pos = pred.get("class"), pred.get("position")
        fields = {k: v for k, v in pred.items() if k not in ("class","position") and v is not None}
        base_pages.append({"page": pg_num, "raw": raw, "cls": cls, "pos": pos,
                            "prev": prev_base, "fields": fields})
        if cls and pos:
            prev_base = f"{cls} | {pos}"
    pdf.close()
    elapsed_base = time.time() - t_base

    # ── Run FINE-TUNED model ──────────────────────────────────────────────────
    prev_ft = FIRST_PREV
    elapsed_ft = 0.0
    if ft_model:
        pdf = fitz.open(pdf_path)
        t_ft = time.time()
        for pg_num, page in enumerate(pdf, 1):
            progress(
                0.5 + pg_num / (n_pages * 2),
                desc=f"Fine-tuned model — page {pg_num}/{n_pages}..."
            )
            mat = fitz.Matrix(150 / 72, 150 / 72)
            img = Image.open(io.BytesIO(page.get_pixmap(matrix=mat).tobytes("png")))
            raw  = _infer(ft_model, ft_proc, img, PROMPT_FT.format(prev=prev_ft))
            pred = _parse(raw)
            cls, pos = pred.get("class"), pred.get("position")
            fields = {k: v for k, v in pred.items() if k not in ("class","position") and v is not None}
            ft_pages.append({"page": pg_num, "raw": raw, "cls": cls, "pos": pos,
                              "prev": prev_ft, "fields": fields})
            if cls and pos:
                prev_ft = f"{cls} | {pos}"
        pdf.close()
        elapsed_ft = time.time() - t_ft
    else:
        ft_pages = [{"page": r["page"], "raw": "—", "cls": None, "pos": None,
                     "prev": FIRST_PREV, "fields": {}} for r in base_pages]

    # ── Build grouped documents ───────────────────────────────────────────────
    base_docs = _group(base_pages)
    ft_docs   = _group(ft_pages)

    # ── Build HTML sections ───────────────────────────────────────────────────
    ft_available = LORA_PATH.exists()

    stats_html = _agreement_stats(base_pages, ft_pages)

    doc_compare_html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#002E5E,#0070AD);
                border-radius:12px;padding:16px 20px;margin-bottom:16px;
                display:flex;justify-content:space-between;align-items:center">
      <div>
        <div style="color:white;font-size:16px;font-weight:700">✅ Comparison Complete</div>
        <div style="color:rgba(255,255,255,0.8);font-size:12px;margin-top:3px">
          {pdf_name} &nbsp;·&nbsp; {n_pages} page(s)
        </div>
      </div>
      <div style="display:flex;gap:8px">
        <div style="background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);
                    border-radius:6px;padding:6px 12px;color:white;font-size:11px;font-weight:600">
          🔵 Base · ⏱ {elapsed_base:.1f}s
        </div>
        <div style="background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);
                    border-radius:6px;padding:6px 12px;color:white;font-size:11px;font-weight:600">
          🟢 Fine-tuned V2 · ⏱ {elapsed_ft:.1f}s
        </div>
      </div>
    </div>

    <!-- Agreement stats -->
    <div style="font-size:12px;font-weight:700;color:#003F7D;
                border-left:4px solid #00B1C1;padding-left:10px;margin-bottom:10px">
      📊 MODEL AGREEMENT
    </div>
    {stats_html}

    <!-- Document summaries side by side -->
    <div style="font-size:12px;font-weight:700;color:#003F7D;
                border-left:4px solid #00B1C1;padding-left:10px;margin-bottom:12px">
      📂 IDENTIFIED DOCUMENTS
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px">
      <div style="background:#f8fafc;border-radius:10px;padding:12px">
        {_doc_column(base_docs, "🔵 BASE MODEL", "#0070AD", elapsed_base)}
      </div>
      <div style="background:#f0fdf4;border-radius:10px;padding:12px">
        {_doc_column(ft_docs, "🟢 FINE-TUNED V2", "#16a34a", elapsed_ft)}
      </div>
    </div>

    <!-- Per-page comparison -->
    <div style="font-size:12px;font-weight:700;color:#003F7D;
                border-left:4px solid #00B1C1;padding-left:10px;margin-bottom:10px">
      📑 PAGE-BY-PAGE COMPARISON
    </div>
    <div style="font-size:10px;color:#64748b;margin-bottom:8px">
      ✅ Both agree &nbsp; 🟡 Class agree, position differs &nbsp;
      🟠 Position agree, class differs &nbsp; ❌ Both differ
    </div>
    {_comparison_table(base_pages, ft_pages)}

    </div>"""

    # ── JSON export ───────────────────────────────────────────────────────────
    export = {
        "pdf":    pdf_name,
        "n_pages": n_pages,
        "base_model": {
            "path":      str(MODEL_PATH),
            "elapsed_s": round(elapsed_base, 1),
            "documents": [
                {"doc": i, "class": d["class"],
                 "page_start": d["page_start"], "page_end": d["page_end"],
                 "n_pages": d["n_pages"], "fields": d.get("fields", {})}
                for i, d in enumerate(base_docs, 1)
            ],
            "pages": [
                {"page": r["page"], "class": r["cls"], "position": r["pos"],
                 "fields": r["fields"], "raw": r["raw"]}
                for r in base_pages
            ],
        },
        "finetuned_model": {
            "path":      str(LORA_PATH) if ft_available else "not found",
            "elapsed_s": round(elapsed_ft, 1),
            "documents": [
                {"doc": i, "class": d["class"],
                 "page_start": d["page_start"], "page_end": d["page_end"],
                 "n_pages": d["n_pages"], "fields": d.get("fields", {})}
                for i, d in enumerate(ft_docs, 1)
            ],
            "pages": [
                {"page": r["page"], "class": r["cls"], "position": r["pos"],
                 "fields": r["fields"], "raw": r["raw"]}
                for r in ft_pages
            ],
        },
    }

    return stats_html, doc_compare_html, json.dumps(export, indent=2)


# ── CSS ───────────────────────────────────────────────────────────────────────
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
.btn-compare {
    background: linear-gradient(135deg, #002E5E, #0070AD) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    padding: 14px 32px !important;
    width: 100% !important;
    box-shadow: 0 3px 12px rgba(0,63,125,0.35) !important;
    cursor: pointer !important;
}
.btn-compare:hover {
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
"""


# ── Gradio UI ─────────────────────────────────────────────────────────────────
def build_app():
    ft_ready = LORA_PATH.exists()
    ft_badge = (
        "<span style='background:#f0fdf4;border:1px solid #86efac;color:#166534;"
        "border-radius:4px;padding:2px 8px;font-size:10px;font-weight:600'>V2 READY</span>"
        if ft_ready else
        "<span style='background:#fffbeb;border:1px solid #fcd34d;color:#92400e;"
        "border-radius:4px;padding:2px 8px;font-size:10px;font-weight:600'>NOT FOUND</span>"
    )

    with gr.Blocks(css=CSS, title="DHL Model Comparison | Capgemini") as app:

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
              DHL Document Intelligence — Model Comparison
            </div>
            <div style="font-size:12px;color:rgba(255,255,255,0.75);margin-top:2px">
              Base Model vs V2 Fine-tuned · Classification · Extraction · Splitting
            </div>
          </div>
          <div style="text-align:right;display:flex;flex-direction:column;gap:6px">
            <div style="background:rgba(59,130,246,0.2);border:1px solid rgba(147,197,253,0.5);
                        border-radius:8px;padding:6px 14px;color:white;font-size:11px">
              🔵 Base: Qwen2.5-VL-3B-Instruct
            </div>
            <div style="background:rgba(34,197,94,0.2);border:1px solid rgba(134,239,172,0.5);
                        border-radius:8px;padding:6px 14px;color:white;font-size:11px">
              🟢 Fine-tuned V2 (LoRA) &nbsp; {ft_badge}
            </div>
          </div>
        </div>
        """)

        with gr.Row():
            with gr.Column(scale=3):
                gr.HTML("""
                <div style="font-size:13px;font-weight:600;color:#003F7D;margin-bottom:6px">
                  📄 Upload PDF Document
                </div>
                <div style="font-size:11px;color:#64748b;margin-bottom:8px">
                  Upload any DHL logistics PDF. Both models will process every page and
                  their outputs will be compared side by side.
                </div>""")
                pdf_input = gr.File(label="", file_types=[".pdf"],
                                    elem_classes=["upload-zone"])

            with gr.Column(scale=1):
                gr.HTML("<div style='height:46px'></div>")
                compare_btn = gr.Button("⚖️  Compare Models", elem_classes=["btn-compare"])
                gr.HTML("<div style='height:8px'></div>")
                clear_btn   = gr.Button("✕  Clear", elem_classes=["btn-clear"])
                gr.HTML("""
                <div style="margin-top:14px;padding:10px 12px;background:white;
                            border:1px solid #e2e8f0;border-radius:8px;
                            font-size:11px;color:#64748b;line-height:1.7">
                  <b style="color:#003F7D">Process:</b><br>
                  1. Base model runs all pages<br>
                  2. Fine-tuned V2 runs all pages<br>
                  3. Results compared side by side<br>
                  <span style="color:#94a3b8">⚠ ~2× inference time vs single model</span>
                </div>""")

        gr.HTML("""
        <div style="font-size:14px;font-weight:700;color:#003F7D;
                    border-left:4px solid #00B1C1;padding-left:10px;margin:16px 0 10px">
          Comparison Results
        </div>""")

        result_html = gr.HTML(
            "<div style='background:white;border:1px solid #e2e8f0;border-radius:12px;"
            "padding:40px;text-align:center;color:#94a3b8;font-family:Segoe UI'>"
            "<div style='font-size:40px;margin-bottom:12px'>⚖️</div>"
            "<div style='font-size:14px;font-weight:600'>Upload a PDF to compare both models</div>"
            "<div style='font-size:12px;margin-top:6px'>Agreement stats, document cards, "
            "and per-page comparison will appear here</div>"
            "</div>"
        )

        with gr.Accordion("⬇️  Export Full Results as JSON", open=False):
            json_output = gr.Code(language="json", label="", value="", lines=18)

        gr.HTML("""
        <div style="text-align:center;color:#94a3b8;font-size:11px;
                    margin-top:20px;padding-top:16px;border-top:1px solid #e2e8f0">
          Capgemini &nbsp;·&nbsp; DHL Document Intelligence &nbsp;·&nbsp;
          Base vs V2 Fine-tuned &nbsp;·&nbsp; Qwen2.5-VL-3B + LoRA
        </div>""")

        compare_btn.click(
            fn=process_pdf,
            inputs=[pdf_input],
            outputs=[result_html, result_html, json_output],
        )

        clear_btn.click(
            fn=lambda: (
                "<div style='background:white;border:1px solid #e2e8f0;border-radius:12px;"
                "padding:40px;text-align:center;color:#94a3b8;font-family:Segoe UI'>"
                "<div style='font-size:40px;margin-bottom:12px'>⚖️</div>"
                "<div style='font-size:14px;font-weight:600'>Upload a PDF to compare both models</div>"
                "</div>",
                "",
                None,
            ),
            inputs=[],
            outputs=[result_html, json_output, pdf_input],
        )

    return app


if __name__ == "__main__":
    print("=" * 60)
    print("  DHL Document Intelligence — Model Comparison")
    print("=" * 60)
    print(f"  Base      : Qwen2.5-VL-3B-Instruct")
    print(f"  Fine-tuned: {'V2 LoRA — ' + str(LORA_PATH) if LORA_PATH.exists() else 'NOT FOUND'}")
    print(f"  URL       : http://localhost:7860")
    print(f"  Note      : Do NOT run while train.py is active (VRAM conflict)")
    print("=" * 60)
    build_app().launch(server_name="0.0.0.0", server_port=7860, share=False, show_error=True)
