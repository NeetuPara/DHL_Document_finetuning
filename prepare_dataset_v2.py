"""
DHL Dataset Preparation v2 — Classification + Splitting + Extraction

New output format (JSON label on every page):

  START page  → full JSON with class, position, + 12 universal fields
  CONTINUATION → short JSON with class + position only (header not visible)

12 universal fields extracted from existing annotation JSONs:
  shipper_name, consignee_name, document_date, document_number,
  country_of_origin, country_of_destination, description_of_goods, gross_weight_kg,
  license_number, validity_start, validity_end, licensee_name

description_of_goods = first 3 line items joined, max 80 chars (Option 2)

Output goes to Training_Data_v2/ — existing Training_Data/ is NOT touched.

Run:
    python prepare_dataset_v2.py
    python prepare_dataset_v2.py --no-skip   # re-convert all images
"""

import json, random, time, argparse
from pathlib import Path
from collections import defaultdict, Counter
import fitz

BASE     = Path(__file__).parent
OUT_DIR  = BASE / "Training_Data_v2"
IMG_DIR  = OUT_DIR / "images"           # where images are stored (may be redirected)
IMG_BASE = OUT_DIR                      # base for computing relative paths in JSONL
DPI      = 150
MAT      = fitz.Matrix(DPI/72, DPI/72)

# ── Class registry ────────────────────────────────────────────────────────────
CLASSES = {
    1: "Commercial Invoice",              2: "House Bill of Lading",
    3: "Certificate of Origin",           4: "Shipper's Letter of Instruction",
    5: "Dangerous Goods Declaration",     6: "Verified Gross Mass",
    7: "House Airway Bill",               8: "Packing List",
    9: "Customs Declaration",            10: "Cargo Manifest",
   11: "Import/Export License",          12: "Power of Attorney",
}
CLASS_FOLDERS = {
    1:  "01_Commercial_Invoice",          2:  "02_House_Bill_of_Lading",
    3:  "03_Certificate_of_Origin",       4:  "04_Shippers_Letter_of_Instruction",
    5:  "05_Dangerous_Goods_Declaration", 6:  "06_Verified_Gross_Mass",
    7:  "07_House_Airway_Bill",           8:  "08_Packing_List",
    9:  "09_Customs_Declarations",       10:  "10_Cargo_Manifest",
   11:  "11_Import_Export_License",      12:  "12_Power_of_Attorney",
}
CLASS_TO_FOLDER = {v: CLASS_FOLDERS[k] for k, v in CLASSES.items()}

FIRST_PAGE_PREV      = "none (first page of batch)"
MAX_SINGLE_DOC_PER_CLASS = 250

# ── Universal field mapping ───────────────────────────────────────────────────
# All mappings are grounded in actual annotation JSON keys — no assumptions.
# Verified against annotation files for every class (single-page and multipage).
#
# Values:
#   str              → direct key in annotation["fields"]
#   list[str|tuple]  → try each in order; str = direct key, tuple = (list_field, item_key)
#   tuple            → (list_field, item_key): join first 3 items' item_key values, max 80 chars
#   None             → field has no equivalent in this document type → always null
FIELD_MAP = {
    "Commercial Invoice": {
        # single: shipper_name, receiver_name, invoice_date, invoice_number,
        #         shipper_country, receiver_country, line_items[].description,
        #         total_gross_weight_kg, total_net_weight_kg
        # multi:  same keys (line_items confirmed present)
        "shipper_name":           "shipper_name",
        "consignee_name":         "receiver_name",
        "document_date":          "invoice_date",
        "document_number":        "invoice_number",
        "country_of_origin":      "shipper_country",
        "country_of_destination": "receiver_country",
        "description_of_goods":   ("line_items", "description"),
        "gross_weight_kg":        "total_gross_weight_kg",
        "net_weight_kg":          "total_net_weight_kg",
        "total_weight_kg":        None,
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "House Bill of Lading": {
        # single: shipper_name, consignee_name, issue_date, bl_number,
        #         shipper_country, consignee_country, description_of_goods,
        #         gross_weight_kg, net_weight_kg
        # multi:  shipper_name, consignee_name, date, bl_number,
        #         pol (port of loading), pod (port of discharge), total_gross_wt_kg
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          ["issue_date", "date"],
        "document_number":        "bl_number",
        "country_of_origin":      ["shipper_country", "pol"],
        "country_of_destination": ["consignee_country", "pod"],
        "description_of_goods":   "description_of_goods",
        "gross_weight_kg":        ["gross_weight_kg", "total_gross_wt_kg"],
        "net_weight_kg":          "net_weight_kg",
        "total_weight_kg":        None,
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Certificate of Origin": {
        # single: exporter_name, consignee_name, issue_date, document_number,
        #         country_of_origin, country_of_destination, goods[].description
        #         (no total weight — only per-item Net Wt shown on document)
        "shipper_name":           "exporter_name",
        "consignee_name":         "consignee_name",
        "document_date":          "issue_date",
        "document_number":        "document_number",
        "country_of_origin":      "country_of_origin",
        "country_of_destination": "country_of_destination",
        "description_of_goods":   ("goods", "description"),
        "gross_weight_kg":        None,
        "net_weight_kg":          None,
        "total_weight_kg":        None,
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Shipper's Letter of Instruction": {
        # single: usppi_name, consignee_name, reference, usppi_country, destination_country,
        #         line_items[].description, total_weight_kg
        #         (date rendered on document but not stored in current annotation files → null)
        # multi:  usppi, consignee, reference, destination
        #         (no date, no origin country, no description in multi annotation → null)
        "shipper_name":           ["usppi_name", "usppi"],
        "consignee_name":         ["consignee_name", "consignee"],
        "document_date":          None,
        "document_number":        "reference",
        "country_of_origin":      "usppi_country",
        "country_of_destination": ["destination_country", "destination"],
        "description_of_goods":   ("line_items", "description"),
        "gross_weight_kg":        None,
        "net_weight_kg":          None,
        "total_weight_kg":        "total_weight_kg",
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Dangerous Goods Declaration": {
        # single: shipper_name, consignee_name, signature_date, awb_number,
        #         shipper_country, consignee_country, dg_entries[].proper_name
        #         (no total gross weight — per-entry net quantities in mixed units)
        # multi:  shipper, consignee, date, awb, departure, destination
        #         (multi annotation stores only n_dg_entries count, no entries list → desc null)
        "shipper_name":           ["shipper_name", "shipper"],
        "consignee_name":         ["consignee_name", "consignee"],
        "document_date":          ["signature_date", "flight_date", "date"],
        "document_number":        ["awb_number", "awb"],
        "country_of_origin":      ["shipper_country", "departure"],
        "country_of_destination": ["consignee_country", "destination"],
        "description_of_goods":   [("dg_entries", "proper_name")],
        "gross_weight_kg":        None,
        "net_weight_kg":          None,
        "total_weight_kg":        None,
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Verified Gross Mass": {
        # single: shipper_name, (no consignee), signature_date, bl_number,
        #         shipper_country, port_of_discharge, (no goods description), vgm_kg
        # multi:  shipper, bl, date, pod, total_vgm_kg
        # VGM is inherently a gross mass measurement
        "shipper_name":           ["shipper_name", "shipper"],
        "consignee_name":         None,
        "document_date":          ["signature_date", "date"],
        "document_number":        ["bl_number", "bl", "booking_reference"],
        "country_of_origin":      "shipper_country",
        "country_of_destination": ["port_of_discharge", "pod"],
        "description_of_goods":   None,
        "gross_weight_kg":        ["vgm_kg", "total_vgm_kg"],
        "net_weight_kg":          None,
        "total_weight_kg":        None,
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "House Airway Bill": {
        # single: shipper_name, consignee_name, issue_date, hawb_number,
        #         airport_departure (e.g. "SIN"), airport_destination (e.g. "LHR"),
        #         nature_of_goods, gross_weight_kg
        # NOTE: HAWB shows airport codes/names, not country names — map to airport fields
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          "issue_date",
        "document_number":        "hawb_number",
        "country_of_origin":      "airport_departure",
        "country_of_destination": "airport_destination",
        "description_of_goods":   "nature_of_goods",
        "gross_weight_kg":        "gross_weight_kg",
        "net_weight_kg":          None,
        "total_weight_kg":        None,
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Packing List": {
        # single: shipper_name, consignee_name, date, invoice_number/reference,
        #         (no origin/destination fields), line_items[].description,
        #         total_gross_weight_kg, total_net_weight_kg
        # multi:  same but items[] key instead of line_items[]
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          "date",
        "document_number":        ["invoice_number", "reference"],
        "country_of_origin":      None,
        "country_of_destination": None,
        "description_of_goods":   [("line_items", "description"), ("items", "description")],
        "gross_weight_kg":        "total_gross_weight_kg",
        "net_weight_kg":          "total_net_weight_kg",
        "total_weight_kg":        None,
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Customs Declaration": {
        # single: sender_name, addressee_name, issue_date, reference/tracking_number,
        #         sender_country, addressee_country, line_items[].description, total_weight_kg
        "shipper_name":           "sender_name",
        "consignee_name":         "addressee_name",
        "document_date":          "issue_date",
        "document_number":        ["reference", "tracking_number"],
        "country_of_origin":      "sender_country",
        "country_of_destination": "addressee_country",
        "description_of_goods":   ("line_items", "description"),
        "gross_weight_kg":        None,
        "net_weight_kg":          None,
        "total_weight_kg":        "total_weight_kg",
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Cargo Manifest": {
        # single: (no single shipper/consignee), issue_date, manifest_number,
        #         departure_airport, destination_airport, entries[].description, total_weight_kg
        # multi:  date, manifest_no, from_location, to_location, total_gross_weight_kg
        "shipper_name":           None,
        "consignee_name":         None,
        "document_date":          ["issue_date", "date"],
        "document_number":        ["manifest_number", "manifest_no"],
        "country_of_origin":      ["departure_airport", "from_location"],
        "country_of_destination": ["destination_airport", "port_of_discharge", "to_location"],
        "description_of_goods":   ("entries", "description"),
        "gross_weight_kg":        "total_gross_weight_kg",
        "net_weight_kg":          None,
        "total_weight_kg":        "total_weight_kg",
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Import/Export License": {
        # single: importer_name/usppi_name, consignee_name/ultimate_consignee, entry_date,
        #         entry_number, country_of_origin, destination_country, line_items[].description
        #         (no gross weight field in annotation)
        # multi:  importer, entry_number, date, country_of_origin (no consignee in multi)
        "shipper_name":           ["importer_name", "usppi_name", "importer"],
        "consignee_name":         ["consignee_name", "ultimate_consignee"],
        "document_date":          ["entry_date", "date"],
        "document_number":        "entry_number",
        "country_of_origin":      "country_of_origin",
        "country_of_destination": "destination_country",
        "description_of_goods":   ("line_items", "description"),
        "gross_weight_kg":        None,
        "net_weight_kg":          None,
        "total_weight_kg":        None,
        "license_number":         "license_number",
        "validity_start":         "validity_start",
        "validity_end":           "validity_end",
        "licensee_name":          "licensee_name",
    },
    "Power of Attorney": {
        # single: grantor_name, (no consignee — agent is DHL, not a consignee),
        #         issue_date, poa_reference, grantor_country (all 3 formats — extracted from
        #         address ending or WHEREAS clause), (no destination),
        #         specific_goods (fmt2 only), (no weight — POA is a legal auth document)
        "shipper_name":           "grantor_name",
        "consignee_name":         None,
        "document_date":          "issue_date",
        "document_number":        "poa_reference",
        "country_of_origin":      "grantor_country",
        "country_of_destination": None,
        "description_of_goods":   "specific_goods",
        "gross_weight_kg":        None,
        "net_weight_kg":          None,
        "total_weight_kg":        None,
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
}

UNIVERSAL_FIELDS = [
    "shipper_name", "consignee_name", "document_date", "document_number",
    "country_of_origin", "country_of_destination", "description_of_goods",
    "gross_weight_kg", "net_weight_kg", "total_weight_kg",
    "license_number", "validity_start", "validity_end",
    "licensee_name",
]

# ── Instruction template ──────────────────────────────────────────────────────
CLASS_LIST = ", ".join(CLASSES[i] for i in range(1, 13))

INSTRUCTION_TMPL = (
    "Analyze this DHL logistics document page.\n\n"
    "Previous page: {prev}\n\n"
    "Output a single JSON line.\n\n"
    "If this is the START (first page of a new document):\n"
    '  {{"class": "...", "position": "START", '
    '"shipper_name": "...", "consignee_name": "...", '
    '"document_date": "...", "document_number": "...", '
    '"country_of_origin": "...", "country_of_destination": "...", '
    '"description_of_goods": "...", '
    '"gross_weight_kg": ..., "net_weight_kg": ..., "total_weight_kg": ..., '
    '"license_number": "...", "validity_start": "...", '
    '"validity_end": "...", "licensee_name": "..."}}\n\n'
    "If this is a CONTINUATION (same document continues from previous page):\n"
    '  {{"class": "...", "position": "CONTINUATION"}}\n\n'
    f"Document classes: {CLASS_LIST}\n\n"
    "Use null for weight fields not labeled as gross, net, or total on this page. "
    "Use null for all other fields not visible on this page."
)


# ── Field extraction helpers ──────────────────────────────────────────────────
def _get_description_list(items: list, item_key: str) -> str | None:
    """Join first 3 items' item_key values, max 80 chars (Option 2)."""
    if not items or not isinstance(items, list):
        return None
    descs = [str(i.get(item_key, "")) for i in items[:3] if i.get(item_key)]
    text  = ", ".join(descs)
    return text[:80] if text else None


def extract_fields(ann_fields: dict, doc_class: str) -> dict:
    """Extract 8 universal fields from annotation fields dict using FIELD_MAP."""
    mapping = FIELD_MAP.get(doc_class, {})
    result  = {}

    for ukey, source in mapping.items():
        if source is None:
            result[ukey] = None

        elif isinstance(source, str):
            result[ukey] = ann_fields.get(source)

        elif isinstance(source, list):
            # Each element can be:
            #   str         → direct key lookup
            #   tuple       → (list_field, item_key) joined description
            # Use first element that yields a non-None/non-empty value.
            val = None
            for s in source:
                if isinstance(s, tuple):
                    list_field, item_key = s
                    items = ann_fields.get(list_field, [])
                    v = _get_description_list(items, item_key)
                else:
                    v = ann_fields.get(s)
                if v is not None and v != "":
                    val = v
                    break
            result[ukey] = val

        elif isinstance(source, tuple):
            # (list_field, item_key) → first 3 items' values joined
            list_field, item_key = source
            items = ann_fields.get(list_field, [])
            result[ukey] = _get_description_list(items, item_key)

    # Normalise all weight fields to float
    for wkey in ("gross_weight_kg", "net_weight_kg", "total_weight_kg"):
        wt = result.get(wkey)
        if wt is not None:
            try:
                result[wkey] = round(float(wt), 2)
            except (TypeError, ValueError):
                result[wkey] = None

    return result


def load_annotation(doc_class: str, stem: str, is_multipage: bool = False) -> dict | None:
    """Load annotation fields dict for a given document stem."""
    folder = CLASS_TO_FOLDER.get(doc_class)
    if not folder:
        return None
    base = BASE / ("Synthetic_Data_MultiPage" if is_multipage else "Synthetic_Data")
    path = base / folder / "annotations" / f"{stem}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data.get("fields", data)
    except Exception:
        return None


def build_label(doc_class: str, position: str, ann_fields: dict | None) -> str:
    """
    Build the JSON label string.
    START pages: full JSON with 8 extracted fields.
    CONTINUATION pages: short JSON with class + position only.
    """
    if position == "CONTINUATION" or ann_fields is None:
        obj = {"class": doc_class, "position": "CONTINUATION"}
    else:
        fields = extract_fields(ann_fields, doc_class)
        obj = {"class": doc_class, "position": "START"}
        obj.update(fields)

    return json.dumps(obj, ensure_ascii=False)


# ── Example builder ───────────────────────────────────────────────────────────
def make_example(img_rel: str, label: str, source: str,
                 prev_label: str = FIRST_PAGE_PREV) -> dict:
    return {
        "messages": [
            {"role": "user", "content": [
                {"type": "image"},
                {"type": "text", "text": INSTRUCTION_TMPL.format(prev=prev_label)},
            ]},
            {"role": "assistant", "content": label},
        ],
        "image":      img_rel,
        "label":      label,
        "prev_label": prev_label,
        "source":     source,
    }


# ── Image conversion ──────────────────────────────────────────────────────────
def pdf_to_pngs(pdf_path: Path, out_folder: Path, stem: str,
                skip_existing: bool = True) -> list[Path]:
    paths = []
    try:
        doc = fitz.open(str(pdf_path))
        for i, page in enumerate(doc, 1):
            img_path = out_folder / f"{stem}_p{i}.png"
            if skip_existing and img_path.exists():
                paths.append(img_path)
                continue
            pix = page.get_pixmap(matrix=MAT)
            pix.save(str(img_path))
            paths.append(img_path)
        doc.close()
    except Exception as e:
        print(f"  ERROR: {pdf_path.name} — {e}")
    return paths


# ── Step 1: single-page docs ──────────────────────────────────────────────────
def step1_single_docs(examples: list, skip_existing: bool = True):
    print(f"\n[STEP 1/3] Single-doc PDFs — cap {MAX_SINGLE_DOC_PER_CLASS}/class ...")
    synth = BASE / "Synthetic_Data"
    total = 0
    for idx, folder_name in CLASS_FOLDERS.items():
        cls    = CLASSES[idx]
        pdf_d  = synth / folder_name / "pdfs"
        if not pdf_d.exists():
            continue
        img_d  = IMG_DIR / "single" / folder_name
        img_d.mkdir(parents=True, exist_ok=True)

        pdfs = sorted(pdf_d.rglob("*.pdf"))
        all_imgs = []
        for pdf in pdfs:
            all_imgs.extend(pdf_to_pngs(pdf, img_d, pdf.stem, skip_existing))

        random.shuffle(all_imgs)
        sampled = all_imgs[:MAX_SINGLE_DOC_PER_CLASS]

        for img in sampled:
            stem      = img.stem.rsplit("_p", 1)[0]          # strip _p1
            ann_fields = load_annotation(cls, stem)
            label     = build_label(cls, "START", ann_fields)
            rel       = img.relative_to(IMG_BASE).as_posix()
            examples.append(make_example(rel, label, "single_doc", FIRST_PAGE_PREV))

        total += len(sampled)
        print(f"  {folder_name:<45} {len(pdfs):>5} PDFs ->{len(sampled)} sampled")

    print(f"  Subtotal: {total:,} examples")
    return total


# ── Step 2: multi-page docs ───────────────────────────────────────────────────
def step2_multipage_docs(examples: list, skip_existing: bool = True):
    print("\n[STEP 2/3] Multi-page docs (Synthetic_Data_MultiPage/) ...")
    mp = BASE / "Synthetic_Data_MultiPage"
    total_s = total_c = 0

    for folder in sorted(mp.iterdir()):
        if not folder.is_dir():
            continue
        pdf_d = folder / "pdfs"
        if not pdf_d.exists():
            continue
        cls = next((CLASSES[k] for k, v in CLASS_FOLDERS.items()
                    if v == folder.name), None)
        if cls is None:
            continue

        img_d = IMG_DIR / "multi" / folder.name
        img_d.mkdir(parents=True, exist_ok=True)
        pdfs  = sorted(pdf_d.rglob("*.pdf"))
        s = c = 0

        for pdf in pdfs:
            stem      = pdf.stem                              # e.g. ci_mp_0001
            ann_fields = load_annotation(cls, stem, is_multipage=True)
            imgs      = pdf_to_pngs(pdf, img_d, stem, skip_existing)
            prev      = FIRST_PAGE_PREV

            for pg_num, img in enumerate(imgs, 1):
                position = "START" if pg_num == 1 else "CONTINUATION"
                label    = build_label(cls, position, ann_fields)
                rel      = img.relative_to(IMG_BASE).as_posix()
                examples.append(make_example(rel, label, "multi_doc", prev))
                prev = f"{cls} | {position}"  # simple format for next page context
                if position == "START": s += 1
                else:                   c += 1

        total_s += s; total_c += c
        if s + c > 0:
            print(f"  {folder.name:<45} {len(pdfs):>4} docs ->{s} START + {c} CONTINUATION")

    print(f"  Subtotal: {total_s:,} START + {total_c:,} CONTINUATION = {total_s+total_c:,}")
    return total_s + total_c


# ── Step 3: splitting packets ─────────────────────────────────────────────────
def step3_splitting_packets(examples: list, skip_existing: bool = True):
    print("\n[STEP 3/3] Splitting packets (Synthetic_Data_Splitting_v2/) ...")
    sp    = BASE / "Synthetic_Data_Splitting_v2"
    pdf_d = sp / "pdfs"
    ann_d = sp / "annotations"
    img_d = IMG_DIR / "packets"
    img_d.mkdir(parents=True, exist_ok=True)

    pdfs       = sorted(pdf_d.glob("*.pdf")) if pdf_d.exists() else []
    total_s    = total_c = 0
    ann_miss   = 0                             # count annotation lookup failures

    for i, pdf in enumerate(pdfs):
        ann_f = ann_d / (pdf.stem + ".json")
        if not ann_f.exists():
            continue
        pkt_ann = json.loads(ann_f.read_text())
        docs    = pkt_ann.get("documents", [])

        # Build page → (doc_class, source_stem, is_multipage) mapping
        page_info: dict[int, tuple] = {}
        for doc in docs:
            cls       = doc["doc_class"]
            src_stem  = Path(doc["source_file"]).stem
            is_mp     = doc.get("is_multipage_doc", False)
            for pg in range(doc["page_start"], doc["page_end"] + 1):
                position = "START" if pg == doc["page_start"] else "CONTINUATION"
                page_info[pg] = (cls, src_stem, is_mp, position)

        # Build prev chain
        page_prev: dict[int, str] = {}
        prev = FIRST_PAGE_PREV
        for pg_num in sorted(page_info.keys()):
            page_prev[pg_num] = prev
            cls, _, _, pos = page_info[pg_num]
            prev = f"{cls} | {pos}"

        # Pre-load annotation per source document (cache within packet)
        ann_cache: dict[str, dict | None] = {}
        for doc in docs:
            cls      = doc["doc_class"]
            src_stem = Path(doc["source_file"]).stem
            is_mp    = doc.get("is_multipage_doc", False)
            key      = (cls, src_stem, is_mp)
            if key not in ann_cache:
                ann_cache[key] = load_annotation(cls, src_stem, is_mp)
                if ann_cache[key] is None:
                    ann_miss += 1

        imgs = pdf_to_pngs(pdf, img_d, pdf.stem, skip_existing)
        for pg_num, img in enumerate(imgs, 1):
            if pg_num not in page_info:
                continue
            cls, src_stem, is_mp, position = page_info[pg_num]
            ann_fields = ann_cache.get((cls, src_stem, is_mp))
            label      = build_label(cls, position, ann_fields)
            prev       = page_prev.get(pg_num, FIRST_PAGE_PREV)
            rel        = img.relative_to(IMG_BASE).as_posix()
            examples.append(make_example(rel, label, "splitting_packet", prev))

            if position == "START": total_s += 1
            else:                   total_c += 1

        if (i + 1) % 500 == 0 or i < 3:
            print(f"  [{i+1:>5}/{len(pdfs)}] {pdf.stem}  "
                  f"{pkt_ann['total_pages']}pp  {len(docs)} docs")

    print(f"  Subtotal: {total_s:,} START + {total_c:,} CONTINUATION  "
          f"(annotation misses: {ann_miss})")
    return total_s + total_c


# ── Split helpers ─────────────────────────────────────────────────────────────
def doc_key(img_rel: str) -> str:
    parts = img_rel.split("/")
    if len(parts) >= 3 and parts[1] == "packets":
        return "images/packets/" + parts[2].rsplit("_p", 1)[0]
    stem = parts[-1].rsplit("_p", 1)[0]
    return "/".join(parts[:-1]) + "/" + stem


def split_dataset(examples: list, seed: int = 42):
    random.seed(seed)
    by_doc = defaultdict(list)
    for ex in examples:
        by_doc[doc_key(ex["image"])].append(ex)
    docs  = list(by_doc.keys())
    random.shuffle(docs)
    n     = len(docs)
    n_tr  = int(n * 0.80)
    n_va  = int(n * 0.10)
    tr_set = set(docs[:n_tr])
    va_set = set(docs[n_tr:n_tr + n_va])
    train, val, test = [], [], []
    for ex in examples:
        k = doc_key(ex["image"])
        if   k in tr_set: train.append(ex)
        elif k in va_set: val.append(ex)
        else:             test.append(ex)
    return train, val, test


def write_jsonl(examples: list, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")


def print_split_stats(examples: list, name: str):
    pos = Counter()
    cls = Counter()
    for ex in examples:
        try:
            obj = json.loads(ex["label"])
            pos[obj.get("position", "?")] += 1
            cls[obj.get("class", "?")] += 1
        except Exception:
            pos["PARSE_ERROR"] += 1
    total = len(examples)
    print(f"\n  {name}: {total:,} examples")
    print(f"    START={pos['START']:,}  CONTINUATION={pos['CONTINUATION']:,}")
    for c, n in sorted(cls.items(), key=lambda x: -x[1]):
        print(f"    {c:<42} {n:>7,}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main(skip_existing: bool = True):
    global IMG_DIR, IMG_BASE
    existing_img = BASE / "Training_Data" / "images"
    if existing_img.exists():
        # Reuse existing images from Training_Data/ — no re-conversion needed.
        # IMG_DIR  → where images physically are
        # IMG_BASE → root used to compute relative paths in JSONL records
        #            must match what train.py's IMG_DIR points to (Training_Data/)
        IMG_DIR  = existing_img
        IMG_BASE = BASE / "Training_Data"
        print("Reusing images from Training_Data/images/ (no re-conversion needed)")
    else:
        IMG_DIR  = OUT_DIR / "images"
        IMG_BASE = OUT_DIR

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("DHL Dataset Preparation v2 — Classification + Splitting + Extraction")
    print(f"Output: {OUT_DIR}")
    print("=" * 65)

    t0       = time.time()
    examples = []

    step1_single_docs(examples,       skip_existing)
    step2_multipage_docs(examples,    skip_existing)
    step3_splitting_packets(examples, skip_existing)

    elapsed = time.time() - t0
    print(f"\n{'='*65}")
    print(f"Total examples: {len(examples):,}  ({elapsed/60:.1f} min)")

    pos = Counter()
    src = Counter()
    for ex in examples:
        try:
            obj = json.loads(ex["label"])
            pos[obj.get("position", "?")] += 1
        except Exception:
            pass
        src[ex["source"]] += 1
    print(f"Position: START={pos['START']:,}  CONTINUATION={pos['CONTINUATION']:,}")
    print(f"Source:   {dict(src)}")

    # Verify extraction — show 3 sample START labels
    print("\nSample START labels (extraction check):")
    shown = 0
    for ex in examples:
        try:
            obj = json.loads(ex["label"])
            if obj.get("position") == "START" and shown < 3:
                print(f"  {obj['class']}: {json.dumps({k: v for k, v in obj.items() if k not in ('class','position')}, ensure_ascii=False)[:120]}")
                shown += 1
        except Exception:
            pass

    train, val, test = split_dataset(examples)
    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)

    print_split_stats(train, "TRAIN (80%)")
    print_split_stats(val,   "VAL   (10%)")
    print_split_stats(test,  "TEST  (10%)")

    write_jsonl(train, OUT_DIR / "train.jsonl")
    write_jsonl(val,   OUT_DIR / "val.jsonl")
    write_jsonl(test,  OUT_DIR / "test.jsonl")

    stats = {
        "total": len(examples), "train": len(train),
        "val": len(val), "test": len(test),
        "start_count": pos["START"], "continuation_count": pos["CONTINUATION"],
        "source_counts": dict(src), "dpi": DPI,
        "elapsed_minutes": round(elapsed / 60, 1),
        "version": "v2_extraction",
    }
    (OUT_DIR / "dataset_stats.json").write_text(json.dumps(stats, indent=2))

    print(f"\nSaved to {OUT_DIR}/")
    print(f"  train.jsonl : {len(train):,}")
    print(f"  val.jsonl   : {len(val):,}")
    print(f"  test.jsonl  : {len(test):,}")
    print()
    print("To use this dataset for training, update train_config.yaml:")
    print('  paths:')
    print('    train_data: "Training_Data_v2/train.jsonl"')
    print('    val_data:   "Training_Data_v2/val.jsonl"')
    print('    image_base: "Training_Data"   # images still in Training_Data/')


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-skip", action="store_true",
                   help="Re-convert PDFs even if images exist")
    args = p.parse_args()
    main(skip_existing=not args.no_skip)
