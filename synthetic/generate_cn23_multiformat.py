"""
CN23 / Customs Declaration — 3 distinct real-world format variants.
Format 1: CN23 Full Form (Royal Mail / postal UPU style)
Format 2: CN22 Small Parcel Form — simplified compact layout
Format 3: US CBP Informal Entry / Low Value Customs Form
Generates 1000 diverse documents distributed across all 3 formats.
"""
import json, random, argparse
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_hawb_number, random_mawb_number, random_bl_number, random_invoice_number,
    random_vat_number, AIRPORTS, PORTS_SEA, VESSEL_NAMES, CURRENCIES,
    COMMODITY_CATEGORIES, PACKAGE_TYPES, INCOTERMS)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "09_Customs_Declarations"
PDF_DIR, ANN_DIR = OUT_DIR / "pdfs", OUT_DIR / "annotations"

W = 186 * mm
BORDER = colors.HexColor("#444444")
LN = colors.HexColor("#CCCCCC")

def S(n, **k):
    d = dict(fontName="Helvetica", fontSize=8, leading=10,
             textColor=colors.black, spaceAfter=0, spaceBefore=0)
    d.update(k)
    return ParagraphStyle(n, **d)

def P(t, s):
    return Paragraph(str(t), s)


# ── Synthetic data builder ─────────────────────────────────────────────────
def make_data():
    sc = random_country()
    rc = random_country()
    while rc[1] == sc[1]: rc = random_country()

    categories_list = ["Gift", "Commercial Sample", "Returned Goods", "Other", "Sale of Goods"]
    category = random.choice(categories_list)

    n_items = random.randint(1, 6)
    items = []
    for _ in range(n_items):
        cat = random.choice(COMMODITY_CATEGORIES)
        qty = random.randint(1, 20)
        unit_val = round(random.uniform(2.0, 150.0), 2)
        wt = round(random.uniform(0.05, 5.0), 3)
        items.append({
            "qty": qty,
            "description": cat["description"][:45],
            "weight_kg": wt,
            "value": round(qty * unit_val, 2),
            "hs_code": cat["hs_code"],
            "country_of_origin": random_country()[0],
        })

    total_weight = round(sum(i["weight_kg"] for i in items), 3)
    total_value = round(sum(i["value"] for i in items), 2)
    currency = random.choice(CURRENCIES)
    insured = random.choice([True, False])
    insured_amount = round(total_value * 1.1, 2) if insured else 0.0

    # US CBP data
    port_of_entry = random.choice([
        "New York, NY", "Los Angeles, CA", "Chicago, IL",
        "Miami, FL", "Houston, TX", "Seattle, WA", "Boston, MA",
    ])
    hts_no = random.choice(COMMODITY_CATEGORIES)["hs_code"]
    entered_value = total_value
    duty_rate = round(random.uniform(0.0, 25.0), 1)
    estimated_duty = round(entered_value * duty_rate / 100, 2)
    entry_number = fake.bothify("###-########-#")
    entry_type = random.choice(["Informal Entry", "Formal Entry", "Section 321 De Minimis"])
    cbp_carrier = random.choice(["DHL Express", "FedEx", "UPS", "USPS", "Royal Mail"])

    return dict(
        sender_name=fake.name(),
        sender_company=random_company(),
        sender_address=fake.address().replace("\n", ", ") + f", {sc[0]}",
        sender_country=sc,
        sender_phone=fake.phone_number(),
        sender_email=fake.email(),
        addressee_name=fake.name(),
        addressee_company=random_company(),
        addressee_address=fake.address().replace("\n", ", ") + f", {rc[0]}",
        addressee_country=rc,
        addressee_phone=fake.phone_number(),
        category=category,
        items=items,
        total_weight_kg=total_weight,
        total_value=total_value,
        currency=currency,
        insured=insured,
        insured_amount=insured_amount,
        postal_charges=round(random.uniform(5.0, 80.0), 2),
        issue_date=fake.date_between(start_date="-1y", end_date="today"),
        reference=f"REF-{fake.bothify('######')}",
        tracking_no=fake.bothify("?? ### ### ### ??").upper().replace(" ", ""),
        # US CBP specific
        port_of_entry=port_of_entry,
        cbp_carrier=cbp_carrier,
        awb_no=random_hawb_number(),
        hts_no=hts_no,
        entered_value=entered_value,
        duty_rate=duty_rate,
        estimated_duty=estimated_duty,
        entry_number=entry_number,
        entry_type=entry_type,
        importer_ein=fake.bothify("##-#######"),
        customs_broker=random_company(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — CN23 Full Form (Royal Mail / UPU postal style)
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    ROYAL = colors.HexColor("#990000")
    LRED = colors.HexColor("#FFF5F5")
    MRED = colors.HexColor("#FFE0E0")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER, textColor=colors.white),
        "upu":    S("upu", fontName="Helvetica-Bold", fontSize=9, textColor=ROYAL),
        "lbl":    S("l", fontSize=6.5, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=8),
        "sm":     S("sm", fontSize=7, leading=8.5),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=6.5, leading=8),
        "cdr":    S("cdr", fontSize=6.5, leading=8, alignment=TA_RIGHT),
        "cdc":    S("cdc", fontSize=6.5, leading=8, alignment=TA_CENTER),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=7.5),
        "chk":    S("chk", fontSize=9),
        "note":   S("nt", fontSize=6, textColor=colors.HexColor("#888888")),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    # Title
    story.append(Table([[
        Ps("CUSTOMS DECLARATION — CN23", "title"),
        Ps("UPU / UNIVERSAL POSTAL UNION", "title"),
    ]], colWidths=[120*mm, 66*mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ROYAL),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("INNERGRID", (0, 0), (-1, -1), .5, colors.white),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
    ])))
    story.append(Spacer(1, 1*mm))

    # Tracking + reference
    ref_t = Table([[
        [Ps("TRACKING / BARCODE NO.", "lbl"), Ps(d["tracking_no"], "bold")],
        [Ps("REFERENCE", "lbl"), Ps(d["reference"], "val")],
        [Ps("DATE", "lbl"), Ps(d["issue_date"].strftime("%d %b %Y"), "val")],
    ]], colWidths=[W])
    ref_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LRED),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(ref_t)
    story.append(Spacer(1, 1*mm))

    # Sender / Addressee blocks
    party_t = Table([[
        [Ps("SENDER", "upu"),
         Ps("Name:", "lbl"), Ps(d["sender_name"], "val"),
         Ps("Company:", "lbl"), Ps(d["sender_company"], "sm"),
         Ps("Address:", "lbl"), Ps(d["sender_address"], "sm"),
         Ps("Phone:", "lbl"), Ps(d["sender_phone"], "sm"),
         Ps("Email:", "lbl"), Ps(d["sender_email"], "sm")],
        [Ps("ADDRESSEE", "upu"),
         Ps("Name:", "lbl"), Ps(d["addressee_name"], "val"),
         Ps("Company:", "lbl"), Ps(d["addressee_company"], "sm"),
         Ps("Address:", "lbl"), Ps(d["addressee_address"], "sm"),
         Ps("Phone:", "lbl"), Ps(d["addressee_phone"], "sm"),
         Ps("Country:", "lbl"), Ps(d["addressee_country"][0], "val")],
    ]], colWidths=[93*mm, 93*mm])
    party_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .5, ROYAL),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(party_t)
    story.append(Spacer(1, 1*mm))

    # Category checkboxes
    cats = ["Gift", "Commercial Sample", "Returned Goods", "Other", "Sale of Goods"]
    chk_row = [Ps(f"[{'X' if d['category'] == c else ' '}] {c}", "chk") for c in cats]
    cat_t = Table([[
        Ps("CATEGORY OF ITEMS", "lbl"),
    ] + chk_row], colWidths=[32*mm] + [32*mm] * len(cats))
    cat_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (0, 0), MRED),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(cat_t)
    story.append(Spacer(1, 1*mm))

    # Items table
    CW = [14*mm, 60*mm, 22*mm, 24*mm, 28*mm, 38*mm]
    rows = [[Ps("Qty", "ch"), Ps("Detailed Description of Contents", "ch"),
             Ps("Weight (KG)", "ch"), Ps(f"Value ({d['currency']})", "ch"),
             Ps("HS Tariff No.", "ch"), Ps("Country of Origin", "ch")]]
    n_data = len(d["items"])
    for it in d["items"]:
        rows.append([
            Ps(str(it["qty"]), "cdc"),
            Ps(it["description"], "cd"),
            Ps(f"{it['weight_kg']:.3f}", "cdr"),
            Ps(f"{it['value']:,.2f}", "cdr"),
            Ps(it["hs_code"], "cdc"),
            Ps(it["country_of_origin"], "cd"),
        ])
    # Totals
    rows.append([
        Ps("", "cdc"), Ps("TOTAL", "bold"),
        Ps(f"{d['total_weight_kg']:.3f}", "cdr"),
        Ps(f"{d['total_value']:,.2f}", "cdr"),
        Ps("", "cdc"), Ps("", "cd"),
    ])

    stripe = [("BACKGROUND", (0, r), (-1, r), LRED) for r in range(1, n_data + 1) if r % 2 == 0]
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ROYAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), MRED), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(it_t)
    story.append(Spacer(1, 1*mm))

    # Insurance + postal charges
    ins_str = f"{d['currency']} {d['insured_amount']:,.2f}" if d["insured"] else "NOT INSURED"
    fin_t = Table([[
        Ps("INSURED AMOUNT", "lbl"), Ps(ins_str, "val"),
        Ps("POSTAL CHARGES", "lbl"), Ps(f"{d['currency']} {d['postal_charges']:.2f}", "val"),
        Ps("TOTAL DECLARED VALUE", "lbl"), Ps(f"{d['currency']} {d['total_value']:,.2f}", "bold"),
    ]], colWidths=[32*mm, 36*mm, 30*mm, 30*mm, 40*mm, 18*mm])
    fin_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, 0), MRED), ("BACKGROUND", (2, 0), (2, 0), MRED),
        ("BACKGROUND", (4, 0), (4, 0), MRED),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(fin_t)
    story.append(Spacer(1, 1*mm))

    # Special instructions + signature
    sig_t = Table([[
        [Ps("SPECIAL INSTRUCTIONS", "lbl"),
         Ps("Handle with care. Do not bend.", "sm"),
         Spacer(1, 2*mm),
         Ps("LICENCE / CERTIFICATE / INVOICE NO.", "lbl"),
         Ps(d["reference"], "sm")],
        [Ps("SENDER'S DECLARATION", "lbl"),
         Ps("I certify that the particulars given in this customs declaration are correct "
            "and that this item does not contain any dangerous article or articles prohibited "
            "by legislation or postal or customs regulations.", "sm"),
         Spacer(1, 4*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"{d['sender_name']}  |  Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
    ]], colWidths=[80*mm, 106*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    story.append(Spacer(1, 1*mm))
    story.append(P("CN23 — This form must be affixed to the outside of the parcel. "
                   "See UPU regulations for further information.",
                   st["note"]))
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — CN22 Small Parcel Form (compact)
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    GREEN2 = colors.HexColor("#1B5E20")
    LGREEN = colors.HexColor("#F1F8E9")
    MGREEN = colors.HexColor("#DCEDC8")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=colors.white),
        "lbl":    S("l", fontSize=7, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=8.5),
        "sm":     S("sm", fontSize=7.5, leading=9),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=8),
        "chk":    S("chk", fontSize=10),
        "note":   S("nt", fontSize=6.5, textColor=colors.HexColor("#888888")),
        "hdr":    S("h", fontName="Helvetica-Bold", fontSize=8, textColor=GREEN2),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    W2 = 180 * mm
    story = []

    # Title — CN22 is a smaller, simpler form
    story.append(Table([[
        Ps("CUSTOMS DECLARATION — CN22", "title"),
        Ps("SMALL PARCEL / LETTER-POST", "title"),
    ]], colWidths=[110*mm, 70*mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN2),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("INNERGRID", (0, 0), (-1, -1), .5, colors.white),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
    ])))
    story.append(Spacer(1, 2*mm))

    # Sender block
    send_t = Table([[
        Ps("SENDER NAME / BUSINESS", "lbl"),
        Ps(f"{d['sender_name']}  /  {d['sender_company']}", "val"),
    ], [
        Ps("SENDER ADDRESS", "lbl"),
        Ps(d["sender_address"], "sm"),
    ]], colWidths=[45*mm, 135*mm])
    send_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, -1), MGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(send_t)
    story.append(Spacer(1, 1*mm))

    # Addressee block
    addr_t = Table([[
        Ps("ADDRESSEE NAME", "lbl"),
        Ps(d["addressee_name"], "val"),
    ], [
        Ps("ADDRESSEE ADDRESS", "lbl"),
        Ps(d["addressee_address"], "sm"),
    ], [
        Ps("COUNTRY OF DESTINATION", "lbl"),
        Ps(d["addressee_country"][0], "val"),
    ]], colWidths=[45*mm, 135*mm])
    addr_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, -1), LGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(addr_t)
    story.append(Spacer(1, 2*mm))

    # Category checkboxes — CN22 style
    cats = ["Gift", "Sample", "Returned Goods", "Other", "Commercial"]
    chk_data = [Ps(f"[{'X' if d['category'][:4].lower() == c[:4].lower() else ' '}] {c}", "chk")
                for c in cats]
    cat_t = Table([[Ps("CATEGORY:", "hdr")] + chk_data],
                  colWidths=[24*mm] + [32*mm] * len(cats))
    cat_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(cat_t)
    story.append(Spacer(1, 2*mm))

    # Brief goods description (CN22 is simpler — just summary)
    desc_lines = "; ".join(it["description"][:30] for it in d["items"][:3])
    if len(d["items"]) > 3:
        desc_lines += f" + {len(d['items']) - 3} more item(s)"

    desc_t = Table([[
        Ps("BRIEF DESCRIPTION OF CONTENTS", "lbl"),
        Ps(desc_lines, "sm"),
    ], [
        Ps("TOTAL WEIGHT", "lbl"),
        Ps(f"{d['total_weight_kg']:.3f} KG", "val"),
    ], [
        Ps("TOTAL VALUE", "lbl"),
        Ps(f"{d['currency']} {d['total_value']:,.2f}", "val"),
    ], [
        Ps("INSURED AMOUNT", "lbl"),
        Ps(f"{d['currency']} {d['insured_amount']:,.2f}" if d["insured"] else "Not Insured", "sm"),
    ]], colWidths=[50*mm, 130*mm])
    desc_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, -1), MGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(desc_t)
    story.append(Spacer(1, 3*mm))

    # Certification + signature
    certify_text = (
        "I certify that the information given in this customs declaration is correct, "
        "that this item does not contain any undeclared dangerous article restricted by "
        "postal regulations, and that it does not contain any narcotic drugs/psychotropic substances."
    )
    cert_t = Table([[
        [Ps("SENDER'S DECLARATION & SIGNATURE", "hdr"),
         Spacer(1, 2*mm),
         Ps(certify_text, "sm"),
         Spacer(1, 5*mm),
         Ps("Signature: _________________________________", "sm"),
         Ps(f"{d['sender_name']}  |  Date: {d['issue_date'].strftime('%d %B %Y')}", "sm")],
        [Ps("TRACKING NO.", "lbl"), Ps(d["tracking_no"], "bold"),
         Spacer(1, 2*mm),
         Ps("REFERENCE", "lbl"), Ps(d["reference"], "sm"),
         Spacer(1, 2*mm),
         Ps("POSTAL CHARGES", "lbl"),
         Ps(f"{d['currency']} {d['postal_charges']:.2f}", "sm")],
    ]], colWidths=[120*mm, 60*mm])
    cert_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, -1), LGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(cert_t)
    story.append(Spacer(1, 2*mm))
    story.append(P("CN22 — Attach securely to outside of parcel. For items up to 2 kg / SDR 300.",
                   st["note"]))
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — US CBP Informal Entry / Low Value Customs Form
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    CBP_BLUE = colors.HexColor("#003366")
    LCBP = colors.HexColor("#E6EEF7")
    MCBP = colors.HexColor("#C5D8F0")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=colors.white),
        "agency": S("ag", fontName="Helvetica-Bold", fontSize=11, textColor=CBP_BLUE),
        "lbl":    S("l", fontSize=6.5, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=8),
        "sm":     S("sm", fontSize=7, leading=8.5),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=8),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=6.5, leading=8),
        "cdr":    S("cdr", fontSize=6.5, leading=8, alignment=TA_RIGHT),
        "cdc":    S("cdc", fontSize=6.5, leading=8, alignment=TA_CENTER),
        "warn":   S("w", fontSize=7, textColor=colors.HexColor("#AA0000")),
        "form":   S("fm", fontSize=7.5, textColor=CBP_BLUE),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    # Agency header
    story.append(Table([[
        [Ps("U.S. CUSTOMS AND BORDER PROTECTION", "agency"),
         Ps("DEPARTMENT OF HOMELAND SECURITY", "sm")],
        Ps("INFORMAL ENTRY / LOW VALUE CUSTOMS DECLARATION", "title"),
        [Ps(f"Entry No: {d['entry_number']}", "bold"),
         Ps(f"Entry Type: {d['entry_type']}", "sm"),
         Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
    ]], colWidths=[70*mm, 80*mm, 36*mm]))
    story[-1].setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), CBP_BLUE),
        ("TEXTCOLOR", (1, 0), (1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Spacer(1, 1*mm))

    # Importer / Consignee details
    imp_t = Table([[
        [Ps("IMPORTER OF RECORD", "lbl"), Ps(d["addressee_name"], "val"),
         Ps(d["addressee_company"], "sm"),
         Ps(d["addressee_address"], "sm"),
         Ps(f"EIN / SSN: {d['importer_ein']}", "sm")],
        [Ps("ULTIMATE CONSIGNEE", "lbl"), Ps(d["addressee_name"], "val"),
         Ps(d["addressee_address"], "sm"),
         Ps(f"Country: {d['addressee_country'][0]}", "sm")],
        [Ps("CUSTOMS BROKER", "lbl"), Ps(d["customs_broker"], "val"),
         Ps(f"CBP Filer Code: {fake.bothify('???')}", "sm"),
         Ps(f"Broker Ref: {d['reference']}", "sm")],
    ]], colWidths=[62*mm, 62*mm, 62*mm])
    imp_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(imp_t)
    story.append(Spacer(1, 1*mm))

    # Transport / Port details
    trans_t = Table([[
        Ps("PORT OF ENTRY", "lbl"), Ps(d["port_of_entry"], "val"),
        Ps("CARRIER / AWB", "lbl"), Ps(f"{d['cbp_carrier']} / {d['awb_no']}", "val"),
        Ps("COUNTRY OF ORIGIN", "lbl"), Ps(d["sender_country"][0], "val"),
        Ps("MODE", "lbl"), Ps("Air", "val"),
    ]], colWidths=[28*mm, 36*mm, 28*mm, 46*mm, 28*mm, 36*mm, 12*mm, 12*mm])
    trans_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, 0), LCBP), ("BACKGROUND", (2, 0), (2, 0), LCBP),
        ("BACKGROUND", (4, 0), (4, 0), LCBP), ("BACKGROUND", (6, 0), (6, 0), LCBP),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(trans_t)
    story.append(Spacer(1, 1*mm))

    # Goods table
    CW = [30*mm, 54*mm, 22*mm, 20*mm, 26*mm, 20*mm, 14*mm]
    rows = [[Ps("HTS NUMBER", "ch"), Ps("Description of Goods", "ch"),
             Ps("Country of\nOrigin", "ch"), Ps("Qty / Unit", "ch"),
             Ps(f"Entered Value\n({d['currency']})", "ch"),
             Ps("Duty Rate", "ch"), Ps(f"Duty\nAmt", "ch")]]
    n_data = len(d["items"])
    for it in d["items"]:
        rows.append([
            Ps(it["hs_code"], "cdc"),
            Ps(it["description"], "cd"),
            Ps(it["country_of_origin"][:14], "cdc"),
            Ps(f"{it['qty']} PCS", "cdc"),
            Ps(f"{it['value']:,.2f}", "cdr"),
            Ps(f"{d['duty_rate']:.1f}%", "cdc"),
            Ps(f"{round(it['value'] * d['duty_rate'] / 100, 2):,.2f}", "cdr"),
        ])
    rows.append([
        Ps("", "cdc"), Ps("TOTAL", "bold"), Ps("", "cdc"),
        Ps("", "cdc"),
        Ps(f"{d['total_value']:,.2f}", "cdr"),
        Ps("", "cdc"),
        Ps(f"{d['estimated_duty']:,.2f}", "cdr"),
    ])

    stripe = [("BACKGROUND", (0, r), (-1, r), LCBP) for r in range(1, n_data + 1) if r % 2 == 0]
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CBP_BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), MCBP), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(it_t)
    story.append(Spacer(1, 1*mm))

    # Summary row
    summ_t = Table([[
        Ps("TOTAL ENTERED VALUE", "lbl"), Ps(f"{d['currency']} {d['total_value']:,.2f}", "bold"),
        Ps("ESTIMATED DUTY", "lbl"), Ps(f"{d['currency']} {d['estimated_duty']:,.2f}", "bold"),
        Ps("TOTAL WEIGHT", "lbl"), Ps(f"{d['total_weight_kg']:.3f} KG", "bold"),
    ]], colWidths=[38*mm, 30*mm, 30*mm, 30*mm, 28*mm, 30*mm])
    summ_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, 0), LCBP), ("BACKGROUND", (2, 0), (2, 0), LCBP),
        ("BACKGROUND", (4, 0), (4, 0), LCBP),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(summ_t)
    story.append(Spacer(1, 2*mm))

    # Certification
    cert_t = Table([[
        [Ps("IMPORTER'S CERTIFICATION", "lbl"),
         Ps("I declare that the statements in the documents herein are true and correct to the "
            "best of my knowledge and belief and that the entered articles are not prohibited. "
            "I acknowledge that civil and criminal penalties may be imposed for false statements.", "sm"),
         Spacer(1, 4*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"{d['addressee_name']}  |  Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
        [Ps("CBP OFFICIAL USE", "lbl"),
         Ps(f"Liquidation Date: ______________", "sm"),
         Ps(f"Officer: ______________", "sm"),
         Ps(f"Port Code: {d['port_of_entry'][:15]}", "sm"),
         Spacer(1, 3*mm),
         Ps("CBP Form 368 / Entry Number:", "form"),
         Ps(d["entry_number"], "bold")],
    ]], colWidths=[120*mm, 66*mm])
    cert_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(cert_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["CN23-Full-Form-UPU", "CN22-Small-Parcel-Form", "US-CBP-Informal-Entry"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"cn23_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Base fields present in all formats
    fields = {
        "addressee_name": d["addressee_name"],
        "addressee_company": d["addressee_company"],
        "addressee_address": d["addressee_address"],
        "addressee_country": d["addressee_country"][0],
        "total_weight_kg": d["total_weight_kg"],
        "total_value": d["total_value"],
        "currency": d["currency"],
        "issue_date": d["issue_date"].strftime("%Y-%m-%d"),
        "reference": d["reference"],
        "line_items": d["items"],
    }

    if fmt_idx == 0:  # fmt1 — CN23 Full Form (UPU)
        fields["sender_name"] = d["sender_name"]
        fields["sender_company"] = d["sender_company"]
        fields["sender_address"] = d["sender_address"]
        fields["sender_phone"] = d["sender_phone"]
        fields["sender_email"] = d["sender_email"]
        fields["addressee_phone"] = d["addressee_phone"]
        fields["category"] = d["category"]
        fields["insured"] = d["insured"]
        fields["insured_amount"] = d["insured_amount"]
        fields["postal_charges"] = d["postal_charges"]
        fields["tracking_number"] = d["tracking_no"]

    if fmt_idx == 1:  # fmt2 — CN22 Small Parcel Form
        fields["sender_name"] = d["sender_name"]
        fields["sender_company"] = d["sender_company"]
        fields["sender_address"] = d["sender_address"]
        fields["category"] = d["category"]
        fields["insured"] = d["insured"]
        fields["insured_amount"] = d["insured_amount"]
        fields["postal_charges"] = d["postal_charges"]
        fields["tracking_number"] = d["tracking_no"]

    if fmt_idx == 2:  # fmt3 — US CBP Informal Entry
        fields["sender_country"] = d["sender_country"][0]
        fields["port_of_entry"] = d["port_of_entry"]
        fields["entry_number"] = d["entry_number"]
        fields["entry_type"] = d["entry_type"]
        fields["duty_rate"] = d["duty_rate"]
        fields["estimated_duty"] = d["estimated_duty"]
        fields["importer_ein"] = d["importer_ein"]
        fields["customs_broker"] = d["customs_broker"]

    ann = {
        "document_id":    fname.replace(".pdf", ""),
        "document_class": "Customs Declaration",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    9,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf", ".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} Customs Declaration documents (3 format variants)...")
    for i in range(1, count + 1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            cat_str = f.get('category', f.get('entry_type', 'N/A'))
            print(f"  [{i:04d}] {a['format_variant'][:25]:<25}  {cat_str:<20}  "
                  f"{f['currency']} {f['total_value']:>10,.2f}  Wt: {f['total_weight_kg']:.2f} KG")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate synthetic CN23/Customs Declaration documents")
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
