"""
Packing List — 3 distinct real-world format variants.
Format 1: DHL GF Style (standard) — Shipper/Consignee 3-col header
Format 2: Detailed Warehouse Style — extra columns, summary box
Format 3: E-commerce/Fulfillment Style — SKU-based modern look
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

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "08_Packing_List"
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
    sc = random_country(); rc = random_country()
    while rc[1] == sc[1]: rc = random_country()

    mode = random.choice(["Air Freight", "Ocean Freight", "Road Freight", "Express Courier"])
    carrier = random.choice(["DHL Freight", "FedEx Freight", "UPS Supply Chain", "Maersk Line",
                              "MSC", "COSCO Shipping", "Lufthansa Cargo", "Emirates SkyCargo"])
    inc = random.choice(INCOTERMS)
    bl_awb = random_hawb_number() if "Air" in mode else random_bl_number()

    n_items = random.randint(2, 8)
    items = []
    used_cats = random.sample(COMMODITY_CATEGORIES, min(n_items, len(COMMODITY_CATEGORIES)))
    for idx, cat in enumerate(used_cats):
        n_pkgs = random.randint(1, 20)
        qty_per = random.randint(1, 50)
        unit_net = round(random.uniform(0.2, 15.0), 3)
        unit_gross = round(unit_net * random.uniform(1.05, 1.20), 3)
        l = round(random.uniform(10, 80), 1)
        w = round(random.uniform(10, 60), 1)
        h = round(random.uniform(5, 50), 1)
        cbm = round((l / 100) * (w / 100) * (h / 100) * n_pkgs, 4)
        sku = f"SKU-{fake.bothify('??####').upper()}"
        barcode = fake.bothify("###########")
        items.append({
            "pkg_no":      f"C{idx + 1:02d}",
            "n_pkgs":      n_pkgs,
            "pkg_type":    random.choice(PACKAGE_TYPES),
            "description": cat["description"],
            "hs_code":     cat["hs_code"],
            "net_wt":      round(unit_net * qty_per * n_pkgs, 2),
            "gross_wt":    round(unit_gross * qty_per * n_pkgs, 2),
            "dims":        f"{l}x{w}x{h}",
            "cbm":         cbm,
            "origin":      random_country()[0],
            "sku":         sku,
            "barcode":     barcode,
            "qty_per_pkg": qty_per,
            "total_qty":   qty_per * n_pkgs,
            "unit_net_wt": unit_net,
            "dims_l":      l, "dims_w": w, "dims_h": h,
            "pallet":      random.choice(["P01", "P02", "P03", "N/A"]),
        })

    tot_pkgs = sum(i["n_pkgs"] for i in items)
    tot_net = round(sum(i["net_wt"] for i in items), 2)
    tot_gross = round(sum(i["gross_wt"] for i in items), 2)
    tot_cbm = round(sum(i["cbm"] for i in items), 4)
    tot_qty = sum(i["total_qty"] for i in items)

    # Package type summary for fmt2
    type_summary = {}
    for it in items:
        type_summary[it["pkg_type"]] = type_summary.get(it["pkg_type"], 0) + it["n_pkgs"]

    return dict(
        shipper_name=random_company(), shipper_address=fake.address().replace("\n", ", ") + f", {sc[0]}",
        shipper_country=sc, shipper_phone=fake.phone_number(), shipper_email=fake.company_email(),
        consignee_name=random_company(), consignee_address=fake.address().replace("\n", ", ") + f", {rc[0]}",
        consignee_country=rc, consignee_phone=fake.phone_number(),
        invoice_no=random_invoice_number(),
        reference=f"REF-{random.randint(100000, 999999)}",
        bl_awb=bl_awb,
        date=fake.date_between(start_date="-1y", end_date="today"),
        mode=mode, carrier=carrier, incoterms=inc,
        items=items,
        tot_pkgs=tot_pkgs, tot_net=tot_net, tot_gross=tot_gross,
        tot_cbm=tot_cbm, tot_qty=tot_qty,
        type_summary=type_summary,
        signatory=fake.name(),
        po_no=f"PO-{random.randint(10000, 99999)}",
        order_ref=f"ORD-{fake.bothify('####-######')}",
        currency=random.choice(CURRENCIES),
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — DHL GF Style (standard)
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    NAVY = colors.HexColor("#00205B")
    LIGHT = colors.HexColor("#E8EDF5")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, textColor=colors.white),
        "lbl":    S("l", fontSize=6.5, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=8),
        "sm":     S("sm", fontSize=7, leading=9),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=6.5, leading=8),
        "cdr":    S("cdr", fontSize=6.5, leading=8, alignment=TA_RIGHT),
        "cdc":    S("cdc", fontSize=6.5, leading=8, alignment=TA_CENTER),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=7.5),
        "foot":   S("ft", fontSize=6.5, textColor=colors.HexColor("#777777")),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    # Title
    story.append(Table([[Ps("PACKING LIST", "title")]],
                       colWidths=[W], style=TableStyle([
                           ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                           ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("BOX", (0, 0), (-1, -1), .5, BORDER),
                       ])))
    story.append(Spacer(1, 1*mm))

    # 3-col header: Shipper | Consignee | Reference
    hdr = Table([[
        [Ps("SHIPPER / EXPORTER", "lbl"), Ps(d["shipper_name"], "val"),
         Ps(d["shipper_address"], "sm"),
         Ps(f"Tel: {d['shipper_phone']}", "sm"),
         Ps(f"Email: {d['shipper_email']}", "sm")],
        [Ps("CONSIGNEE", "lbl"), Ps(d["consignee_name"], "val"),
         Ps(d["consignee_address"], "sm"),
         Ps(f"Tel: {d['consignee_phone']}", "sm")],
        [Ps("SHIPMENT REFERENCE", "lbl"),
         Ps(f"Invoice No:", "lbl"), Ps(d["invoice_no"], "val"),
         Ps(f"Reference:", "lbl"), Ps(d["reference"], "val"),
         Ps(f"AWB / B/L:", "lbl"), Ps(d["bl_awb"], "val"),
         Ps(f"PO No:", "lbl"), Ps(d["po_no"], "val"),
         Ps(f"Date:", "lbl"), Ps(d["date"].strftime("%d %b %Y"), "val")],
    ]], colWidths=[62*mm, 62*mm, 62*mm])
    hdr.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 1*mm))

    # Mode/Carrier/Incoterms row
    info_t = Table([[
        Ps("MODE OF TRANSPORT", "lbl"), Ps(d["mode"], "val"),
        Ps("CARRIER", "lbl"), Ps(d["carrier"], "val"),
        Ps("INCOTERMS", "lbl"), Ps(d["incoterms"], "val"),
        Ps("DATE", "lbl"), Ps(d["date"].strftime("%d %b %Y"), "val"),
    ]], colWidths=[30*mm, 32*mm, 22*mm, 40*mm, 22*mm, 18*mm, 10*mm, 12*mm])
    info_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("BACKGROUND", (2, 0), (2, -1), LIGHT),
        ("BACKGROUND", (4, 0), (4, -1), LIGHT),
        ("BACKGROUND", (6, 0), (6, -1), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(info_t)
    story.append(Spacer(1, 1*mm))

    # Items table
    CW = [14*mm, 14*mm, 18*mm, 44*mm, 22*mm, 16*mm, 16*mm, 22*mm, 20*mm]
    rows = [[Ps("Mark/No", "ch"), Ps("Pkgs", "ch"), Ps("Type", "ch"),
             Ps("Description of Goods", "ch"), Ps("HS Code", "ch"),
             Ps("Net Wt (KG)", "ch"), Ps("Gross Wt (KG)", "ch"),
             Ps("Dims (cm)", "ch"), Ps("CBM", "ch")]]
    n_data = len(d["items"])
    for it in d["items"]:
        rows.append([
            Ps(it["pkg_no"], "cdc"), Ps(str(it["n_pkgs"]), "cdr"),
            Ps(it["pkg_type"], "cdc"), Ps(it["description"], "cd"),
            Ps(it["hs_code"], "cdc"),
            Ps(f"{it['net_wt']:.2f}", "cdr"), Ps(f"{it['gross_wt']:.2f}", "cdr"),
            Ps(it["dims"], "cdc"), Ps(f"{it['cbm']:.4f}", "cdr"),
        ])
    # Totals row
    rows.append([
        Ps("TOTAL", "bold"), Ps(str(d["tot_pkgs"]), "cdr"), Ps("", "cdc"),
        Ps("", "cd"), Ps("", "cdc"),
        Ps(f"{d['tot_net']:.2f}", "cdr"), Ps(f"{d['tot_gross']:.2f}", "cdr"),
        Ps("", "cdc"), Ps(f"{d['tot_cbm']:.4f}", "cdr"),
    ])

    stripe = [("BACKGROUND", (0, r), (-1, r), LIGHT) for r in range(1, n_data + 1) if r % 2 == 0]
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#DDDDDD")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(it_t)
    story.append(Spacer(1, 3*mm))

    # Signature block
    sig_t = Table([[
        [Ps("DECLARATION", "lbl"),
         Ps("We hereby certify that the above packing list is true and correct.", "sm"),
         Spacer(1, 5*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"{d['signatory']}  |  Date: {d['date'].strftime('%d %b %Y')}", "sm"),
         Ps(d["shipper_name"], "sm")],
        [Ps("TOTALS", "lbl"),
         Ps(f"Total Packages:  {d['tot_pkgs']}", "bold"),
         Ps(f"Total Net Weight:  {d['tot_net']:.2f} KG", "bold"),
         Ps(f"Total Gross Weight:  {d['tot_gross']:.2f} KG", "bold"),
         Ps(f"Total Volume:  {d['tot_cbm']:.4f} CBM", "bold")],
    ]], colWidths=[120*mm, 66*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — Detailed Warehouse Style
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    ORANGE = colors.HexColor("#E65100")
    LORANGE = colors.HexColor("#FFF3E0")
    MORANGE = colors.HexColor("#FFE0B2")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=colors.white),
        "co":     S("co", fontName="Helvetica-Bold", fontSize=12, textColor=ORANGE),
        "lbl":    S("l", fontSize=6.5, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=7.5),
        "sm":     S("sm", fontSize=7, leading=8.5),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=6, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=6, leading=7.5),
        "cdr":    S("cdr", fontSize=6, leading=7.5, alignment=TA_RIGHT),
        "cdc":    S("cdc", fontSize=6, leading=7.5, alignment=TA_CENTER),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=7),
        "sec":    S("sec", fontName="Helvetica-Bold", fontSize=8, textColor=ORANGE),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=10*mm, rightMargin=10*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    # Company letterhead
    lh = Table([[
        [Ps(d["shipper_name"], "co"),
         Ps(d["shipper_address"], "sm"),
         Ps(f"Tel: {d['shipper_phone']}  |  Email: {d['shipper_email']}", "sm")],
        [Ps("PACKING LIST", "title"),
         Spacer(1, 2*mm),
         Ps(f"Doc No: {d['invoice_no']}", "val"),
         Ps(f"Date: {d['date'].strftime('%d %b %Y')}", "sm")],
    ]], colWidths=[120*mm, 66*mm])
    lh.setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), ORANGE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
    ]))
    story.append(lh)
    story.append(Spacer(1, 1*mm))

    # Consignee + ref
    cr_t = Table([[
        [Ps("CONSIGNEE / DELIVER TO", "lbl"), Ps(d["consignee_name"], "val"),
         Ps(d["consignee_address"], "sm"), Ps(f"Tel: {d['consignee_phone']}", "sm")],
        [Ps("REFERENCE DETAILS", "lbl"),
         Ps(f"Invoice No: {d['invoice_no']}", "sm"),
         Ps(f"Ref: {d['reference']}", "sm"),
         Ps(f"AWB/BL: {d['bl_awb']}", "sm"),
         Ps(f"PO: {d['po_no']}", "sm"),
         Ps(f"Mode: {d['mode']}", "sm"),
         Ps(f"Carrier: {d['carrier']}", "sm"),
         Ps(f"Incoterms: {d['incoterms']}", "sm")],
    ]], colWidths=[93*mm, 93*mm])
    cr_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(cr_t)
    story.append(Spacer(1, 2*mm))

    story.append(Ps("PACKING DETAILS", "sec"))
    story.append(Spacer(1, 1*mm))

    # Detailed items table — wider columns
    CW = [10*mm, 10*mm, 14*mm, 32*mm, 14*mm, 14*mm, 14*mm, 12*mm, 16*mm, 14*mm, 12*mm, 14*mm]
    rows = [[
        Ps("Pkg\nNo", "ch"), Ps("Pkgs", "ch"), Ps("Type", "ch"),
        Ps("Description", "ch"), Ps("HS Code", "ch"),
        Ps("Qty/\nPkg", "ch"), Ps("Total\nQty", "ch"),
        Ps("Unit Wt\n(KG)", "ch"), Ps("Pkg Dims\nL×W×H cm", "ch"),
        Ps("Net Wt\n(KG)", "ch"), Ps("Gross\nWt (KG)", "ch"),
        Ps("Pallet", "ch"),
    ]]
    n_data = len(d["items"])
    for it in d["items"]:
        rows.append([
            Ps(it["pkg_no"], "cdc"), Ps(str(it["n_pkgs"]), "cdr"),
            Ps(it["pkg_type"], "cdc"), Ps(it["description"][:35], "cd"),
            Ps(it["hs_code"], "cdc"),
            Ps(str(it["qty_per_pkg"]), "cdr"), Ps(str(it["total_qty"]), "cdr"),
            Ps(f"{it['unit_net_wt']:.3f}", "cdr"),
            Ps(f"{it['dims_l']}×{it['dims_w']}×{it['dims_h']}", "cdc"),
            Ps(f"{it['net_wt']:.2f}", "cdr"), Ps(f"{it['gross_wt']:.2f}", "cdr"),
            Ps(it["pallet"], "cdc"),
        ])
    # Totals
    rows.append([
        Ps("TOTAL", "bold"), Ps(str(d["tot_pkgs"]), "cdr"), Ps("", "cdc"),
        Ps("", "cd"), Ps("", "cdc"),
        Ps("", "cdr"), Ps(str(d["tot_qty"]), "cdr"),
        Ps("", "cdr"), Ps("", "cdc"),
        Ps(f"{d['tot_net']:.2f}", "cdr"), Ps(f"{d['tot_gross']:.2f}", "cdr"),
        Ps("", "cdc"),
    ])

    stripe = [("BACKGROUND", (0, r), (-1, r), LORANGE) for r in range(1, n_data + 1) if r % 2 == 0]
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORANGE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), MORANGE), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(it_t)
    story.append(Spacer(1, 2*mm))

    # Summary box by package type
    story.append(Ps("PACKAGE TYPE SUMMARY", "sec"))
    story.append(Spacer(1, 1*mm))
    sum_rows = [[Ps("Package Type", "ch"), Ps("Quantity", "ch"), Ps("% of Total", "ch")]]
    for ptype, cnt in d["type_summary"].items():
        pct = round(cnt / d["tot_pkgs"] * 100, 1)
        sum_rows.append([Ps(ptype, "cd"), Ps(str(cnt), "cdr"), Ps(f"{pct}%", "cdr")])
    sum_rows.append([Ps("TOTAL", "bold"), Ps(str(d["tot_pkgs"]), "cdr"), Ps("100.0%", "cdr")])

    n_sum = len(d["type_summary"])
    stripe2 = [("BACKGROUND", (0, r), (-1, r), LORANGE) for r in range(1, n_sum + 1) if r % 2 == 0]
    sum_t = Table(sum_rows, colWidths=[50*mm, 30*mm, 30*mm])
    sum_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORANGE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), MORANGE), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ] + stripe2))

    sig_summary = Table([[sum_t,
        [Ps("AUTHORIZED SIGNATURE", "lbl"),
         Spacer(1, 5*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"{d['signatory']}", "sm"),
         Ps(d["shipper_name"], "sm"),
         Ps(f"Date: {d['date'].strftime('%d %b %Y')}", "sm")]
    ]], colWidths=[115*mm, 71*mm])
    sig_summary.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (1, 0), (1, 0), 10),
    ]))
    story.append(sig_summary)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — E-commerce / Fulfillment Style
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    TEAL = colors.HexColor("#006064")
    LTEAL = colors.HexColor("#E0F7FA")
    MTEAL = colors.HexColor("#B2EBF2")
    DARK = colors.HexColor("#2D3436")
    st = {
        "brand":  S("br", fontName="Helvetica-Bold", fontSize=14, textColor=TEAL),
        "tag":    S("tg", fontSize=7.5, textColor=colors.HexColor("#636E72")),
        "title":  S("t", fontName="Helvetica-Bold", fontSize=11, textColor=DARK),
        "lbl":    S("l", fontSize=6.5, textColor=colors.HexColor("#636E72")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=8, textColor=DARK),
        "sm":     S("sm", fontSize=7, leading=8.5, textColor=DARK),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=6.5, leading=8),
        "cdr":    S("cdr", fontSize=6.5, leading=8, alignment=TA_RIGHT),
        "cdc":    S("cdc", fontSize=6.5, leading=8, alignment=TA_CENTER),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=7),
        "meta":   S("mt", fontSize=6.5, textColor=colors.HexColor("#95A5A6")),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    # Brand header
    hdr = Table([[
        [Ps(d["shipper_name"], "brand"),
         Ps("Fulfillment & Logistics Division", "tag"),
         Ps(d["shipper_address"], "sm")],
        [Ps("PACKING LIST", "title"),
         Spacer(1, 2*mm),
         Ps(f"Order Ref: {d['order_ref']}", "val"),
         Ps(f"Invoice: {d['invoice_no']}", "sm"),
         Ps(f"Date: {d['date'].strftime('%d %b %Y')}", "sm")],
    ]], colWidths=[110*mm, 76*mm])
    hdr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width=W, thickness=2, color=TEAL))
    story.append(Spacer(1, 2*mm))

    # Ship from / ship to / logistics
    ft = Table([[
        [Ps("SHIP FROM", "lbl"), Ps(d["shipper_name"], "val"),
         Ps(d["shipper_address"], "sm")],
        [Ps("SHIP TO", "lbl"), Ps(d["consignee_name"], "val"),
         Ps(d["consignee_address"], "sm"),
         Ps(f"Tel: {d['consignee_phone']}", "sm")],
        [Ps("LOGISTICS", "lbl"),
         Ps(f"Mode: {d['mode']}", "sm"),
         Ps(f"Carrier: {d['carrier']}", "sm"),
         Ps(f"AWB/BL: {d['bl_awb']}", "sm"),
         Ps(f"Incoterms: {d['incoterms']}", "sm"),
         Ps(f"PO: {d['po_no']}", "sm")],
    ]], colWidths=[62*mm, 62*mm, 62*mm])
    ft.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#B2EBF2")),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, -1), LTEAL),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(ft)
    story.append(Spacer(1, 2*mm))

    # SKU-based table
    CW = [20*mm, 28*mm, 40*mm, 20*mm, 14*mm, 16*mm, 16*mm, 10*mm, 14*mm, 14*mm]
    rows = [[
        Ps("SKU", "ch"), Ps("Product Code /\nBarcode", "ch"),
        Ps("Product Name / Description", "ch"), Ps("HS Code", "ch"),
        Ps("Origin", "ch"), Ps("Qty\nOrdered", "ch"), Ps("Qty\nPacked", "ch"),
        Ps("Unit", "ch"), Ps("Net Wt\n(KG)", "ch"), Ps("Box No.", "ch"),
    ]]
    n_data = len(d["items"])
    for it in d["items"]:
        rows.append([
            Ps(it["sku"], "cd"),
            Ps(it["barcode"], "cdc"),
            Ps(it["description"][:40], "cd"),
            Ps(it["hs_code"], "cdc"),
            Ps(it["origin"][:10], "cdc"),
            Ps(str(it["total_qty"]), "cdr"),
            Ps(str(it["total_qty"]), "cdr"),
            Ps(it["pkg_type"][:6], "cdc"),
            Ps(f"{it['net_wt']:.2f}", "cdr"),
            Ps(it["pkg_no"], "cdc"),
        ])
    # Totals
    rows.append([
        Ps("", "cd"), Ps("", "cdc"),
        Ps(f"TOTAL  ({n_data} line items)", "bold"),
        Ps("", "cdc"), Ps("", "cdc"),
        Ps(str(d["tot_qty"]), "cdr"),
        Ps(str(d["tot_qty"]), "cdr"),
        Ps("", "cdc"),
        Ps(f"{d['tot_net']:.2f}", "cdr"),
        Ps("", "cdc"),
    ])

    stripe = [("BACKGROUND", (0, r), (-1, r), LTEAL) for r in range(1, n_data + 1) if r % 2 == 0]
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), MTEAL), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#B2EBF2")),
        ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#E0F7FA")),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(it_t)
    story.append(Spacer(1, 3*mm))

    # Summary footer
    foot = Table([[
        [Ps("SHIPMENT SUMMARY", "lbl"),
         Ps(f"Total Packages: {d['tot_pkgs']}", "bold"),
         Ps(f"Net Weight: {d['tot_net']:.2f} KG", "bold"),
         Ps(f"Gross Weight: {d['tot_gross']:.2f} KG", "bold"),
         Ps(f"Volume: {d['tot_cbm']:.4f} CBM", "bold")],
        [Ps("CERTIFIED BY", "lbl"),
         Spacer(1, 4*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"{d['signatory']}  |  {d['shipper_name']}", "sm"),
         Ps(f"Date: {d['date'].strftime('%d %b %Y')}", "sm")],
    ]], colWidths=[93*mm, 93*mm])
    foot.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#B2EBF2")),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, -1), LTEAL),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(foot)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["DHL-GF-Standard", "Detailed-Warehouse-Style", "ECommerce-Fulfillment-Style"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"packing_list_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Build format-conditional fields
    # Common fields rendered in all three formats:
    fields = {
        "shipper_name": d["shipper_name"],
        "shipper_address": d["shipper_address"],
        "consignee_name": d["consignee_name"],
        "consignee_address": d["consignee_address"],
        "invoice_number": d["invoice_no"],
        "reference": d["reference"],
        "bl_awb_number": d["bl_awb"],
        "po_number": d["po_no"],
        "date": d["date"].strftime("%Y-%m-%d"),
        "mode_of_transport": d["mode"],
        "carrier": d["carrier"],
        "incoterms": d["incoterms"],
        "total_packages": d["tot_pkgs"],
        "total_net_weight_kg": d["tot_net"],
        "total_gross_weight_kg": d["tot_gross"],
        "total_qty": d["tot_qty"],
        "signatory": d["signatory"],
        "line_items": d["items"],
    }
    # fmt1 (DHL-GF-Standard): renders total_cbm in TOTALS signature block;
    #                          also renders shipper_phone, shipper_email, consignee_phone
    if fmt_idx == 0:
        fields["shipper_phone"] = d["shipper_phone"]
        fields["shipper_email"] = d["shipper_email"]
        fields["consignee_phone"] = d["consignee_phone"]
        fields["total_cbm"] = d["tot_cbm"]
    # fmt2 (Detailed-Warehouse-Style): renders package_type_summary;
    #                                   does NOT render total_cbm (no CBM column or total)
    if fmt_idx == 1:
        fields["shipper_phone"] = d["shipper_phone"]
        fields["shipper_email"] = d["shipper_email"]
        fields["consignee_phone"] = d["consignee_phone"]
        fields["package_type_summary"] = d["type_summary"]
    # fmt3 (ECommerce-Fulfillment-Style): renders order_ref and total_cbm in summary footer;
    #                                      renders consignee_phone
    if fmt_idx == 2:
        fields["order_reference"] = d["order_ref"]
        fields["consignee_phone"] = d["consignee_phone"]
        fields["total_cbm"] = d["tot_cbm"]

    ann = {
        "document_id":    fname.replace(".pdf", ""),
        "document_class": "Packing List",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    8,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf", ".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} Packing List documents (3 format variants)...")
    for i in range(1, count + 1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            print(f"  [{i:04d}] {a['format_variant'][:28]:<28}  Inv: {f['invoice_number']}  "
                  f"Pkgs: {f['total_packages']}  Net: {f['total_net_weight_kg']:.1f} KG")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate synthetic Packing List documents")
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
