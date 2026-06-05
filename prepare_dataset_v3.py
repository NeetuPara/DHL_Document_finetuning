"""
DHL Dataset Preparation v3 — Classification + Splitting + Extraction + Blank Forms

Changes from v2:
  1. Weight fields removed (gross_weight_kg, net_weight_kg, total_weight_kg) from
     UNIVERSAL_FIELDS, FIELD_MAP (all 12 classes), INSTRUCTION_TMPL, and extract_fields().
  2. Output directory changed to Training_Data_v3/; version string "v3_extraction".
  3. Two new processing steps added:
       step4_real_blank_docs  — processes real blank PDFs from Documents/
       step5_synthetic_blank_docs — generates synthetic blank forms via ReportLab
     Both use BLANK_FORM_LABELS for form structure and build_blank_label() for labels.

Output format (JSON label on every page):

  START page  → full JSON with class, position, + universal fields (no weight fields)
  CONTINUATION → short JSON with class + position only (header not visible)

Universal fields (9, down from 12 — weight fields removed):
  shipper_name, consignee_name, document_date, document_number,
  country_of_origin, country_of_destination, description_of_goods,
  license_number, validity_start, validity_end, licensee_name

description_of_goods = first 3 line items joined, max 80 chars (Option 2)

Output goes to Training_Data_v3/ — existing Training_Data/ is NOT touched.

Run:
    python prepare_dataset_v3.py
    python prepare_dataset_v3.py --no-skip   # re-convert all images
"""

import json, random, time, argparse
from pathlib import Path
from collections import defaultdict, Counter
import fitz

BASE     = Path(__file__).parent
OUT_DIR  = BASE / "Training_Data_v3"
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
        #         shipper_country, receiver_country, line_items[].description
        # multi:  same keys (line_items confirmed present)
        "shipper_name":           "shipper_name",
        "consignee_name":         "receiver_name",
        "document_date":          "invoice_date",
        "document_number":        "invoice_number",
        "country_of_origin":      "shipper_country",
        "country_of_destination": "receiver_country",
        "description_of_goods":   ("line_items", "description"),
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "House Bill of Lading": {
        # single: shipper_name, consignee_name, issue_date, bl_number,
        #         shipper_country, consignee_country, description_of_goods
        # multi:  shipper_name, consignee_name, date, bl_number,
        #         pol (port of loading), pod (port of discharge)
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          ["issue_date", "date"],
        "document_number":        "bl_number",
        "country_of_origin":      ["shipper_country", "pol"],
        "country_of_destination": ["consignee_country", "pod"],
        "description_of_goods":   "description_of_goods",
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Certificate of Origin": {
        # single: exporter_name, consignee_name, issue_date, document_number,
        #         country_of_origin, country_of_destination, goods[].description
        # FTA variants also have blanket_period_from / blanket_period_to (validity dates)
        "shipper_name":           "exporter_name",
        "consignee_name":         "consignee_name",
        "document_date":          "issue_date",
        "document_number":        "document_number",
        "country_of_origin":      "country_of_origin",
        "country_of_destination": "country_of_destination",
        "description_of_goods":   ("goods", "description"),
        "license_number":         None,
        "validity_start":         "blanket_period_from",
        "validity_end":           "blanket_period_to",
        "licensee_name":          None,
    },
    "Shipper's Letter of Instruction": {
        # single: usppi_name, consignee_name, reference, usppi_country, destination_country,
        #         line_items[].description, license_number (confirmed present in annotations)
        # multi:  usppi, consignee, reference, destination
        # NOTE: no document_date field exists in SLI annotations (verified)
        "shipper_name":           ["usppi_name", "usppi"],
        "consignee_name":         ["consignee_name", "consignee"],
        "document_date":          None,
        "document_number":        "reference",
        "country_of_origin":      "usppi_country",
        "country_of_destination": ["destination_country", "destination"],
        "description_of_goods":   ("line_items", "description"),
        "license_number":         "license_number",
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Dangerous Goods Declaration": {
        # single: shipper_name, consignee_name, signature_date, awb_number,
        #         shipper_country, consignee_country, dg_entries[].proper_name
        # multi:  shipper, consignee, date, awb, departure, destination
        "shipper_name":           ["shipper_name", "shipper"],
        "consignee_name":         ["consignee_name", "consignee"],
        "document_date":          ["signature_date", "flight_date", "date"],
        "document_number":        ["awb_number", "awb"],
        "country_of_origin":      ["shipper_country", "departure"],
        "country_of_destination": ["consignee_country", "destination"],
        "description_of_goods":   [("dg_entries", "proper_name")],
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Verified Gross Mass": {
        # single: shipper_name, (no consignee), signature_date, bl_number,
        #         shipper_country, port_of_loading, (no goods description)
        # multi:  shipper, bl, date
        # port_of_loading confirmed in all VGM single variants.
        # port_of_discharge confirmed in vgm_0003 (Carrier-Terminal-Submission) + multipage "pod".
        # packages[].description confirmed in vgm_0002 (Method2-Sum-of-Packages).
        "shipper_name":           ["shipper_name", "shipper"],
        "consignee_name":         None,
        "document_date":          ["signature_date", "date"],
        "document_number":        ["bl_number", "bl", "booking_reference"],
        "country_of_origin":      ["shipper_country", "port_of_loading"],
        "country_of_destination": ["port_of_discharge", "pod"],
        "description_of_goods":   ("packages", "description"),
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "House Airway Bill": {
        # single: shipper_name, consignee_name, issue_date, hawb_number,
        #         airport_departure (e.g. "SIN"), airport_destination (e.g. "LHR"),
        #         nature_of_goods
        # NOTE: HAWB shows airport codes/names, not country names — map to airport fields
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          "issue_date",
        "document_number":        "hawb_number",
        "country_of_origin":      "airport_departure",
        "country_of_destination": "airport_destination",
        "description_of_goods":   "nature_of_goods",
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Packing List": {
        # single: shipper_name, consignee_name, date, invoice_number/reference,
        #         (no origin/destination fields), line_items[].description
        # multi:  same but items[] key instead of line_items[]
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          "date",
        "document_number":        ["invoice_number", "reference"],
        "country_of_origin":      None,
        "country_of_destination": None,
        "description_of_goods":   [("line_items", "description"), ("items", "description")],
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Customs Declaration": {
        # single: sender_name, addressee_name, issue_date, reference/tracking_number,
        #         sender_country, addressee_country, line_items[].description
        # sender_country exists in US-CBP informal entry variant as top-level key.
        # CN23/UPU variants embed it in sender_address — use line_items[].country_of_origin fallback.
        # addressee_country IS a top-level key in all CN23 variants → destination works correctly.
        "shipper_name":           "sender_name",
        "consignee_name":         "addressee_name",
        "document_date":          "issue_date",
        "document_number":        ["reference", "tracking_number"],
        "country_of_origin":      ["sender_country", ("line_items", "country_of_origin")],
        "country_of_destination": "addressee_country",
        "description_of_goods":   ("line_items", "description"),
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Cargo Manifest": {
        # single: (no single shipper/consignee), issue_date, manifest_number,
        #         departure_airport, destination_airport, entries[].description
        # multi:  date, manifest_no, from_location, to_location
        "shipper_name":           None,
        "consignee_name":         None,
        "document_date":          ["issue_date", "date"],
        "document_number":        ["manifest_number", "manifest_no"],
        # departure_airport = air manifests; port_of_loading = ocean manifests (confirmed present)
        # destination_airport = air; port_of_discharge = ocean (confirmed present)
        "country_of_origin":      ["departure_airport", "port_of_loading", "from_location"],
        "country_of_destination": ["destination_airport", "port_of_discharge", "to_location"],
        "description_of_goods":   ("entries", "description"),
        "license_number":         None,
        "validity_start":         None,
        "validity_end":           None,
        "licensee_name":          None,
    },
    "Import/Export License": {
        # 3 format variants verified against actual annotations:
        #   CBP-Entry-Summary-7501: entry_number, entry_date, importer_name, country_of_origin (top-level)
        #   US-SED-EEI-Export-Filing: usppi_name, ultimate_consignee, export_date, itn_number,
        #                              destination_country, line_items[].country_of_origin (no top-level)
        #   Import-Export-License-Document: license_number, licensee_name, validity_start/end,
        #                                   authorized_commodity (no entry_number, no line_items)
        # "importer" and "date" do NOT exist in any IEL annotation — confirmed by file audit
        "shipper_name":           ["importer_name", "usppi_name"],
        "consignee_name":         ["consignee_name", "ultimate_consignee"],
        "document_date":          ["entry_date", "export_date"],
        "document_number":        ["entry_number", "itn_number", "license_number"],
        "country_of_origin":      ["country_of_origin", ("line_items", "country_of_origin")],
        "country_of_destination": "destination_country",
        "description_of_goods":   [("line_items", "description"), "authorized_commodity"],
        "license_number":         "license_number",
        "validity_start":         "validity_start",
        "validity_end":           "validity_end",
        "licensee_name":          "licensee_name",
    },
    "Power of Attorney": {
        # All 3 format variants verified: grantor_name, grantor_country, issue_date,
        # poa_reference present in all. effective_date/expiry_date present in all formats.
        # specific_goods present in fmt2 (Limited-Specific-POA) only — null for others.
        "shipper_name":           "grantor_name",
        "consignee_name":         None,
        "document_date":          "issue_date",
        "document_number":        "poa_reference",
        "country_of_origin":      "grantor_country",
        "country_of_destination": None,
        "description_of_goods":   "specific_goods",
        "license_number":         None,
        "validity_start":         "effective_date",
        "validity_end":           "expiry_date",
        "licensee_name":          None,
    },
}

UNIVERSAL_FIELDS = [
    "shipper_name", "consignee_name", "document_date", "document_number",
    "country_of_origin", "country_of_destination", "description_of_goods",
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
    '"license_number": "...", "validity_start": "...", '
    '"validity_end": "...", "licensee_name": "..."}}\n\n'
    "If this is a CONTINUATION (same document continues from previous page):\n"
    '  {{"class": "...", "position": "CONTINUATION"}}\n\n'
    f"Document classes: {CLASS_LIST}\n\n"
    "Rules:\n"
    "- Output ONLY values that are clearly printed and readable on this page.\n"
    "- If a field is blank, empty, missing, or you cannot read it, output null.\n"
    "- Do NOT invent, guess, or fill in values from memory.\n"
    "- Use null for all fields not visible on this page."
)

# ── Blank form labels ─────────────────────────────────────────────────────────
BLANK_FORM_LABELS = {
    "Commercial Invoice": {
        "title_variants": ["COMMERCIAL INVOICE", "INVOICE", "EXPORT COMMERCIAL INVOICE", "COMMERCIAL INVOICE / FACTURA COMMERCIAL"],
        "fields": ["Shipper / Exporter", "Consignee / Receiver", "Invoice Date", "Invoice No.", "Country of Origin", "Country of Destination", "Description of Goods"],
    },
    "House Bill of Lading": {
        "title_variants": ["HOUSE BILL OF LADING", "BILL OF LADING", "H.B/L", "HOUSE B/L"],
        "fields": ["Shipper", "Consignee", "Issue Date", "B/L Number", "Port of Loading", "Port of Discharge", "Description of Goods"],
    },
    "Certificate of Origin": {
        "title_variants": ["CERTIFICATE OF ORIGIN", "CERTIFICATE OF ORIGIN (FORM A)", "GSP CERTIFICATE OF ORIGIN"],
        "fields": ["Exporter / Producer", "Consignee", "Date of Issuance", "Reference No.", "Country of Origin", "Country of Destination", "Description of Goods"],
    },
    "Shipper's Letter of Instruction": {
        "title_variants": ["SHIPPER'S LETTER OF INSTRUCTION", "SLI", "EXPORT SHIPPER'S LETTER OF INSTRUCTION"],
        "fields": ["USPPI / Shipper", "Consignee", "SLI Reference No.", "Country of Export", "Country of Destination", "Description of Commodities"],
    },
    "Dangerous Goods Declaration": {
        "title_variants": ["SHIPPER'S DECLARATION FOR DANGEROUS GOODS", "DANGEROUS GOODS DECLARATION", "IATA DANGEROUS GOODS DECLARATION"],
        "fields": ["Shipper", "Consignee", "Date", "Air Waybill No.", "Airport of Departure", "Airport of Destination", "Nature and Quantity of Goods"],
    },
    "Verified Gross Mass": {
        "title_variants": ["VERIFIED GROSS MASS DECLARATION", "VGM DECLARATION", "CONTAINER WEIGHT DECLARATION"],
        "fields": ["Shipper / Cargo Owner", "Issue Date", "B/L No.", "Country of Origin", "Port of Discharge"],
    },
    "House Airway Bill": {
        "title_variants": ["HOUSE AIR WAYBILL", "AIR WAYBILL", "HOUSE AIRWAY BILL", "HAWB"],
        "fields": ["Shipper's Name and Address", "Consignee's Name and Address", "Issue Date", "AWB Number", "Airport of Departure", "Airport of Destination", "Nature and Quantity of Goods"],
    },
    "Packing List": {
        "title_variants": ["PACKING LIST", "EXPORT PACKING LIST", "DETAILED PACKING LIST"],
        "fields": ["Shipper / Exporter", "Consignee", "Date", "Reference / Invoice No.", "Description of Contents"],
    },
    "Customs Declaration": {
        "title_variants": ["CUSTOMS DECLARATION", "CN 23 — CUSTOMS DECLARATION", "CUSTOMS AND POSTAL DECLARATION"],
        "fields": ["Sender's Name and Address", "Addressee / Consignee", "Date", "Reference / Tracking Number", "Country of Origin", "Country of Destination", "Description of Contents"],
    },
    "Cargo Manifest": {
        "title_variants": ["CARGO MANIFEST", "INWARD CARGO MANIFEST", "MARINE CARGO MANIFEST"],
        "fields": ["Issue Date", "Manifest Number", "Airport / Port of Departure", "Airport / Port of Destination", "Description of Cargo"],
    },
    "Import/Export License": {
        "title_variants": ["IMPORT / EXPORT LICENSE", "EXPORT LICENSE", "IMPORT LICENSE"],
        "fields": ["Licensee / Importer Name", "Consignee / Ultimate Consignee", "Issue Date", "Entry Number", "Country of Origin", "Destination Country", "Description of Goods", "License Number", "Validity Start", "Validity End"],
    },
    "Power of Attorney": {
        "title_variants": ["POWER OF ATTORNEY", "CUSTOMS POWER OF ATTORNEY", "LIMITED POWER OF ATTORNEY"],
        "fields": ["Grantor / Principal Name", "Issue Date", "POA Reference Number", "Country of Grantor", "Authorized Agent / Attorney", "Scope of Authorization"],
    },
}

# Folder-to-class mapping for real blank docs in Documents/
DOCS_FOLDER_TO_CLASS = {
    "01_Commercial_Invoice":              "Commercial Invoice",
    "02_House_Bill_of_Lading":            "House Bill of Lading",
    "03_Certificate_of_Origin":           "Certificate of Origin",
    "04_Shippers_Letter_of_Instruction":  "Shipper's Letter of Instruction",
    "05_Dangerous_Goods_Declaration":     "Dangerous Goods Declaration",
    "06_Verified_Gross_Mass":             "Verified Gross Mass",
    "07_House_Airway_Bill":               "House Airway Bill",
    "08_Packing_List":                    "Packing List",
    "09_Customs_Declarations":            "Customs Declaration",
    "10_Cargo_Manifest":                  "Cargo Manifest",
    "11_Import_Export_License":           "Import/Export License",
    "12_Power_of_Attorney":               "Power of Attorney",
}


# ── Field extraction helpers ──────────────────────────────────────────────────
def _get_description_list(items: list, item_key: str) -> str | None:
    """Join first 3 items' item_key values, max 80 chars (Option 2)."""
    if not items or not isinstance(items, list):
        return None
    descs = [str(i.get(item_key, "")) for i in items[:3] if i.get(item_key)]
    text  = ", ".join(descs)
    return text[:80] if text else None


def extract_fields(ann_fields: dict, doc_class: str) -> dict:
    """Extract universal fields from annotation fields dict using FIELD_MAP."""
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
    START pages: full JSON with extracted fields.
    CONTINUATION pages: short JSON with class + position only.
    """
    if position == "CONTINUATION" or ann_fields is None:
        obj = {"class": doc_class, "position": "CONTINUATION"}
    else:
        fields = extract_fields(ann_fields, doc_class)
        obj = {"class": doc_class, "position": "START"}
        obj.update(fields)

    return json.dumps(obj, ensure_ascii=False)


def build_blank_label(cls: str) -> str:
    """Return a JSON string for a blank form: class=cls, position=START, all fields null."""
    obj = {"class": cls, "position": "START"}
    for f in UNIVERSAL_FIELDS:
        obj[f] = None
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


# ── Blank form PDF generator ──────────────────────────────────────────────────
def _generate_blank_pdf(cls: str, out_path: Path, seed: int):
    """Generate a single blank form PDF using ReportLab."""
    from reportlab.lib.pagesizes import A4, LETTER
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.pdfgen import canvas

    rng = random.Random(seed)

    page_size = A4 if seed % 2 == 0 else LETTER
    width, height = page_size

    info = BLANK_FORM_LABELS[cls]
    title_text = info["title_variants"][seed % len(info["title_variants"])]
    fields = info["fields"]

    # Font selection
    fonts = ["Helvetica", "Times-Roman", "Courier"]
    font_name = fonts[seed % len(fonts)]
    bold_font = font_name + "-Bold" if font_name != "Courier" else "Courier-Bold"

    # Font size varies: 10-13pt
    font_size = 10 + (seed % 4)

    style = seed % 4

    c = canvas.Canvas(str(out_path), pagesize=page_size)

    margin_left  = 2.5 * cm
    margin_right = 2.5 * cm
    usable_width = width - margin_left - margin_right

    if style == 0:
        # Style 0: title centered at top with horizontal divider,
        # then "Field Label:  ___________" rows
        y = height - 3 * cm

        # Title centered
        c.setFont(bold_font, font_size + 4)
        c.drawCentredString(width / 2, y, title_text)
        y -= 0.6 * cm

        # Horizontal divider
        c.setLineWidth(1.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 0.8 * cm

        c.setFont(font_name, font_size)
        line_height = (font_size + 6) * 0.0353 * cm  # approx in cm
        line_height = max(line_height, 0.7 * cm)

        for field_label in fields:
            if y < 2 * cm:
                break
            c.setFont(bold_font, font_size)
            label_str = field_label + ":"
            c.drawString(margin_left, y, label_str)
            label_w = c.stringWidth(label_str, bold_font, font_size)
            # Underline for value
            line_x_start = margin_left + label_w + 0.4 * cm
            line_x_end   = width - margin_right
            c.setLineWidth(0.5)
            c.line(line_x_start, y - 0.05 * cm, line_x_end, y - 0.05 * cm)
            y -= line_height + 0.4 * cm

    elif style == 1:
        # Style 1: title in a shaded header rectangle, fields in a simple box/table layout
        # Header rectangle
        header_h = 1.8 * cm
        c.setFillColor(colors.Color(0.2, 0.3, 0.5))
        c.rect(0, height - 2.5 * cm - header_h, width, header_h, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont(bold_font, font_size + 5)
        c.drawCentredString(width / 2, height - 2.5 * cm - header_h + 0.5 * cm, title_text)

        c.setFillColor(colors.black)
        y = height - 2.5 * cm - header_h - 1.0 * cm
        row_h = 1.1 * cm
        col_label_w = usable_width * 0.40
        col_value_w = usable_width * 0.60

        for field_label in fields:
            if y < 2 * cm:
                break
            # Draw box around label cell
            c.setLineWidth(0.5)
            c.setFillColor(colors.Color(0.92, 0.92, 0.95))
            c.rect(margin_left, y - row_h + 0.3 * cm, col_label_w, row_h, fill=1, stroke=1)
            c.setFillColor(colors.black)
            c.setFont(bold_font, font_size - 1)
            c.drawString(margin_left + 0.2 * cm, y - 0.1 * cm, field_label)
            # Draw box for value cell
            c.setFillColor(colors.white)
            c.rect(margin_left + col_label_w, y - row_h + 0.3 * cm, col_value_w, row_h, fill=1, stroke=1)
            c.setFillColor(colors.black)
            y -= row_h + 0.15 * cm

    elif style == 2:
        # Style 2: two-column field layout
        y = height - 2.5 * cm

        # Title
        c.setFont(bold_font, font_size + 3)
        c.drawCentredString(width / 2, y, title_text)
        y -= 0.5 * cm
        c.setLineWidth(1.0)
        c.line(margin_left, y, width - margin_right, y)
        y -= 0.9 * cm

        col_w     = usable_width / 2 - 0.5 * cm
        col2_x    = margin_left + usable_width / 2 + 0.5 * cm
        row_h     = 0.9 * cm
        left_col  = [f for i, f in enumerate(fields) if i % 2 == 0]
        right_col = [f for i, f in enumerate(fields) if i % 2 == 1]
        rows = max(len(left_col), len(right_col))

        for row in range(rows):
            if y < 2 * cm:
                break
            if row < len(left_col):
                c.setFont(bold_font, font_size - 1)
                c.drawString(margin_left, y, left_col[row] + ":")
                c.setLineWidth(0.4)
                c.line(margin_left, y - 0.15 * cm, margin_left + col_w, y - 0.15 * cm)
            if row < len(right_col):
                c.setFont(bold_font, font_size - 1)
                c.drawString(col2_x, y, right_col[row] + ":")
                c.setLineWidth(0.4)
                c.line(col2_x, y - 0.15 * cm, col2_x + col_w, y - 0.15 * cm)
            y -= row_h + 0.3 * cm

    else:
        # Style 3: minimal plain text "FIELD LABEL: _______________" list
        y = height - 3.5 * cm

        c.setFont(font_name, font_size + 2)
        c.drawString(margin_left, y, title_text)
        y -= 0.5 * cm
        c.setLineWidth(0.8)
        c.line(margin_left, y, width - margin_right, y)
        y -= 1.0 * cm

        for field_label in fields:
            if y < 2 * cm:
                break
            c.setFont(font_name, font_size)
            line_str = field_label.upper() + ": " + "_" * 35
            c.drawString(margin_left, y, line_str)
            y -= (font_size + 8) * 0.0353 * cm + 0.3 * cm

    c.save()


# ── Step 1: single-page docs ──────────────────────────────────────────────────
def step1_single_docs(examples: list, skip_existing: bool = True):
    print(f"\n[STEP 1/5] Single-doc PDFs — cap {MAX_SINGLE_DOC_PER_CLASS}/class ...")
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
    print("\n[STEP 2/5] Multi-page docs (Synthetic_Data_MultiPage/) ...")
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
    print("\n[STEP 3/5] Splitting packets (Synthetic_Data_Splitting_v2/) ...")
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


# ── Step 4: real blank docs ───────────────────────────────────────────────────
def step4_real_blank_docs(examples: list, skip_existing: bool = True):
    """Process real blank PDFs from the Documents/ folder."""
    print("\n[STEP 4/5] Real blank docs (Documents/) ...")
    docs_root = BASE / "Documents"
    if not docs_root.exists():
        print(f"  Documents/ folder not found at {docs_root} — skipping.")
        return 0

    total = 0
    for folder_name, cls in DOCS_FOLDER_TO_CLASS.items():
        folder_path = docs_root / folder_name
        if not folder_path.exists():
            continue

        img_d = IMG_DIR / "blank_real" / folder_name
        img_d.mkdir(parents=True, exist_ok=True)

        pdfs = sorted(folder_path.rglob("*.pdf"))
        s = c = 0

        for pdf in pdfs:
            stem = pdf.stem
            imgs = pdf_to_pngs(pdf, img_d, stem, skip_existing)
            prev = FIRST_PAGE_PREV

            for pg_num, img in enumerate(imgs, 1):
                if pg_num == 1:
                    position = "START"
                    label    = build_blank_label(cls)
                else:
                    position = "CONTINUATION"
                    label    = json.dumps({"class": cls, "position": "CONTINUATION"}, ensure_ascii=False)
                rel = img.relative_to(IMG_BASE).as_posix()
                examples.append(make_example(rel, label, "blank_real", prev))
                prev = f"{cls} | {position}"
                if position == "START": s += 1
                else:                   c += 1

        total += s + c
        if s + c > 0:
            print(f"  {folder_name:<45} {len(pdfs):>4} PDFs -> {s} START + {c} CONTINUATION")

    print(f"  Subtotal: {total:,} examples")
    return total


# ── Step 5: synthetic blank docs ─────────────────────────────────────────────
def step5_synthetic_blank_docs(examples: list, skip_existing: bool = True):
    """Generate synthetic blank forms using _generate_blank_pdf()."""
    print("\n[STEP 5/5] Synthetic blank forms (80/class) ...")
    total = 0

    for idx, folder_name in CLASS_FOLDERS.items():
        cls   = CLASSES[idx]
        pdf_d = BASE / "Synthetic_Data_Blank" / folder_name / "pdfs"
        pdf_d.mkdir(parents=True, exist_ok=True)

        img_d = IMG_DIR / "blank_synth" / folder_name
        img_d.mkdir(parents=True, exist_ok=True)

        count = 0
        for seed in range(80):
            img_path = img_d / f"blank_{seed:04d}_p1.png"
            if skip_existing and img_path.exists():
                label = build_blank_label(cls)
                rel   = img_path.relative_to(IMG_BASE).as_posix()
                examples.append(make_example(rel, label, "blank_synth", FIRST_PAGE_PREV))
                count += 1
                continue

            pdf_path = pdf_d / f"blank_{seed:04d}.pdf"
            try:
                _generate_blank_pdf(cls, pdf_path, seed)
            except Exception as e:
                print(f"  ERROR generating {cls} seed={seed}: {e}")
                continue

            imgs = pdf_to_pngs(pdf_path, img_d, f"blank_{seed:04d}", skip_existing=False)
            if imgs:
                label = build_blank_label(cls)
                rel   = imgs[0].relative_to(IMG_BASE).as_posix()
                examples.append(make_example(rel, label, "blank_synth", FIRST_PAGE_PREV))
                count += 1

        total += count
        print(f"  {folder_name:<45} {count:>3} synthetic blank pages")

    print(f"  Subtotal: {total:,} examples")
    return total


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
    print("DHL Dataset Preparation v3 — Classification + Splitting + Extraction + Blank Forms")
    print(f"Output: {OUT_DIR}")
    print("=" * 65)

    t0       = time.time()
    examples = []

    step1_single_docs(examples,          skip_existing)
    step2_multipage_docs(examples,       skip_existing)
    step3_splitting_packets(examples,    skip_existing)
    step4_real_blank_docs(examples,      skip_existing)
    step5_synthetic_blank_docs(examples, skip_existing)

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
        "version": "v3_extraction",
    }
    (OUT_DIR / "dataset_stats.json").write_text(json.dumps(stats, indent=2))

    print(f"\nSaved to {OUT_DIR}/")
    print(f"  train.jsonl : {len(train):,}")
    print(f"  val.jsonl   : {len(val):,}")
    print(f"  test.jsonl  : {len(test):,}")
    print()
    print("To use this dataset for training, update train_config.yaml:")
    print('  paths:')
    print('    train_data: "Training_Data_v3/train.jsonl"')
    print('    val_data:   "Training_Data_v3/val.jsonl"')
    print('    image_base: "Training_Data"   # images still in Training_Data/')


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-skip", action="store_true",
                   help="Re-convert PDFs even if images exist")
    args = p.parse_args()
    main(skip_existing=not args.no_skip)
