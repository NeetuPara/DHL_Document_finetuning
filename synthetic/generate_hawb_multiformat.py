"""
House Airway Bill (HAWB) — 3 distinct real-world format variants.
Format 1: IATA Neutral HAWB — full IATA AWB format
Format 2: Express/DHL Courier AWB — DHL Express style
Format 3: Consolidated Air Cargo HAWB — multiple consignments
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

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "07_House_Airway_Bill"
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

    dep_apt = random.choice(AIRPORTS)
    dst_apt = random.choice(AIRPORTS)
    while dst_apt[1] == dep_apt[1]: dst_apt = random.choice(AIRPORTS)

    mid_apt = random.choice(AIRPORTS)
    while mid_apt[1] in (dep_apt[1], dst_apt[1]): mid_apt = random.choice(AIRPORTS)

    n_pieces = random.randint(1, 50)
    gross_wt = round(random.uniform(0.5, 500.0), 1)
    chargeable_wt = max(gross_wt, round(gross_wt * random.uniform(1.0, 1.3), 1))
    rate = round(random.uniform(1.5, 12.0), 2)
    total_charge = round(chargeable_wt * rate, 2)
    weight_charge = round(chargeable_wt * rate * 0.75, 2)
    other_charges = round(total_charge - weight_charge, 2)
    surcharge = round(random.uniform(5.0, 80.0), 2)
    fuel_surcharge = round(gross_wt * random.uniform(0.3, 1.2), 2)

    commodity = random.choice(COMMODITY_CATEGORIES)
    nature_of_goods = commodity["description"]
    hs_code = commodity["hs_code"]

    handling_codes = ["PIL", "VAL", "PER", "HEA", "AVI", "DGR", "HUM", "EAP", "SUR"]
    handling_info = random.choice([
        "NO SPECIAL HANDLING REQUIRED",
        f"HANDLING CODE: {random.choice(handling_codes)}",
        "KEEP DRY - FRAGILE",
        f"TEMP CONTROLLED: {random.randint(2, 8)}°C - {random.randint(10, 25)}°C",
        "RUSH - PRIORITY HANDLING",
    ])

    rate_class = random.choice(["N", "Q", "B", "M", "R", "U", "C", "E"])
    commodity_no = fake.bothify("###.##")
    charge_code = random.choice(["PP", "CC"])

    iata_code = fake.bothify("##-###")
    agent_cass = fake.bothify("####-####")
    airline_code = random.choice(["020", "074", "176", "057", "618", "085"])

    issue_date = fake.date_between(start_date="-1y", end_date="today")
    signatory = fake.name()

    declared_value_carriage = random.choice(["NVD", f"{random.choice(CURRENCIES)} {round(random.uniform(100, 50000), 2):,.2f}"])
    declared_value_customs = random.choice(["NCV", f"{random.choice(CURRENCIES)} {round(random.uniform(100, 50000), 2):,.2f}"])

    # Sub-shipments for fmt3
    n_sub = random.randint(3, 8)
    sub_shipments = []
    for _ in range(n_sub):
        sub_apt = random.choice(AIRPORTS)
        sub_cat = random.choice(COMMODITY_CATEGORIES)
        sub_pcs = random.randint(1, 20)
        sub_wt = round(random.uniform(0.5, 100.0), 1)
        sub_shipments.append({
            "hawb_ref": random_hawb_number(),
            "pieces": sub_pcs,
            "weight": sub_wt,
            "destination": sub_apt[1],
            "consignee": random_company(),
            "description": sub_cat["description"][:35],
        })

    return dict(
        hawb_number=random_hawb_number(),
        mawb_number=random_mawb_number(),
        shipper_name=random_company(), shipper_address=fake.address().replace("\n", ", ") + f", {sc[0]}",
        shipper_acct=fake.bothify("DHL-#########"),
        consignee_name=random_company(), consignee_address=fake.address().replace("\n", ", ") + f", {rc[0]}",
        agent_name=random_company(), iata_code=iata_code, agent_cass=agent_cass,
        airport_departure=dep_apt, airport_destination=dst_apt, airport_transit=mid_apt,
        airline_code=airline_code,
        currency=random.choice(CURRENCIES),
        charge_code=charge_code,
        declared_value_carriage=declared_value_carriage,
        declared_value_customs=declared_value_customs,
        n_pieces=n_pieces, gross_weight_kg=gross_wt,
        chargeable_weight=chargeable_wt,
        rate=rate, rate_class=rate_class, commodity_no=commodity_no,
        total_charge=total_charge, weight_charge=weight_charge,
        other_charges=other_charges, surcharge=surcharge, fuel_surcharge=fuel_surcharge,
        nature_of_goods=nature_of_goods, hs_code=hs_code,
        handling_info=handling_info,
        issue_date=issue_date, signatory=signatory,
        service_type=random.choice(["EXPRESS", "ECONOMY", "MEDICAL", "PRIORITY", "STANDARD"]),
        dims_l=round(random.uniform(10, 120), 1),
        dims_w=round(random.uniform(10, 100), 1),
        dims_h=round(random.uniform(5, 80), 1),
        shipper_country=sc, consignee_country=rc,
        special_handling=random.choice([True, False]),
        sub_shipments=sub_shipments,
        consolidation_ref=f"CONS-{fake.bothify('####-######')}",
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — IATA Neutral HAWB
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    NAVY = colors.HexColor("#00205B")
    LIGHT = colors.HexColor("#E8EDF5")
    st = {
        "title": S("t", fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER, textColor=colors.white),
        "hdr":   S("h", fontName="Helvetica-Bold", fontSize=7, textColor=NAVY),
        "lbl":   S("l", fontSize=6.5, textColor=colors.HexColor("#555555")),
        "val":   S("v", fontName="Helvetica-Bold", fontSize=7.5),
        "sm":    S("sm", fontSize=7, leading=8.5),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=6.5, leading=8),
        "cdr":   S("cdr", fontSize=6.5, leading=8, alignment=TA_RIGHT),
        "cdc":   S("cdc", fontSize=6.5, leading=8, alignment=TA_CENTER),
        "bold":  S("b", fontName="Helvetica-Bold", fontSize=7.5),
        "large": S("lg", fontName="Helvetica-Bold", fontSize=10, textColor=NAVY),
    }
    def Ps(t, s): return P(t, st[s])
    def lv(label, val): return [Ps(label, "lbl"), Ps(val, "val")]

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=10*mm, rightMargin=10*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    # Title banner
    story.append(Table([[Ps("AIR WAYBILL — HOUSE (HAWB)", "title"),
                         Ps("NOT NEGOTIABLE", "title")]],
                       colWidths=[130*mm, 56*mm],
                       style=TableStyle([
                           ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                           ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("BOX", (0, 0), (-1, -1), .5, BORDER),
                           ("INNERGRID", (0, 0), (-1, -1), .5, colors.white),
                       ])))
    story.append(Spacer(1, 1*mm))

    # AWB numbers block
    awb_row = Table([[
        [Ps("HOUSE AWB NO.", "lbl"), Ps(d["hawb_number"], "large")],
        [Ps("MASTER AWB NO.", "lbl"), Ps(d["mawb_number"], "large")],
        [Ps("AIRLINE CODE", "lbl"), Ps(d["airline_code"], "val"),
         Ps("IATA AGENT CODE", "lbl"), Ps(d["iata_code"], "val")],
        [Ps("AGENT CASS NO.", "lbl"), Ps(d["agent_cass"], "val"),
         Ps("ISSUE DATE", "lbl"), Ps(d["issue_date"].strftime("%d %b %Y"), "val")],
    ]], colWidths=[W])
    awb_row.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(awb_row)
    story.append(Spacer(1, 1*mm))

    # Shipper / Consignee / Agent block
    party_t = Table([[
        [Ps("SHIPPER / EXPORTER", "lbl"), Ps(d["shipper_name"], "val"),
         Ps(d["shipper_address"], "sm"),
         Ps(f"Account: {d['shipper_acct']}", "sm")],
        [Ps("CONSIGNEE", "lbl"), Ps(d["consignee_name"], "val"),
         Ps(d["consignee_address"], "sm")],
        [Ps("ISSUING CARRIER'S AGENT / IATA", "lbl"), Ps(d["agent_name"], "val"),
         Ps(f"IATA Code: {d['iata_code']}", "sm"),
         Ps(f"CASS No: {d['agent_cass']}", "sm")],
    ]], colWidths=[62*mm, 62*mm, 62*mm])
    party_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(party_t)
    story.append(Spacer(1, 1*mm))

    # Routing block
    routing_t = Table([
        [Ps("AIRPORT OF DEPARTURE", "lbl"), Ps("ROUTING / TRANSFER", "lbl"),
         Ps("AIRPORT OF DESTINATION", "lbl"), Ps("FLIGHT / DATE", "lbl")],
        [Ps(f"{d['airport_departure'][0]} ({d['airport_departure'][1]})", "val"),
         Ps(f"Via {d['airport_transit'][1]}", "val"),
         Ps(f"{d['airport_destination'][0]} ({d['airport_destination'][1]})", "val"),
         Ps(f"DHL{random.randint(100,999)} / {d['issue_date'].strftime('%d%b').upper()}", "val")],
    ], colWidths=[55*mm, 40*mm, 61*mm, 30*mm])
    routing_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(routing_t)
    story.append(Spacer(1, 1*mm))

    # Declared values block
    decl_t = Table([
        [Ps("CURR.", "lbl"), Ps("CHGS CODE", "lbl"),
         Ps("DECLARED VALUE FOR CARRIAGE", "lbl"), Ps("DECLARED VALUE FOR CUSTOMS", "lbl"),
         Ps("AMT. OF INSURANCE", "lbl")],
        [Ps(d["currency"], "val"), Ps(d["charge_code"], "val"),
         Ps(d["declared_value_carriage"], "val"),
         Ps(d["declared_value_customs"], "val"),
         Ps("NIL", "val")],
    ], colWidths=[18*mm, 26*mm, 54*mm, 54*mm, 34*mm])
    decl_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(decl_t)
    story.append(Spacer(1, 1*mm))

    # Rate table header
    CW = [14*mm, 20*mm, 12*mm, 16*mm, 20*mm, 22*mm, 16*mm, 18*mm, 48*mm]
    rate_rows = [[
        Ps("PIECES", "ch"), Ps("GROSS WT", "ch"), Ps("KG/LB", "ch"),
        Ps("RATE CLASS", "ch"), Ps("COMMODITY#", "ch"), Ps("CHGBLE WT", "ch"),
        Ps("RATE", "ch"), Ps("TOTAL", "ch"), Ps("NATURE & QUANTITY OF GOODS", "ch"),
    ]]
    n_data = 1
    rate_rows.append([
        Ps(str(d["n_pieces"]), "cdc"), Ps(f"{d['gross_weight_kg']:.1f}", "cdr"),
        Ps("K", "cdc"), Ps(d["rate_class"], "cdc"),
        Ps(d["commodity_no"], "cdc"), Ps(f"{d['chargeable_weight']:.1f}", "cdr"),
        Ps(f"{d['rate']:.2f}", "cdr"), Ps(f"{d['total_charge']:,.2f}", "cdr"),
        Ps(d["nature_of_goods"], "cd"),
    ])
    # Add blank rows
    for _ in range(2):
        rate_rows.append([Ps("", "cd")] * 9)
        n_data += 1
    n_data = 3

    stripe = [("BACKGROUND", (0, r), (-1, r), LIGHT) for r in range(1, n_data + 1) if r % 2 == 0]
    rt = Table(rate_rows, colWidths=CW, repeatRows=1)
    rt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(rt)
    story.append(Spacer(1, 1*mm))

    # Handling info
    hdl_t = Table([[
        [Ps("HANDLING INFORMATION", "lbl"), Ps(d["handling_info"], "sm")],
        [Ps("HS CODE", "lbl"), Ps(d["hs_code"], "val"),
         Ps("NO. OF PIECES", "lbl"), Ps(str(d["n_pieces"]), "val")],
    ]], colWidths=[W])
    hdl_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(hdl_t)
    story.append(Spacer(1, 1*mm))

    # Charge breakdown
    chg_t = Table([
        [Ps("WEIGHT CHARGE", "lbl"), Ps("OTHER CHARGES", "lbl"),
         Ps("FUEL SURCHARGE", "lbl"), Ps("TOTAL CHARGES", "lbl")],
        [Ps(f"{d['currency']} {d['weight_charge']:,.2f}", "val"),
         Ps(f"{d['currency']} {d['other_charges']:,.2f}", "val"),
         Ps(f"{d['currency']} {d['fuel_surcharge']:,.2f}", "val"),
         Ps(f"{d['currency']} {d['total_charge']:,.2f}", "bold")],
        [Ps(f"CHARGE CODE: {d['charge_code']}  (PP=Prepaid / CC=Collect)", "sm"),
         "", "", ""],
    ], colWidths=[46*mm, 46*mm, 46*mm, 48*mm])
    chg_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("SPAN", (0, 2), (-1, 2)),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(chg_t)
    story.append(Spacer(1, 2*mm))

    # Signature block
    sig_t = Table([[
        [Ps("SIGNATURE OF SHIPPER OR AGENT", "lbl"), Spacer(1, 5*mm),
         Ps(f"Signed: ________________________________", "sm"),
         Ps(f"{d['signatory']}  —  {d['agent_name']}", "sm"),
         Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
        [Ps("EXECUTED ON (DATE)", "lbl"), Ps(d["issue_date"].strftime("%d %B %Y"), "val"),
         Spacer(1, 2*mm),
         Ps("AT (PLACE)", "lbl"), Ps(d["airport_departure"][0], "val"),
         Spacer(1, 2*mm),
         Ps("ORIGINAL 3 (FOR SHIPPER)", "bold")],
    ]], colWidths=[93*mm, 93*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — Express / DHL Courier AWB style
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    RED = colors.HexColor("#D40511")
    LGRAY = colors.HexColor("#F5F5F5")
    DGRAY = colors.HexColor("#333333")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=14, alignment=TA_CENTER, textColor=colors.white),
        "wbno":   S("wbno", fontName="Helvetica-Bold", fontSize=16, textColor=RED),
        "lbl":    S("l", fontSize=6.5, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=8),
        "sm":     S("sm", fontSize=7, leading=9),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=7, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=7, leading=9),
        "cdc":    S("cdc", fontSize=7, leading=9, alignment=TA_CENTER),
        "cdr":    S("cdr", fontSize=7, leading=9, alignment=TA_RIGHT),
        "svc":    S("svc", fontName="Helvetica-Bold", fontSize=9, alignment=TA_CENTER, textColor=RED),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=8),
        "chk":    S("chk", fontSize=9),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    # Header banner
    story.append(Table([[
        Ps("DHL EXPRESS", "title"),
        Ps("AIR WAYBILL", "title"),
    ]], colWidths=[93*mm, 93*mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), RED),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("INNERGRID", (0, 0), (-1, -1), .5, colors.white),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
    ])))
    story.append(Spacer(1, 2*mm))

    # Waybill number + service type
    top_t = Table([[
        [Ps("WAYBILL NUMBER", "lbl"), Ps(d["hawb_number"], "wbno")],
        [Ps("SERVICE TYPE", "lbl"), Ps(d["service_type"], "svc"),
         Spacer(1, 1*mm),
         Table([[
             Ps("[ ] PRIORITY", "chk"),
             Ps(f"[{'X' if d['service_type'] == 'EXPRESS' else ' '}] EXPRESS", "chk"),
             Ps(f"[{'X' if d['service_type'] == 'ECONOMY' else ' '}] ECONOMY", "chk"),
             Ps(f"[{'X' if d['service_type'] == 'MEDICAL' else ' '}] MEDICAL", "chk"),
         ]], colWidths=[30*mm]*4, style=TableStyle([
             ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
         ]))],
        [Ps("MASTER AWB REF", "lbl"), Ps(d["mawb_number"], "val")],
        [Ps("DATE OF ISSUE", "lbl"), Ps(d["issue_date"].strftime("%d %B %Y"), "val")],
    ]], colWidths=[W])
    top_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LGRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(top_t)
    story.append(Spacer(1, 1*mm))

    # From / To block
    from_to = Table([[
        [Ps("FROM (SHIPPER)", "lbl"), Ps(d["shipper_name"], "val"),
         Ps(d["shipper_address"], "sm"),
         Ps(f"DHL Acct: {d['shipper_acct']}", "sm")],
        [Ps("TO (CONSIGNEE)", "lbl"), Ps(d["consignee_name"], "val"),
         Ps(d["consignee_address"], "sm")],
    ]], colWidths=[93*mm, 93*mm])
    from_to.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .5, RED),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(from_to)
    story.append(Spacer(1, 1*mm))

    # Route block
    route_t = Table([[
        [Ps("ORIGIN", "lbl"), Ps(f"{d['airport_departure'][1]}", "val"),
         Ps(d["airport_departure"][0], "sm")],
        [Ps("DESTINATION", "lbl"), Ps(f"{d['airport_destination'][1]}", "val"),
         Ps(d["airport_destination"][0], "sm")],
        [Ps("CHARGE CODE", "lbl"), Ps(d["charge_code"], "val"),
         Ps("PP = Prepaid  |  CC = Collect", "sm")],
    ]], colWidths=[62*mm, 62*mm, 62*mm])
    route_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(route_t)
    story.append(Spacer(1, 1*mm))

    # Special handling checkboxes
    hdl_checks = [
        ("FRAGILE", random.choice([True, False])),
        ("KEEP UPRIGHT", random.choice([True, False])),
        ("TEMPERATURE SENSITIVE", random.choice([True, False])),
        ("DANGEROUS GOODS", False),
        ("VALUABLE CARGO", random.choice([True, False])),
        ("LIVE ANIMAL", False),
        ("PERISHABLE", random.choice([True, False])),
        ("OVERSIZED", random.choice([True, False])),
    ]
    chk_data = [[Ps(f"[{'X' if v else ' '}] {lbl}", "chk") for lbl, v in hdl_checks[:4]],
                [Ps(f"[{'X' if v else ' '}] {lbl}", "chk") for lbl, v in hdl_checks[4:]]]
    chk_t = Table([[
        [Ps("SPECIAL HANDLING", "lbl")] +
        [Table(chk_data, colWidths=[45*mm]*4, style=TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))]
    ]], colWidths=[W])
    chk_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LGRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(chk_t)
    story.append(Spacer(1, 1*mm))

    # Content + value table
    cont_t = Table([
        [Ps("CONTENT DESCRIPTION", "lbl"), Ps("DECLARED VALUE", "lbl"),
         Ps("CURRENCY", "lbl"), Ps("CHARGE CODE", "lbl")],
        [Ps(d["nature_of_goods"], "val"), Ps(d["declared_value_carriage"], "val"),
         Ps(d["currency"], "val"), Ps(d["charge_code"], "val")],
        [Ps(f"HS CODE: {d['hs_code']}", "sm"),
         Ps(f"CUSTOMS VALUE: {d['declared_value_customs']}", "sm"), "", ""],
    ], colWidths=[80*mm, 50*mm, 28*mm, 28*mm])
    cont_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
        ("SPAN", (0, 2), (1, 2)),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(cont_t)
    story.append(Spacer(1, 1*mm))

    # Weight / dimensions summary
    dim_str = f"{d['dims_l']} x {d['dims_w']} x {d['dims_h']} cm"
    wt_t = Table([
        [Ps("NO. OF PIECES", "lbl"), Ps("GROSS WEIGHT", "lbl"),
         Ps("CHARGEABLE WEIGHT", "lbl"), Ps("DIMENSIONS (L×W×H)", "lbl"),
         Ps("TOTAL CHARGES", "lbl")],
        [Ps(str(d["n_pieces"]), "val"), Ps(f"{d['gross_weight_kg']:.1f} KG", "val"),
         Ps(f"{d['chargeable_weight']:.1f} KG", "val"),
         Ps(dim_str, "val"),
         Ps(f"{d['currency']} {d['total_charge']:,.2f}", "bold")],
    ], colWidths=[28*mm, 34*mm, 38*mm, 44*mm, 42*mm])
    wt_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(wt_t)
    story.append(Spacer(1, 4*mm))

    # Signature
    sig_t = Table([[
        [Ps("SHIPPER'S CERTIFICATION", "lbl"),
         Ps("I certify that the particulars on the face hereof are correct and that insofar as any "
            "part of the consignment contains dangerous goods, such part is properly described by name "
            "and is in proper condition for carriage by air according to applicable national and "
            "international government regulations.", "sm"),
         Spacer(1, 4*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"{d['signatory']}  |  Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
        [Ps("CARRIER USE ONLY", "lbl"),
         Ps("Executed by carrier agent:", "sm"),
         Spacer(1, 4*mm),
         Ps("_______________________________", "sm"),
         Ps(d["agent_name"], "sm")],
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
# FORMAT 3 — Consolidated Air Cargo HAWB
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    GREEN = colors.HexColor("#1B5E20")
    LGREEN = colors.HexColor("#E8F5E9")
    MGREEN = colors.HexColor("#C8E6C9")
    st = {
        "title": S("t", fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER, textColor=colors.white),
        "lbl":   S("l", fontSize=6.5, textColor=colors.HexColor("#555555")),
        "val":   S("v", fontName="Helvetica-Bold", fontSize=8),
        "sm":    S("sm", fontSize=7, leading=8.5),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=6.5, leading=8),
        "cdr":   S("cdr", fontSize=6.5, leading=8, alignment=TA_RIGHT),
        "cdc":   S("cdc", fontSize=6.5, leading=8, alignment=TA_CENTER),
        "bold":  S("b", fontName="Helvetica-Bold", fontSize=8),
        "hdr2":  S("h2", fontName="Helvetica-Bold", fontSize=9, textColor=GREEN),
        "large": S("lg", fontName="Helvetica-Bold", fontSize=12, textColor=GREEN),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=10*mm, rightMargin=10*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    # Title
    story.append(Table([[
        Ps("CONSOLIDATED AIR CARGO — HOUSE AIR WAYBILL", "title"),
        Ps("CONSOLIDATION COPY", "title"),
    ]], colWidths=[130*mm, 56*mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("INNERGRID", (0, 0), (-1, -1), .5, colors.white),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
    ])))
    story.append(Spacer(1, 1*mm))

    # Master AWB + consolidation ref at top
    mawb_t = Table([[
        [Ps("MASTER AWB NUMBER", "lbl"), Ps(d["mawb_number"], "large")],
        [Ps("CONSOLIDATION REF", "lbl"), Ps(d["consolidation_ref"], "val")],
        [Ps("HAWB NUMBER", "lbl"), Ps(d["hawb_number"], "val")],
        [Ps("DATE", "lbl"), Ps(d["issue_date"].strftime("%d %b %Y"), "val")],
    ]], colWidths=[W])
    mawb_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(mawb_t)
    story.append(Spacer(1, 1*mm))

    # Agent + route block
    agent_route = Table([[
        [Ps("CONSOLIDATING AGENT", "lbl"), Ps(d["agent_name"], "val"),
         Ps(f"IATA Code: {d['iata_code']}", "sm"),
         Ps(f"CASS: {d['agent_cass']}", "sm")],
        [Ps("DEPARTURE", "lbl"),
         Ps(f"{d['airport_departure'][1]} — {d['airport_departure'][0]}", "val")],
        [Ps("DESTINATION", "lbl"),
         Ps(f"{d['airport_destination'][1]} — {d['airport_destination'][0]}", "val")],
        [Ps("CHARGE CODE / CURRENCY", "lbl"),
         Ps(f"{d['charge_code']} / {d['currency']}", "val")],
    ]], colWidths=[W])
    agent_route.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(agent_route)
    story.append(Spacer(1, 2*mm))

    # Sub-shipment breakdown table
    story.append(Ps("INDIVIDUAL SHIPMENT BREAKDOWN", "hdr2"))
    story.append(Spacer(1, 1*mm))

    n_sub = len(d["sub_shipments"])
    CW = [32*mm, 14*mm, 20*mm, 18*mm, 40*mm, 48*mm]
    sub_rows = [[
        Ps("HAWB REF", "ch"), Ps("PIECES", "ch"), Ps("WEIGHT (KG)", "ch"),
        Ps("DEST", "ch"), Ps("CONSIGNEE", "ch"), Ps("DESCRIPTION", "ch"),
    ]]
    for ss in d["sub_shipments"]:
        sub_rows.append([
            Ps(ss["hawb_ref"], "cd"),
            Ps(str(ss["pieces"]), "cdc"),
            Ps(f"{ss['weight']:.1f}", "cdr"),
            Ps(ss["destination"], "cdc"),
            Ps(ss["consignee"], "cd"),
            Ps(ss["description"], "cd"),
        ])

    stripe = [("BACKGROUND", (0, r), (-1, r), LGREEN) for r in range(1, n_sub + 1) if r % 2 == 0]
    sub_t = Table(sub_rows, colWidths=CW, repeatRows=1)
    sub_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(sub_t)
    story.append(Spacer(1, 2*mm))

    # Total summary
    total_pcs = sum(ss["pieces"] for ss in d["sub_shipments"])
    total_wt = sum(ss["weight"] for ss in d["sub_shipments"])
    summary_t = Table([
        [Ps("TOTAL SUMMARY", "lbl"), "", "", "", "", ""],
        [Ps(f"Total Sub-Shipments: {n_sub}", "bold"),
         Ps(f"Total Pieces: {total_pcs}", "bold"),
         Ps(f"Total Weight: {total_wt:.1f} KG", "bold"),
         Ps(f"Chargeable: {d['chargeable_weight']:.1f} KG", "bold"),
         Ps(f"Rate: {d['currency']} {d['rate']:.2f}/KG", "bold"),
         Ps(f"TOTAL: {d['currency']} {d['total_charge']:,.2f}", "bold")],
    ], colWidths=[32*mm, 28*mm, 32*mm, 30*mm, 32*mm, 42*mm])
    summary_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), MGREEN),
        ("BACKGROUND", (0, 1), (-1, 1), LGREEN),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("SPAN", (0, 0), (-1, 0)),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_t)
    story.append(Spacer(1, 2*mm))

    # Signature
    sig_t = Table([[
        [Ps("AGENT SIGNATURE", "lbl"), Spacer(1, 5*mm),
         Ps("Signature: ________________________________", "sm"),
         Ps(f"{d['signatory']}  |  {d['agent_name']}", "sm"),
         Ps(f"IATA: {d['iata_code']}  |  Date: {d['issue_date'].strftime('%d %b %Y')}", "sm")],
        [Ps("HANDLING INFORMATION", "lbl"),
         Ps(d["handling_info"], "sm"),
         Spacer(1, 2*mm),
         Ps(f"Declared Value (Carriage): {d['declared_value_carriage']}", "sm"),
         Ps(f"Declared Value (Customs): {d['declared_value_customs']}", "sm")],
    ]], colWidths=[93*mm, 93*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["IATA-Neutral-HAWB", "Express-DHL-Courier-AWB", "Consolidated-Air-Cargo-HAWB"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"hawb_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Build format-conditional fields
    # Common fields rendered in all three formats:
    fields = {
        "hawb_number": d["hawb_number"],
        "mawb_number": d["mawb_number"],
        "shipper_name": d["shipper_name"],
        "shipper_address": d["shipper_address"],
        "consignee_name": d["consignee_name"],
        "consignee_address": d["consignee_address"],
        "agent_name": d["agent_name"],
        "airport_departure": d["airport_departure"][1],
        "airport_destination": d["airport_destination"][1],
        "currency": d["currency"],
        "charge_code": d["charge_code"],
        "declared_value_carriage": d["declared_value_carriage"],
        "declared_value_customs": d["declared_value_customs"],
        "n_pieces": d["n_pieces"],
        "gross_weight_kg": d["gross_weight_kg"],
        "chargeable_weight": d["chargeable_weight"],
        "rate": d["rate"],
        "total_charge": d["total_charge"],
        "nature_of_goods": d["nature_of_goods"],
        "hs_code": d["hs_code"],
        "handling_info": d["handling_info"],
        "issue_date": d["issue_date"].strftime("%Y-%m-%d"),
        "signatory": d["signatory"],
    }
    # fmt1 (IATA-Neutral): renders iata_code, agent_cass, airline_code, rate_class,
    #                       commodity_no, shipper_acct, weight_charge, other_charges,
    #                       fuel_surcharge
    if fmt_idx == 0:
        fields["iata_code"] = d["iata_code"]
        fields["agent_cass"] = d["agent_cass"]
        fields["airline_code"] = d["airline_code"]
        fields["rate_class"] = d["rate_class"]
        fields["commodity_no"] = d["commodity_no"]
        fields["shipper_account"] = d["shipper_acct"]
        fields["weight_charge"] = d["weight_charge"]
        fields["other_charges"] = d["other_charges"]
        fields["fuel_surcharge"] = d["fuel_surcharge"]
    # fmt2 (Express-DHL-Courier): renders service_type, shipper_acct, dims
    if fmt_idx == 1:
        fields["service_type"] = d["service_type"]
        fields["shipper_account"] = d["shipper_acct"]
        fields["dims_l"] = d["dims_l"]
        fields["dims_w"] = d["dims_w"]
        fields["dims_h"] = d["dims_h"]
    # fmt3 (Consolidated): renders iata_code, agent_cass, consolidation_ref, sub_shipments
    if fmt_idx == 2:
        fields["iata_code"] = d["iata_code"]
        fields["agent_cass"] = d["agent_cass"]
        fields["consolidation_ref"] = d["consolidation_ref"]
        fields["sub_shipments"] = d["sub_shipments"]

    ann = {
        "document_id":    fname.replace(".pdf", ""),
        "document_class": "House Airway Bill",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    7,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf", ".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} House Airway Bill documents (3 format variants)...")
    for i in range(1, count + 1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            print(f"  [{i:04d}] {a['format_variant'][:30]:<30}  HAWB: {f['hawb_number']}  "
                  f"Wt: {f['gross_weight_kg']} KG  {f['currency']} {f['total_charge']:>10,.2f}")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate synthetic HAWB documents")
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
