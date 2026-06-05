"""
Full ground-truth audit: verifies every extraction field for every class/variant
resolves to an actual value in the annotation JSON.

Checks 10 samples per class, reports:
  - sample GT values actually extracted
  - null% (how often the annotation doesn't have the field)
  - MISS if a mapped key doesn't exist in ANY annotation
"""
import json, os, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "D:/finetuning/DHL_Document_finetuning"
N_SAMPLES = 10

TARGET = [
    "shipper_name", "consignee_name", "document_date", "document_number",
    "country_of_origin", "country_of_destination", "description_of_goods",
    "gross_weight_kg",
]

# ── FIELD_MAP (mirrors prepare_dataset_v2.py exactly) ──────────────────────
FIELD_MAP = {
    "CI single": {
        "shipper_name":           "shipper_name",
        "consignee_name":         "receiver_name",
        "document_date":          "invoice_date",
        "document_number":        "invoice_number",
        "country_of_origin":      "shipper_country",
        "country_of_destination": "receiver_country",
        "description_of_goods":   ("line_items", "description"),
        "gross_weight_kg":        "total_gross_weight_kg",
    },
    "CI multi": {
        "shipper_name":           "shipper_name",
        "consignee_name":         "receiver_name",
        "document_date":          "invoice_date",
        "document_number":        "invoice_number",
        "country_of_origin":      "shipper_country",
        "country_of_destination": "receiver_country",
        "description_of_goods":   ("line_items", "description"),
        "gross_weight_kg":        "total_gross_weight_kg",
    },
    "HBL single": {
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          "issue_date",
        "document_number":        "bl_number",
        "country_of_origin":      "shipper_country",
        "country_of_destination": "consignee_country",
        "description_of_goods":   "description_of_goods",
        "gross_weight_kg":        "gross_weight_kg",
    },
    "HBL multi": {
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          "date",
        "document_number":        "bl_number",
        "country_of_origin":      "pol",
        "country_of_destination": "pod",
        "description_of_goods":   None,
        "gross_weight_kg":        "total_gross_wt_kg",
    },
    "COO single": {
        "shipper_name":           "exporter_name",
        "consignee_name":         "consignee_name",
        "document_date":          "issue_date",
        "document_number":        "document_number",
        "country_of_origin":      "country_of_origin",
        "country_of_destination": "country_of_destination",
        "description_of_goods":   ("goods", "description"),
        "gross_weight_kg":        None,
    },
    "SLI single": {
        "shipper_name":           "usppi_name",
        "consignee_name":         "consignee_name",
        "document_date":          None,
        "document_number":        "reference",
        "country_of_origin":      "usppi_country",
        "country_of_destination": "destination_country",
        "description_of_goods":   ("line_items", "description"),
        "gross_weight_kg":        "total_weight_kg",
    },
    "SLI multi": {
        "shipper_name":           "usppi",
        "consignee_name":         "consignee",
        "document_date":          None,
        "document_number":        "reference",
        "country_of_origin":      None,
        "country_of_destination": "destination",
        "description_of_goods":   None,
        "gross_weight_kg":        None,
    },
    "DGD single": {
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          "signature_date",
        "document_number":        "awb_number",
        "country_of_origin":      "shipper_country",
        "country_of_destination": "consignee_country",
        "description_of_goods":   ("dg_entries", "proper_name"),
        "gross_weight_kg":        None,
    },
    "DGD multi": {
        "shipper_name":           "shipper",
        "consignee_name":         "consignee",
        "document_date":          "date",
        "document_number":        "awb",
        "country_of_origin":      "departure",
        "country_of_destination": "destination",
        "description_of_goods":   None,
        "gross_weight_kg":        None,
    },
    "VGM single": {
        "shipper_name":           "shipper_name",
        "consignee_name":         None,
        "document_date":          "signature_date",
        "document_number":        "bl_number",
        "country_of_origin":      "shipper_country",
        "country_of_destination": "port_of_discharge",
        "description_of_goods":   None,
        "gross_weight_kg":        "vgm_kg",
    },
    "VGM multi": {
        "shipper_name":           "shipper",
        "consignee_name":         None,
        "document_date":          "date",
        "document_number":        "bl",
        "country_of_origin":      None,
        "country_of_destination": "pod",
        "description_of_goods":   None,
        "gross_weight_kg":        "total_vgm_kg",
    },
    "HAWB single": {
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          "issue_date",
        "document_number":        "hawb_number",
        "country_of_origin":      "airport_departure",
        "country_of_destination": "airport_destination",
        "description_of_goods":   "nature_of_goods",
        "gross_weight_kg":        "gross_weight_kg",
    },
    "PL single": {
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          "date",
        "document_number":        "invoice_number",
        "country_of_origin":      None,
        "country_of_destination": None,
        "description_of_goods":   ("line_items", "description"),
        "gross_weight_kg":        "total_gross_weight_kg",
    },
    "PL multi": {
        "shipper_name":           "shipper_name",
        "consignee_name":         "consignee_name",
        "document_date":          "date",
        "document_number":        "invoice_number",
        "country_of_origin":      None,
        "country_of_destination": None,
        "description_of_goods":   ("items", "description"),
        "gross_weight_kg":        "total_gross_weight_kg",
    },
    "CN23 single": {
        "shipper_name":           "sender_name",
        "consignee_name":         "addressee_name",
        "document_date":          "issue_date",
        "document_number":        "reference",
        "country_of_origin":      "sender_country",
        "country_of_destination": "addressee_country",
        "description_of_goods":   ("line_items", "description"),
        "gross_weight_kg":        "total_weight_kg",
    },
    "CM single": {
        "shipper_name":           None,
        "consignee_name":         None,
        "document_date":          "issue_date",
        "document_number":        "manifest_number",
        "country_of_origin":      "departure_airport",
        "country_of_destination": "destination_airport",
        "description_of_goods":   ("entries", "description"),
        "gross_weight_kg":        "total_weight_kg",
    },
    "CM multi": {
        "shipper_name":           None,
        "consignee_name":         None,
        "document_date":          "date",
        "document_number":        "manifest_no",
        "country_of_origin":      "from_location",
        "country_of_destination": "to_location",
        "description_of_goods":   None,
        "gross_weight_kg":        "total_gross_weight_kg",
    },
    "EEI single": {
        "shipper_name":           "importer_name",
        "consignee_name":         ["consignee_name", "ultimate_consignee"],
        "document_date":          "entry_date",
        "document_number":        "entry_number",
        "country_of_origin":      "country_of_origin",
        "country_of_destination": "destination_country",
        "description_of_goods":   ("line_items", "description"),
        "gross_weight_kg":        None,
    },
    "EEI multi": {
        "shipper_name":           "importer",
        "consignee_name":         None,
        "document_date":          "date",
        "document_number":        "entry_number",
        "country_of_origin":      "country_of_origin",
        "country_of_destination": None,
        "description_of_goods":   None,
        "gross_weight_kg":        None,
    },
    "POA single": {
        "shipper_name":           "grantor_name",
        "consignee_name":         None,
        "document_date":          "issue_date",
        "document_number":        "poa_reference",
        "country_of_origin":      "grantor_country",
        "country_of_destination": None,
        "description_of_goods":   "specific_goods",
        "gross_weight_kg":        None,
    },
}

PATHS = {
    "CI single":   "Synthetic_Data/01_Commercial_Invoice",
    "CI multi":    "Synthetic_Data_MultiPage/01_Commercial_Invoice",
    "HBL single":  "Synthetic_Data/02_House_Bill_of_Lading",
    "HBL multi":   "Synthetic_Data_MultiPage/02_House_Bill_of_Lading",
    "COO single":  "Synthetic_Data/03_Certificate_of_Origin",
    "SLI single":  "Synthetic_Data/04_Shippers_Letter_of_Instruction",
    "SLI multi":   "Synthetic_Data_MultiPage/04_Shippers_Letter_of_Instruction",
    "DGD single":  "Synthetic_Data/05_Dangerous_Goods_Declaration",
    "DGD multi":   "Synthetic_Data_MultiPage/05_Dangerous_Goods_Declaration",
    "VGM single":  "Synthetic_Data/06_Verified_Gross_Mass",
    "VGM multi":   "Synthetic_Data_MultiPage/06_Verified_Gross_Mass",
    "HAWB single": "Synthetic_Data/07_House_Airway_Bill",
    "PL single":   "Synthetic_Data/08_Packing_List",
    "PL multi":    "Synthetic_Data_MultiPage/08_Packing_List",
    "CN23 single": "Synthetic_Data/09_Customs_Declarations",
    "CM single":   "Synthetic_Data/10_Cargo_Manifest",
    "CM multi":    "Synthetic_Data_MultiPage/10_Cargo_Manifest",
    "EEI single":  "Synthetic_Data/11_Import_Export_License",
    "EEI multi":   "Synthetic_Data_MultiPage/11_Import_Export_License",
    "POA single":  "Synthetic_Data/12_Power_of_Attorney",
}


def load_all(rel_path, n=N_SAMPLES):
    ann_dir = os.path.join(BASE, rel_path, "annotations")
    if not os.path.exists(ann_dir):
        return []
    files = sorted(os.listdir(ann_dir))[:n]
    out = []
    for f in files:
        try:
            d = json.loads(open(os.path.join(ann_dir, f), encoding="utf-8").read())
            out.append(d.get("fields", d))
        except Exception:
            pass
    return out


def extract_one(flds, src):
    """Extract one field value from annotation dict using src spec. Returns value or None."""
    if src is None:
        return None
    if isinstance(src, tuple):
        lk, ik = src
        items = flds.get(lk, [])
        if items and isinstance(items, list) and items[0].get(ik):
            return items[0][ik]
        return None
    if isinstance(src, list):
        for item in src:
            if isinstance(item, tuple):
                lk, ik = item
                items = flds.get(lk, [])
                if items and isinstance(items, list) and items[0].get(ik):
                    return items[0][ik]
            else:
                v = flds.get(item)
                if v is not None:
                    return v
        return None
    return flds.get(src)


all_issues = []

for label in PATHS:
    mapping = FIELD_MAP[label]
    samples = load_all(PATHS[label])
    if not samples:
        print(f"\n{'='*80}")
        print(f"  {label}: NO ANNOTATION FILES FOUND at {PATHS[label]}")
        continue

    print(f"\n{'='*80}")
    print(f"  {label}  ({len(samples)} samples)  path: {PATHS[label]}")
    print(f"  {'Field':<26}  {'Ann Key':<30}  {'S1 value':<30}  {'S2 value':<30}  {'null%'}")
    print(f"  {'-'*26}  {'-'*30}  {'-'*30}  {'-'*30}  ------")

    for field in TARGET:
        src = mapping[field]
        values = [extract_one(s, src) for s in samples]
        null_count = sum(1 for v in values if v is None)
        null_pct = int(100 * null_count / len(samples))
        s1 = str(values[0])[:28] if values[0] is not None else "null"
        s2 = str(values[1])[:28] if len(values) > 1 and values[1] is not None else ("null" if len(values) > 1 else "-")

        # Determine status
        if src is None:
            status = "(intentional null)"
        elif null_count == len(samples):
            status = "*** ALL NULL — KEY MISSING ***"
            all_issues.append(f"  {label} | {field} | src={src} | key not found in any annotation")
        elif null_pct > 50:
            status = f"WARNING: {null_pct}% null"
        else:
            status = ""

        src_str = str(src)[:28] if src is not None else "None → intentional"
        print(f"  {field:<26}  {src_str:<30}  {s1:<30}  {s2:<30}  {null_pct:3d}%  {status}")

print(f"\n{'='*80}")
if all_issues:
    print(f"ISSUES — keys that resolve to NULL in ALL samples ({len(all_issues)} total):")
    for i in all_issues:
        print(i)
else:
    print("ALL FIELDS RESOLVE CORRECTLY.")
    print("Every non-null source key found actual values in the annotation JSON.")
    print("Null entries marked '(intentional null)' have no field equivalent for that doc type.")
