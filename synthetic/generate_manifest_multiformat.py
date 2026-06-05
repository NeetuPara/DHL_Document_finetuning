"""
Cargo Manifest — 3 distinct real-world format variants.
Format 1: Air Cargo Manifest (CBP 7509 style) — landscape
Format 2: Ocean Vessel Cargo Manifest — landscape
Format 3: Consolidated Freight Manifest (LCL/groupage) — landscape
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

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "10_Cargo_Manifest"
PDF_DIR, ANN_DIR = OUT_DIR / "pdfs", OUT_DIR / "annotations"

WL = 267 * mm   # landscape usable width
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
    mtype = random.choice(["Air", "Ocean", "Consolidated"])

    dep = random.choice(AIRPORTS)
    dst = random.choice(AIRPORTS)
    while dst[1] == dep[1]: dst = random.choice(AIRPORTS)
    pol = random.choice(PORTS_SEA)
    pod = random.choice(PORTS_SEA)
    while pod == pol: pod = random.choice(PORTS_SEA)

    carrier = random.choice(["DHL Air", "Emirates SkyCargo", "Lufthansa Cargo",
                              "Maersk Line", "MSC", "CMA CGM", "COSCO Shipping",
                              "Evergreen Marine", "Hapag-Lloyd", "ONE"])
    vessel = random.choice(VESSEL_NAMES)
    flight_no = f"{random.choice(['DL', 'LH', 'EK', 'QR', 'SQ', 'CX'])}{random.randint(100, 999)}"
    voyage_no = f"{random.randint(100, 999)}{''.join(random.choices('NESW', k=1))}"

    n_entries = random.randint(8, 20)
    entries = []
    for _ in range(n_entries):
        cat = random.choice(COMMODITY_CATEGORIES)
        sc = random_country(); rc = random_country()
        while rc[1] == sc[1]: rc = random_country()
        n_pkgs = random.randint(1, 50)
        gw = round(random.uniform(10, 5000), 1)
        cbm = round(n_pkgs * random.uniform(0.01, 0.15), 3)
        entries.append({
            "ref_no": random_hawb_number() if mtype != "Ocean" else random_bl_number(),
            "shipper": random_company(),
            "consignee": random_company(),
            "origin": sc[0],
            "destination": rc[0],
            "n_pkgs": n_pkgs,
            "pkg_type": random.choice(PACKAGE_TYPES),
            "description": cat["description"][:35],
            "hs_code": cat["hs_code"],
            "gross_weight": gw,
            "cbm": cbm,
            "freight_terms": random.choice(["Prepaid", "Collect", "As Arranged"]),
            "marks": f"{fake.bothify('???')}/{random.randint(1, 99)}",
        })

    tot_pkgs = sum(e["n_pkgs"] for e in entries)
    tot_wt = round(sum(e["gross_weight"] for e in entries), 1)
    tot_cbm = round(sum(e["cbm"] for e in entries), 3)

    flag = random.choice(["Panama", "Liberia", "Marshall Islands", "Bahamas", "Singapore"])
    agent_name = random_company()
    master = fake.name()

    return dict(
        manifest_no=f"MFT-{fake.bothify('####-######')}",
        manifest_type=mtype,
        flight_no=flight_no, vessel=vessel, voyage_no=voyage_no,
        carrier=carrier, flag=flag,
        dep_airport=dep, dst_airport=dst,
        port_of_loading=pol, port_of_discharge=pod,
        issue_date=fake.date_between(start_date="-1y", end_date="today"),
        agent_name=agent_name, master=master,
        entries=entries,
        tot_pkgs=tot_pkgs, tot_wt=tot_wt, tot_cbm=tot_cbm,
        consolidation_ref=f"MBL-{fake.bothify('########')}",
        consolidator=random_company(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — Air Cargo Manifest (CBP 7509 style)
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    NAVY = colors.HexColor("#00205B")
    LIGHT = colors.HexColor("#E8EDF5")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=colors.white),
        "lbl":    S("l", fontSize=6, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=7),
        "sm":     S("sm", fontSize=6, leading=7.5),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=5.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=5.5, leading=7),
        "cdr":    S("cdr", fontSize=5.5, leading=7, alignment=TA_RIGHT),
        "cdc":    S("cdc", fontSize=5.5, leading=7, alignment=TA_CENTER),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=7),
        "form":   S("fm", fontSize=8, textColor=NAVY, fontName="Helvetica-Bold"),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4),
                            leftMargin=10*mm, rightMargin=10*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    # Title
    story.append(Table([[
        [Ps("U.S. CUSTOMS AND BORDER PROTECTION", "form"),
         Ps("AIR CARGO MANIFEST — CBP FORM 7509", "form")],
        Ps("AIR CARGO MANIFEST", "title"),
        [Ps(f"Manifest No: {d['manifest_no']}", "bold"),
         Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
    ]], colWidths=[90*mm, 107*mm, 70*mm]))
    story[-1].setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), NAVY),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Spacer(1, 1*mm))

    # Flight + route header
    flt_t = Table([[
        Ps("FLIGHT NUMBER", "lbl"), Ps(d["flight_no"], "val"),
        Ps("FLIGHT DATE", "lbl"), Ps(d["issue_date"].strftime("%d %b %Y"), "val"),
        Ps("CARRIER", "lbl"), Ps(d["carrier"], "val"),
        Ps("DEPARTURE AIRPORT", "lbl"), Ps(f"{d['dep_airport'][1]} — {d['dep_airport'][0]}", "val"),
        Ps("DESTINATION AIRPORT", "lbl"), Ps(f"{d['dst_airport'][1]} — {d['dst_airport'][0]}", "val"),
    ]], colWidths=[24*mm, 22*mm, 20*mm, 22*mm, 20*mm, 32*mm, 30*mm, 48*mm, 30*mm, 39*mm])
    flt_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, 0), LIGHT), ("BACKGROUND", (2, 0), (2, 0), LIGHT),
        ("BACKGROUND", (4, 0), (4, 0), LIGHT), ("BACKGROUND", (6, 0), (6, 0), LIGHT),
        ("BACKGROUND", (8, 0), (8, 0), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(flt_t)
    story.append(Spacer(1, 1*mm))

    # Entries table
    CW = [30*mm, 26*mm, 26*mm, 18*mm, 18*mm, 14*mm, 16*mm, 32*mm, 18*mm, 16*mm, 14*mm]
    rows = [[
        Ps("AWB NUMBER", "ch"), Ps("SHIPPER", "ch"), Ps("CONSIGNEE", "ch"),
        Ps("CTRY\nORIGIN", "ch"), Ps("CTRY\nDEST", "ch"),
        Ps("PKGS", "ch"), Ps("TYPE", "ch"),
        Ps("DESCRIPTION", "ch"), Ps("GROSS WT\n(KG)", "ch"),
        Ps("VOL\n(CBM)", "ch"), Ps("REMARKS", "ch"),
    ]]
    n_data = len(d["entries"])
    for e in d["entries"]:
        rows.append([
            Ps(e["ref_no"], "cd"), Ps(e["shipper"][:20], "cd"), Ps(e["consignee"][:20], "cd"),
            Ps(e["origin"][:10], "cdc"), Ps(e["destination"][:10], "cdc"),
            Ps(str(e["n_pkgs"]), "cdr"), Ps(e["pkg_type"][:8], "cdc"),
            Ps(e["description"][:30], "cd"),
            Ps(f"{e['gross_weight']:,.1f}", "cdr"),
            Ps(f"{e['cbm']:.3f}", "cdr"),
            Ps(e["freight_terms"][:8], "cdc"),
        ])
    # Totals
    rows.append([
        Ps("TOTALS", "bold"), Ps("", "cd"), Ps("", "cd"),
        Ps("", "cdc"), Ps("", "cdc"),
        Ps(str(d["tot_pkgs"]), "cdr"), Ps("", "cdc"),
        Ps(f"{n_data} shipments", "cd"),
        Ps(f"{d['tot_wt']:,.1f}", "cdr"),
        Ps(f"{d['tot_cbm']:.3f}", "cdr"),
        Ps("", "cdc"),
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
    story.append(Spacer(1, 2*mm))

    # Agent signature
    sig_t = Table([[
        [Ps("AGENT / CARRIER CERTIFICATION", "lbl"),
         Ps("I hereby certify that the above is a true and complete manifest of all articles "
            "loaded on this aircraft for this flight.", "sm"),
         Spacer(1, 4*mm),
         Ps("Agent Signature: _______________________________", "sm"),
         Ps(f"{d['agent_name']}  |  Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
        [Ps("CBP USE ONLY", "lbl"),
         Ps("Inspector: ______________", "sm"),
         Ps("Badge No: ______________", "sm"),
         Ps("Port Code: ______________", "sm"),
         Ps("Date: ______________", "sm")],
    ]], colWidths=[180*mm, 87*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — Ocean Vessel Cargo Manifest
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    TEAL2 = colors.HexColor("#004D40")
    LTEAL = colors.HexColor("#E0F2F1")
    MTEAL = colors.HexColor("#B2DFDB")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=colors.white),
        "lbl":    S("l", fontSize=6, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=7),
        "sm":     S("sm", fontSize=6, leading=7.5),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=5.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=5.5, leading=7),
        "cdr":    S("cdr", fontSize=5.5, leading=7, alignment=TA_RIGHT),
        "cdc":    S("cdc", fontSize=5.5, leading=7, alignment=TA_CENTER),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=7),
        "vessel": S("vs", fontName="Helvetica-Bold", fontSize=10, textColor=TEAL2),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4),
                            leftMargin=10*mm, rightMargin=10*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    story.append(Table([[
        [Ps("OCEAN VESSEL CARGO MANIFEST", "vessel"),
         Ps(f"Manifest No: {d['manifest_no']}", "bold"),
         Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
        Ps("OCEAN VESSEL CARGO MANIFEST", "title"),
        [Ps(f"Carrier: {d['carrier']}", "val"),
         Ps("NOT NEGOTIABLE", "sm")],
    ]], colWidths=[100*mm, 97*mm, 70*mm]))
    story[-1].setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), TEAL2),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Spacer(1, 1*mm))

    # Vessel details
    vsl_t = Table([[
        Ps("VESSEL NAME", "lbl"), Ps(d["vessel"], "val"),
        Ps("VOYAGE NO.", "lbl"), Ps(d["voyage_no"], "val"),
        Ps("FLAG", "lbl"), Ps(d["flag"], "val"),
        Ps("PORT OF LOADING", "lbl"), Ps(d["port_of_loading"], "val"),
        Ps("PORT OF DISCHARGE", "lbl"), Ps(d["port_of_discharge"], "val"),
    ]], colWidths=[24*mm, 38*mm, 20*mm, 20*mm, 14*mm, 24*mm, 30*mm, 42*mm, 30*mm, 45*mm])
    vsl_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, 0), LTEAL), ("BACKGROUND", (2, 0), (2, 0), LTEAL),
        ("BACKGROUND", (4, 0), (4, 0), LTEAL), ("BACKGROUND", (6, 0), (6, 0), LTEAL),
        ("BACKGROUND", (8, 0), (8, 0), LTEAL),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(vsl_t)
    story.append(Spacer(1, 1*mm))

    # Entries table
    CW = [30*mm, 24*mm, 24*mm, 16*mm, 12*mm, 32*mm, 18*mm, 18*mm, 16*mm, 20*mm, 47*mm]
    rows = [[
        Ps("B/L NUMBER", "ch"), Ps("SHIPPER", "ch"), Ps("CONSIGNEE", "ch"),
        Ps("MARKS &\nNUMBERS", "ch"), Ps("NO.\nPKGS", "ch"),
        Ps("DESCRIPTION OF GOODS", "ch"), Ps("HS CODE", "ch"),
        Ps("GROSS WT\n(KG)", "ch"), Ps("CBM", "ch"),
        Ps("FREIGHT\nTERMS", "ch"), Ps("REMARKS", "ch"),
    ]]
    n_data = len(d["entries"])
    for e in d["entries"]:
        rows.append([
            Ps(e["ref_no"], "cd"), Ps(e["shipper"][:20], "cd"), Ps(e["consignee"][:20], "cd"),
            Ps(e["marks"], "cdc"), Ps(str(e["n_pkgs"]), "cdr"),
            Ps(e["description"][:28], "cd"),
            Ps(e["hs_code"], "cdc"),
            Ps(f"{e['gross_weight']:,.1f}", "cdr"),
            Ps(f"{e['cbm']:.3f}", "cdr"),
            Ps(e["freight_terms"][:10], "cdc"),
            Ps("", "cd"),
        ])
    # Totals
    rows.append([
        Ps("TOTALS", "bold"), Ps("", "cd"), Ps("", "cd"),
        Ps("", "cdc"), Ps(str(d["tot_pkgs"]), "cdr"),
        Ps(f"{n_data} B/Ls", "cd"), Ps("", "cdc"),
        Ps(f"{d['tot_wt']:,.1f}", "cdr"),
        Ps(f"{d['tot_cbm']:.3f}", "cdr"),
        Ps("", "cdc"), Ps("", "cd"),
    ])

    stripe = [("BACKGROUND", (0, r), (-1, r), LTEAL) for r in range(1, n_data + 1) if r % 2 == 0]
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL2), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), MTEAL), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(it_t)
    story.append(Spacer(1, 2*mm))

    # Master signature
    sig_t = Table([[
        [Ps("MASTER'S CERTIFICATION", "lbl"),
         Ps("I, the undersigned Master of the above-named vessel, hereby certify that this is a true "
            "and complete manifest of all cargo laden on board at the port of loading.", "sm"),
         Spacer(1, 4*mm),
         Ps("Master Signature: _______________________________", "sm"),
         Ps(f"Master: {d['master']}  |  Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
        [Ps("AGENT DETAILS", "lbl"),
         Ps(d["agent_name"], "val"),
         Spacer(1, 2*mm),
         Ps(f"Vessel: {d['vessel']}", "sm"),
         Ps(f"Voyage: {d['voyage_no']}", "sm"),
         Ps(f"Flag: {d['flag']}", "sm")],
    ]], colWidths=[175*mm, 92*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — Consolidated Freight Manifest (LCL/groupage)
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    PURPLE = colors.HexColor("#4A148C")
    LPURP = colors.HexColor("#F3E5F5")
    MPURP = colors.HexColor("#E1BEE7")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=colors.white),
        "lbl":    S("l", fontSize=6, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=7),
        "sm":     S("sm", fontSize=6, leading=7.5),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=5.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=5.5, leading=7),
        "cdr":    S("cdr", fontSize=5.5, leading=7, alignment=TA_RIGHT),
        "cdc":    S("cdc", fontSize=5.5, leading=7, alignment=TA_CENTER),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=7),
        "hdr2":   S("h2", fontName="Helvetica-Bold", fontSize=8, textColor=PURPLE),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4),
                            leftMargin=10*mm, rightMargin=10*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    story.append(Table([[
        [Ps("CONSOLIDATED FREIGHT MANIFEST", "hdr2"),
         Ps(f"Consolidator: {d['consolidator']}", "sm")],
        Ps("CONSOLIDATED FREIGHT MANIFEST (LCL/GROUPAGE)", "title"),
        [Ps(f"Manifest No: {d['manifest_no']}", "bold"),
         Ps(f"MBL/MAWB: {d['consolidation_ref']}", "sm"),
         Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
    ]], colWidths=[88*mm, 107*mm, 72*mm]))
    story[-1].setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), PURPLE),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Spacer(1, 1*mm))

    # Consolidator + route details
    cons_t = Table([[
        Ps("CONSOLIDATOR", "lbl"), Ps(d["consolidator"], "val"),
        Ps("MBL / MAWB REF", "lbl"), Ps(d["consolidation_ref"], "val"),
        Ps("CARRIER", "lbl"), Ps(d["carrier"], "val"),
        Ps("PORT / AIRPORT OF LOADING", "lbl"), Ps(d["port_of_loading"], "val"),
        Ps("PORT / AIRPORT OF DISCHARGE", "lbl"), Ps(d["port_of_discharge"], "val"),
    ]], colWidths=[24*mm, 40*mm, 24*mm, 34*mm, 20*mm, 32*mm, 38*mm, 34*mm, 38*mm, 33*mm])
    cons_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, 0), LPURP), ("BACKGROUND", (2, 0), (2, 0), LPURP),
        ("BACKGROUND", (4, 0), (4, 0), LPURP), ("BACKGROUND", (6, 0), (6, 0), LPURP),
        ("BACKGROUND", (8, 0), (8, 0), LPURP),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(cons_t)
    story.append(Spacer(1, 1*mm))

    story.append(Ps("INDIVIDUAL SHIPMENT BREAKDOWN", "hdr2"))
    story.append(Spacer(1, 1*mm))

    # HBL breakdown table
    CW = [30*mm, 24*mm, 26*mm, 14*mm, 12*mm, 32*mm, 16*mm, 16*mm, 20*mm, 24*mm, 53*mm]
    rows = [[
        Ps("HBL / HAWB NUMBER", "ch"), Ps("SHIPPER", "ch"), Ps("CONSIGNEE", "ch"),
        Ps("PIECES", "ch"), Ps("PKG\nTYPE", "ch"),
        Ps("DESCRIPTION", "ch"), Ps("WEIGHT\n(KG)", "ch"),
        Ps("CBM", "ch"), Ps("DESTINATION", "ch"),
        Ps("FREIGHT\nTERMS", "ch"), Ps("REMARKS", "ch"),
    ]]
    n_data = len(d["entries"])
    for e in d["entries"]:
        rows.append([
            Ps(e["ref_no"], "cd"),
            Ps(e["shipper"][:18], "cd"),
            Ps(e["consignee"][:18], "cd"),
            Ps(str(e["n_pkgs"]), "cdr"),
            Ps(e["pkg_type"][:6], "cdc"),
            Ps(e["description"][:28], "cd"),
            Ps(f"{e['gross_weight']:,.1f}", "cdr"),
            Ps(f"{e['cbm']:.3f}", "cdr"),
            Ps(e["destination"][:14], "cdc"),
            Ps(e["freight_terms"][:10], "cdc"),
            Ps("", "cd"),
        ])
    rows.append([
        Ps("CONSOLIDATION TOTAL", "bold"), Ps("", "cd"), Ps("", "cd"),
        Ps(str(d["tot_pkgs"]), "cdr"), Ps("", "cdc"),
        Ps(f"{n_data} HBLs / HAWBs", "cd"),
        Ps(f"{d['tot_wt']:,.1f}", "cdr"),
        Ps(f"{d['tot_cbm']:.3f}", "cdr"),
        Ps("", "cdc"), Ps("", "cdc"), Ps("", "cd"),
    ])

    stripe = [("BACKGROUND", (0, r), (-1, r), LPURP) for r in range(1, n_data + 1) if r % 2 == 0]
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), MPURP), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(it_t)
    story.append(Spacer(1, 2*mm))

    # Summary + signature
    sig_t = Table([[
        [Ps("CONSOLIDATOR CERTIFICATION", "lbl"),
         Ps("I hereby certify that this is a true and accurate manifest of all consignments "
            "included in this consolidated shipment under the referenced Master B/L or MAWB.", "sm"),
         Spacer(1, 4*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"{d['agent_name']}  |  Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
        [Ps("SUMMARY", "lbl"),
         Ps(f"Total HBLs/HAWBs: {n_data}", "bold"),
         Ps(f"Total Pieces: {d['tot_pkgs']}", "bold"),
         Ps(f"Total Weight: {d['tot_wt']:,.1f} KG", "bold"),
         Ps(f"Total Volume: {d['tot_cbm']:.3f} CBM", "bold"),
         Spacer(1, 2*mm),
         Ps(f"MBL Ref: {d['consolidation_ref']}", "sm")],
    ]], colWidths=[170*mm, 97*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["Air-Cargo-Manifest-CBP7509", "Ocean-Vessel-Cargo-Manifest", "Consolidated-Freight-Manifest-LCL"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"manifest_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Build format-conditional fields
    # Common fields rendered in all three formats:
    fields = {
        "manifest_number": d["manifest_no"],
        "carrier": d["carrier"],
        "port_of_loading": d["port_of_loading"],
        "port_of_discharge": d["port_of_discharge"],
        "issue_date": d["issue_date"].strftime("%Y-%m-%d"),
        "agent_name": d["agent_name"],
        "total_entries": len(d["entries"]),
        "total_packages": d["tot_pkgs"],
        "total_weight_kg": d["tot_wt"],
        "total_cbm": d["tot_cbm"],
        "entries": d["entries"],
    }
    # fmt1 (Air-Cargo-Manifest-CBP7509): renders flight_number, departure_airport,
    #                                     destination_airport; uses airports not sea ports
    if fmt_idx == 0:
        fields["flight_number"] = d["flight_no"]
        fields["departure_airport"] = d["dep_airport"][1]
        fields["destination_airport"] = d["dst_airport"][1]
    # fmt2 (Ocean-Vessel-Cargo-Manifest): renders vessel_name, voyage_number, flag, master;
    #                                      uses port_of_loading/discharge (already in common)
    if fmt_idx == 1:
        fields["vessel_name"] = d["vessel"]
        fields["voyage_number"] = d["voyage_no"]
        fields["flag"] = d["flag"]
        fields["master"] = d["master"]
    # fmt3 (Consolidated-Freight-Manifest-LCL): renders consolidation_ref, consolidator;
    #                                             uses port_of_loading/discharge (already in common)
    if fmt_idx == 2:
        fields["consolidation_ref"] = d["consolidation_ref"]
        fields["consolidator"] = d["consolidator"]
    # NOTE: manifest_type is never rendered as a labeled field in any PDF format — omitted.

    ann = {
        "document_id":    fname.replace(".pdf", ""),
        "document_class": "Cargo Manifest",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    10,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf", ".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} Cargo Manifest documents (3 format variants)...")
    for i in range(1, count + 1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            print(f"  [{i:04d}] {a['format_variant'][:30]:<30}  Manifest: {f['manifest_number']}  "
                  f"Entries: {f['total_entries']}  Wt: {f['total_weight_kg']:,.1f} KG")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate synthetic Cargo Manifest documents")
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
