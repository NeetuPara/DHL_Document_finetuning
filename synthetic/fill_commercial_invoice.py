"""
Fills the ORIGINAL DHL Commercial Invoice template PDF with synthetic data.
Overlays text at exact field positions — template layout is 100% preserved.
"""
import json, random, argparse
from pathlib import Path
import fitz  # PyMuPDF

import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_line_items, random_invoice_number, random_vat_number, random_dhl_account,
    INCOTERMS, CURRENCIES, PAYMENT_TERMS, EXPORT_TYPES)

TEMPLATE = Path(__file__).parent.parent / "Documents" / "01_Commercial_Invoice" / "Commercial Invoice Template-DHL Express (2).pdf"
OUT_DIR  = Path(__file__).parent.parent / "Synthetic_Data_v2" / "01_Commercial_Invoice"
PDF_DIR  = OUT_DIR / "pdfs"
ANN_DIR  = OUT_DIR / "annotations"

# ── Font helpers ─────────────────────────────────────────────────────────────
F_REG  = "helv"   # Helvetica regular
F_BOLD = "hebo"   # Helvetica bold

# ── Field rects (x0, y0, x1, y1) derived from exact template text analysis ──
# All coordinates are in PDF points from top-left of the 612×792pt page.
R = {
    # Shipper block (y=28.6–114.5, left x=23.2–316.1)
    "sh_name":  (70,  31,  314, 42),   # same row as "Shipper:" label (ends x=67.1)
    "sh_addr1": (30,  43,  314, 55),   # address line 1 — row below label
    "sh_addr2": (30,  55,  314, 67),   # address line 2
    "sh_phone": (62,  92,  314, 103),  # after "Phone:" (ends x=59.6)
    "sh_vat":   (84,  104, 314, 115),  # after "VAT/GST No:" (ends x=81.4)
    # Receiver block (y=114.5–196.7, left x=23.2–316.1)
    "rc_name":  (70,  117, 314, 128),  # same row as "Receiver:" (ends x=68.5)
    "rc_addr1": (30,  129, 314, 141),
    "rc_addr2": (30,  141, 314, 153),
    "rc_phone": (62,  174, 314, 185),  # "Phone:" ends x=59.6
    "rc_vat":   (86,  186, 314, 197),  # "VAT/GST No:" ends x=83.8
    # Right-column date/invoice fields
    "date":     (350, 117, 581, 128),  # "Date:" ends x=348.3
    "inv_no":   (394, 147, 581, 158),  # "Invoice Number:" ends x=391.5
    "ship_ref": (414, 174, 581, 185),  # "Shipment Reference:" ends x=411.5
    # Full-width section (y=196.7–272.9)
    "bill3rd":  (107, 199, 314, 211),  # "Bill to Third Party:" ends x=103.9
    "comments": (376, 199, 581, 246),  # "Comments:" ends x=373.0, multi-line
    "awb":      (410, 248, 581, 260),  # "Airway Bill Number:" ends x=407.3
    # Totals (inside table, y=510.8–546.6)
    "t_val":    (317, 511, 385, 528),  # Total Declared Value (right-align, divider at x=386.2)
    "t_nwt":    (468, 511, 580, 528),  # Total Net Weight (right-align)
    "t_pcs":    (281, 529, 385, 546),  # Total Pieces (right-align)
    "t_gwt":    (476, 529, 580, 546),  # Total Gross Weight (right-align)
    # GST/VAT section (y~547–613)
    "gst":      (131, 564, 262, 584),  # Payer of GST/VAT (label ends ~x=130)
    "cur":      (344, 564, 581, 584),  # Currency Code (label ends x=341.9)
    "exp_type": (122, 578, 268, 598),  # Type of Export (label ends ~x=121)
    "inco":     (323, 578, 581, 598),  # Incoterm (label ends ~x=320.2)
    "pay":      (110, 592, 581, 612),  # Terms of Payment (label ends x=107.9)
    # Signature section
    "sig":      (75,  688, 314, 700),  # "Signature:" ends x=72.5
    "pos":      (120, 706, 314, 718),  # "Position in Company:" ends x=117.1
    "consult":  (151, 724, 350, 736),  # "Shipping Consultant:" ends ~x=150
    "stamp":    (354, 724, 581, 736),  # "Company Stamp:" ends x=351.6
}

# Item table column rects: (x0, x1, align)  align: 0=left,1=center,2=right
COLS = {
    "no":      (24,  49,  2),   # No. column
    "desc":    (51,  192, 0),   # Description
    "qty":     (193, 220, 2),   # Qty.
    "uom":     (221, 254, 1),   # UOM
    "hs":      (255, 316, 1),   # Commodity Code
    "uval":    (317, 356, 2),   # Unit Value
    "sval":    (357, 404, 2),   # Subtotal Value
    "uwt":     (405, 453, 2),   # Unit Net Weight
    "swt":     (454, 506, 2),   # Subtotal Weight
    "origin":  (507, 581, 0),   # Country of Origin
}

# Row y-boundaries from h_lines (8 data rows)
ITEM_ROWS = [(303,329),(329,355),(355,381),(381,407),(407,433),(433,459),(459,485),(485,511)]


def _txt(page, rect_key_or_rect, text, size=9, bold=False, align=0, color=(0,0,0)):
    """Insert text into a named rect or explicit (x0,y0,x1,y1) tuple."""
    r = R[rect_key_or_rect] if isinstance(rect_key_or_rect, str) else rect_key_or_rect
    page.insert_textbox(
        fitz.Rect(*r), str(text),
        fontsize=size, fontname=(F_BOLD if bold else F_REG),
        color=color, align=align,
    )


def _item_cell(page, col_key, row_y0, row_y1, text, size=8):
    x0, x1, align = COLS[col_key]
    # 1pt padding inside row
    page.insert_textbox(
        fitz.Rect(x0+1, row_y0+1, x1-1, row_y1-1), str(text),
        fontsize=size, fontname=F_REG, align=align,
    )


def _split_addr(addr: str, max_lines=2) -> list:
    """Split address string into at most max_lines for the form."""
    parts = [p.strip() for p in addr.split(",")]
    if len(parts) <= max_lines:
        return parts
    # Merge first parts onto fewer lines
    city_country = ", ".join(parts[-(max_lines-1):])
    street = ", ".join(parts[:len(parts)-(max_lines-1)])
    return [street[:50], city_country[:50]]


def generate_one(doc_id: int) -> dict:
    sc = random_country(); rc = random_country()
    while rc[1] == sc[1]: rc = random_country()

    sn = random_company()
    sa = fake.address().replace("\n", ", ") + f", {sc[0]}"
    sp = fake.phone_number(); sv = random_vat_number(sc[1])

    rn = random_company()
    ra = fake.address().replace("\n", ", ") + f", {rc[0]}"
    rp = fake.phone_number(); rv = random_vat_number(rc[1])
    ra2 = random_dhl_account()

    dt  = fake.date_between(start_date="-2y", end_date="today")
    inv = random_invoice_number()
    ref = f"REF-{random.randint(100000,999999)}"
    awb = f"{random.randint(100,999)}-{random.randint(10000000,99999999)}"
    b3p = random.choice(["Yes","No","No","No"])
    cmt = random.choice(["","","Fragile — Handle with care",
                          f"PO# {random.randint(10000,99999)}","Sample — No commercial value"])
    cur = random.choice(CURRENCIES); inc = random.choice(INCOTERMS)
    pay = random.choice(PAYMENT_TERMS); exp = random.choice(EXPORT_TYPES)
    gst = random.choice(["Shipper","Receiver","Third Party"])

    items = random_line_items(random.randint(1, 8))
    tv = round(sum(i["total_value"]     for i in items), 2)
    tn = round(sum(i["total_weight_kg"] for i in items), 2)
    tg = round(tn * random.uniform(1.05, 1.25), 2)
    tp = random.randint(len(items), len(items) * 20)

    sig_name = fake.name()
    sig_pos  = random.choice(["Export Manager","Logistics Director","Operations Manager",
                               "Compliance Officer","Trade Manager","Finance Controller"])
    consultant = fake.name()

    # ── Open template, insert data ────────────────────────────────────────
    doc  = fitz.open(str(TEMPLATE))
    page = doc[0]

    # — Shipper —
    sa_lines = _split_addr(sa, 2)
    _txt(page, "sh_name",  sn, bold=True)
    _txt(page, "sh_addr1", sa_lines[0])
    if len(sa_lines) > 1: _txt(page, "sh_addr2", sa_lines[1])
    _txt(page, "sh_phone", sp)
    _txt(page, "sh_vat",   sv)

    # — Receiver —
    ra_lines = _split_addr(ra, 2)
    _txt(page, "rc_name",  rn, bold=True)
    _txt(page, "rc_addr1", ra_lines[0])
    if len(ra_lines) > 1: _txt(page, "rc_addr2", ra_lines[1])
    _txt(page, "rc_phone", rp)
    _txt(page, "rc_vat",   rv)

    # — Date / Invoice / Ref —
    _txt(page, "date",     dt.strftime("%d %b %Y"))
    _txt(page, "inv_no",   inv)
    _txt(page, "ship_ref", ref)

    # — Bill / Comments / AWB —
    _txt(page, "bill3rd",  b3p)
    _txt(page, "comments", cmt)
    _txt(page, "awb",      awb)

    # — Line items (up to 8 rows) —
    for i, (item, (ry0, ry1)) in enumerate(zip(items[:8], ITEM_ROWS)):
        _item_cell(page, "no",     ry0, ry1, i+1)
        _item_cell(page, "desc",   ry0, ry1, item["description"], size=7.5)
        _item_cell(page, "qty",    ry0, ry1, item["qty"])
        _item_cell(page, "uom",    ry0, ry1, item["unit"])
        _item_cell(page, "hs",     ry0, ry1, item["hs_code"])
        _item_cell(page, "uval",   ry0, ry1, f"{item['unit_value']:,.2f}")
        _item_cell(page, "sval",   ry0, ry1, f"{item['total_value']:,.2f}")
        _item_cell(page, "uwt",    ry0, ry1, f"{item['unit_weight_kg']:.3f}")
        _item_cell(page, "swt",    ry0, ry1, f"{item['total_weight_kg']:.2f}")
        _item_cell(page, "origin", ry0, ry1, item["country_of_origin"], size=7.5)

    # — Totals —
    _txt(page, "t_val", f"{cur} {tv:,.2f}", bold=True, align=2)
    _txt(page, "t_nwt", f"{tn:,.3f} KG",   bold=True, align=2)
    _txt(page, "t_pcs", str(tp),            bold=True, align=2)
    _txt(page, "t_gwt", f"{tg:,.3f} KG",   bold=True, align=2)

    # — GST/VAT section —
    _txt(page, "gst",      gst, bold=True)
    _txt(page, "cur",      cur, bold=True)
    _txt(page, "exp_type", exp, bold=True)
    _txt(page, "inco",     inc, bold=True)
    _txt(page, "pay",      pay, bold=True)

    # — Signature —
    _txt(page, "sig",     sig_name)
    _txt(page, "pos",     sig_pos)
    _txt(page, "consult", consultant)
    _txt(page, "stamp",   sn)           # company name in stamp area

    fname = f"commercial_invoice_{doc_id:04d}.pdf"
    doc.save(str(PDF_DIR / fname))
    doc.close()

    ann = {
        "document_id":    fname.replace(".pdf",""),
        "document_class": "Commercial Invoice",
        "class_index":    1,
        "fields": {
            "shipper_name":          sn,  "shipper_address": sa,
            "shipper_phone":         sp,  "shipper_vat":     sv,
            "shipper_country":       sc[0], "shipper_country_code": sc[1],
            "receiver_name":         rn,  "receiver_address": ra,
            "receiver_phone":        rp,  "receiver_vat":    rv,
            "receiver_dhl_account":  ra2,
            "receiver_country":      rc[0], "receiver_country_code": rc[1],
            "invoice_date":          dt.strftime("%Y-%m-%d"),
            "invoice_number":        inv, "shipment_reference": ref,
            "airway_bill_number":    awb, "bill_to_third_party": b3p,
            "comments":              cmt, "currency": cur,
            "incoterm":              inc, "payment_terms": pay,
            "export_type":           exp, "gst_vat_payer": gst,
            "total_declared_value":  tv,  "total_net_weight_kg": tn,
            "total_gross_weight_kg": tg,  "total_pieces": tp,
            "signatory_name":        sig_name, "signatory_position": sig_pos,
            "shipping_consultant":   consultant,
            "line_items":            items,
        },
    }
    (ANN_DIR / fname.replace(".pdf",".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=10):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} Commercial Invoice documents (template fill)...")
    for i in range(1, count+1):
        a = generate_one(i)
        f = a["fields"]
        print(f"  [{i:04d}] {f['invoice_number']}  {f['currency']} {f['total_declared_value']:>12,.2f}  {len(f['line_items'])} items")
    print(f"\nDone -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=10)
    generate(p.parse_args().count)
