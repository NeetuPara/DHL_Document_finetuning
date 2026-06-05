"""
Shipper's Letter of Instruction — 3 distinct real-world format variants.
Format 1: DHL US SLI (full form) — USPPI, line items, export control, ECCN
Format 2: Simple Export Instructions — 2-column layout, less formal
Format 3: Ocean Freight SLI — vessel/booking/container details emphasis
Generates 1000 diverse documents distributed across all 3 formats.
"""
import json, random, argparse
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_bl_number, random_container_number, random_seal_number,
    random_hawb_number, random_mawb_number, VESSEL_NAMES, PORTS_SEA,
    AIRPORTS, PACKAGE_TYPES, INCOTERMS, CURRENCIES, COMMODITY_CATEGORIES,
    UN_NUMBERS, random_vat_number, random_invoice_number)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "04_Shippers_Letter_of_Instruction"
PDF_DIR, ANN_DIR = OUT_DIR / "pdfs", OUT_DIR / "annotations"

W = 186*mm

def S(n, **k):
    d = dict(fontName="Helvetica", fontSize=8, leading=10,
             textColor=colors.black, spaceAfter=0, spaceBefore=0)
    d.update(k); return ParagraphStyle(n, **d)

def P(t, s): return Paragraph(str(t), s)

def tbl(data, colWidths, style_cmds, repeat=0):
    t = Table(data, colWidths=colWidths, repeatRows=repeat)
    t.setStyle(TableStyle(style_cmds)); return t

BORDER = colors.HexColor("#555555")
LN     = colors.HexColor("#CCCCCC")

ECCN_CODES   = ["EAR99","5E992","3A992","7A994","9A515","2B350","1C351","4A994","5A002","6A002"]
LICENSE_TYPES = ["NLR","License Exception LVS","License Exception GBS","License Exception ENC",
                  "License Exception TSR","Individual Validated License","Distributor License"]
DOM_FOR_OPTIONS = ["D","F","D/F"]
SCHEDULE_B_CODES = [
    "8534.00.0020","8483.40.5010","2936.90.0010","5407.42.0010","8708.30.5060",
    "8518.30.2000","2901.10.0010","3926.90.9995","9018.31.0000","2008.19.9000",
    "9002.11.0010","4016.93.5000","7208.37.0060","9401.30.8040","4819.10.0040",
]
SERVICES = ["Air Freight","Ocean Freight","Ground","Express Courier","LCL Ocean"]
PAYMENT_TERMS = ["Prepaid","Collect","Third Party"]


def make_data():
    uc = random_country()  # USPPI country (typically US or origin)
    cc = random_country()  # consignee country
    while cc[1] == uc[1]: cc = random_country()
    nc = random_country()

    un = random_company(); ua = fake.address().replace("\n", ", ") + f", {uc[0]}"
    ein = f"{random.randint(10,99)}-{random.randint(1000000,9999999)}"
    cn = random_company(); ca = fake.address().replace("\n", ", ") + f", {cc[0]}"
    nn = random_company()
    forwarder = random.choice(["DHL Global Forwarding","Kuehne+Nagel","DB Schenker",
                                "Expeditors","Panalpina","Ceva Logistics"])

    reference   = f"SLI-{fake.date_this_decade().strftime('%Y%m')}-{random.randint(1000,9999)}"
    service     = random.choice(SERVICES)
    incoterm    = random.choice(INCOTERMS)
    named_port  = random.choice(PORTS_SEA) if "Ocean" in service else random.choice(AIRPORTS)[0]
    dangerous_goods = random.choice([True, False, False, False])
    insurance_value = round(random.uniform(1000, 50000), 2)
    license_type    = random.choice(LICENSE_TYPES)
    license_no      = f"LIC-{random.randint(100000,999999)}" if "License" in license_type else "N/A"
    eccn            = random.choice(ECCN_CODES)
    destination_country = cc[0]
    payment_terms   = random.choice(PAYMENT_TERMS)

    n_items = random.randint(2, 8)
    cats    = random.sample(COMMODITY_CATEGORIES, min(n_items, len(COMMODITY_CATEGORIES)))
    items   = []
    for cat in cats:
        qty   = random.randint(5, 200)
        wt    = round(qty * random.uniform(*cat["unit_weight_kg"]), 2)
        val   = round(qty * random.uniform(*cat["unit_value_range"]), 2)
        items.append({
            "marks":       f"{random.choice(['SLI','EXP','ABC'])}/{random.randint(1,50)}",
            "description": cat["description"],
            "schedule_b":  random.choice(SCHEDULE_B_CODES),
            "dom_for":     random.choice(DOM_FOR_OPTIONS),
            "qty":         qty,
            "unit":        cat["unit"],
            "weight_kg":   wt,
            "value_usd":   val,
        })

    signatory = fake.name()
    title     = random.choice(["Export Manager","Logistics Director","Trade Compliance Officer",
                                "Operations Manager","Shipping Coordinator"])

    return dict(
        reference=reference, service=service, incoterm=incoterm, named_port=named_port,
        dangerous_goods=dangerous_goods, insurance_value=insurance_value,
        license_type=license_type, license_no=license_no, eccn=eccn,
        destination_country=destination_country, payment_terms=payment_terms,
        usppi_name=un, usppi_address=ua, usppi_country=uc, ein=ein,
        consignee_name=cn, consignee_address=ca, consignee_country=cc,
        notify_party=nn, nc=nc, forwarder=forwarder,
        schedule_b_items=items,
        signatory=signatory, title=title,
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — DHL US SLI Full Form
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    DHL_RED  = colors.HexColor("#D40511")
    DGRAY    = colors.HexColor("#F5F5F5")
    DARK     = colors.HexColor("#222222")

    st = {
        "title": S("t",  fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, textColor=colors.white),
        "sub":   S("su", fontSize=8,  alignment=TA_CENTER, textColor=DHL_RED, fontName="Helvetica-Bold"),
        "lbl":   S("l",  fontSize=7,  textColor=colors.HexColor("#555555")),
        "val":   S("v",  fontName="Helvetica-Bold", fontSize=8),
        "sm":    S("sm", fontSize=7,  leading=9),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=7,  leading=9),
        "cdr":   S("cdr",fontSize=7,  leading=9,  alignment=TA_RIGHT),
        "cdc":   S("cdc",fontSize=7,  leading=9,  alignment=TA_CENTER),
        "bold":  S("b",  fontName="Helvetica-Bold", fontSize=8.5),
        "note":  S("nt", fontSize=6.5,textColor=colors.HexColor("#666666"), leading=8.5),
        "warn":  S("w",  fontName="Helvetica-Bold", fontSize=7.5, textColor=DHL_RED),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    story.append(tbl([[Ps("SHIPPER'S LETTER OF INSTRUCTION (SLI)","title")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),DHL_RED),
         ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
         ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(tbl([[Ps("U.S. PRINCIPAL PARTY IN INTEREST — EXPORT CONTROL DOCUMENT","sub")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),DGRAY),
         ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    story.append(Spacer(1,1*mm))

    # USPPI + Consignee + Notify
    parties_t = tbl([[
        [Ps("USPPI (Exporter)","lbl"), Ps(d["usppi_name"],"bold"),
         Ps(d["usppi_address"],"sm"), Ps(f"EIN: {d['ein']}","sm"),
         Ps(f"Country: {d['usppi_country'][0]}","sm")],
        [Ps("CONSIGNEE","lbl"), Ps(d["consignee_name"],"bold"),
         Ps(d["consignee_address"],"sm"), Ps(f"Country: {d['consignee_country'][0]}","sm")],
        [Ps("NOTIFY PARTY","lbl"), Ps(d["notify_party"],"bold"),
         Spacer(1,2*mm),
         Ps("FORWARDER","lbl"), Ps(d["forwarder"],"val"),
         Ps(f"Ref: {d['reference']}","sm")],
    ]], [62*mm,62*mm,62*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(parties_t); story.append(Spacer(1,1*mm))

    # Service + flags row
    svc_chk = [(s, "X" if s==d["service"] else "  ") for s in SERVICES[:4]]
    svc_cells = []
    for svc_name, chk in svc_chk:
        svc_cells.append(Ps(f"[{chk}] {svc_name}","sm"))
    service_t = tbl([
        [Ps("SERVICE TYPE","lbl"), Ps("DANGEROUS GOODS","lbl"),
         Ps("INCOTERMS","lbl"), Ps("NAMED PORT","lbl"), Ps("PAYMENT","lbl")],
        [[c for c in svc_cells],
         Ps("YES" if d["dangerous_goods"] else "NO","warn" if d["dangerous_goods"] else "val"),
         Ps(d["incoterm"],"bold"),
         Ps(d["named_port"],"val"),
         Ps(d["payment_terms"],"val")],
        [Ps("INSURANCE VALUE (USD)","lbl"), Ps(f"USD {d['insurance_value']:,.2f}","val"),
         Ps("DESTINATION COUNTRY","lbl"), Ps(d["destination_country"],"val"), Ps("","sm")],
    ], [48*mm,28*mm,24*mm,52*mm,34*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,0),DGRAY),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(service_t); story.append(Spacer(1,1*mm))

    # Line items table
    n = len(d["schedule_b_items"])
    it_rows = [[Ps("Marks","ch"), Ps("Description of Goods","ch"),
                Ps("D/F","ch"), Ps("Schedule B","ch"),
                Ps("Qty","ch"), Ps("Unit","ch"),
                Ps("Net Wt KG","ch"), Ps("Value USD","ch")]]
    for it in d["schedule_b_items"]:
        it_rows.append([
            Ps(it["marks"],"cdc"), Ps(it["description"],"cd"),
            Ps(it["dom_for"],"cdc"), Ps(it["schedule_b"],"cdc"),
            Ps(str(it["qty"]),"cdr"), Ps(it["unit"],"cdc"),
            Ps(f"{it['weight_kg']:.2f}","cdr"),
            Ps(f"{it['value_usd']:,.2f}","cdr")])
    # Totals
    total_wt  = sum(i["weight_kg"] for i in d["schedule_b_items"])
    total_val = sum(i["value_usd"] for i in d["schedule_b_items"])
    it_rows.append([Ps("TOTAL","ch"), Ps("","cd"), Ps("","cdc"),
                    Ps("","cdc"), Ps("","cdr"), Ps("","cdc"),
                    Ps(f"{total_wt:.2f}","cdr"), Ps(f"{total_val:,.2f}","cdr")])
    stripe_it = [("BACKGROUND",(0,r),(-1,r),DGRAY) for r in range(1,n+1) if r%2==0]
    it_t = Table(it_rows, colWidths=[20*mm,56*mm,10*mm,28*mm,14*mm,12*mm,22*mm,24*mm], repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),DGRAY),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe_it))
    story.append(it_t); story.append(Spacer(1,1*mm))

    # Export Control block
    ec_t = tbl([
        [Ps("EXPORT CONTROL / LICENSE INFORMATION","lbl"),
         Ps("ECCN","lbl"), Ps("LICENSE TYPE","lbl"), Ps("LICENSE NUMBER","lbl")],
        [Ps("All export requirements have been verified","sm"),
         Ps(d["eccn"],"bold"), Ps(d["license_type"],"val"), Ps(d["license_no"],"val")],
    ], [62*mm,20*mm,56*mm,48*mm],
    [("SPAN",(0,0),(0,0)),("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,0),DGRAY),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),4)])
    story.append(ec_t); story.append(Spacer(1,1*mm))

    # Signature
    sig_t = tbl([[
        [Ps("AUTHORIZATION & SIGNATURE","lbl"),
         Ps("By signing this form, the USPPI authorizes the freight forwarder to prepare and "
            "execute all export documents and act as agent in accordance with U.S. export "
            "regulations (EAR/ITAR as applicable).","note"),
         Spacer(1,3*mm),
         Ps(f"Signature: _________________________","sm"),
         Ps(f"Name: {d['signatory']}","sm"),
         Ps(f"Title: {d['title']}","sm")],
        [Ps(f"Company: {d['usppi_name']}","sm"),
         Ps(f"Date: {fake.date_between(start_date='-30d', end_date='today').strftime('%d %b %Y')}","sm"),
         Spacer(1,2*mm),
         Ps("FORWARDER USE ONLY","lbl"),
         Ps(f"Forwarder: {d['forwarder']}","sm"),
         Ps(f"Ref: {d['reference']}","sm")],
    ]], [93*mm, 93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — Simple Export Instructions (2-column, less formal)
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    TEAL     = colors.HexColor("#006666")
    TEAL_LT  = colors.HexColor("#E0F0F0")
    WARM     = colors.HexColor("#F9F9F0")

    st = {
        "title": S("t",  fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER, textColor=colors.white),
        "co":    S("co", fontName="Helvetica-Bold", fontSize=11, textColor=TEAL),
        "lbl":   S("l",  fontSize=7,  textColor=TEAL, fontName="Helvetica-Bold"),
        "val":   S("v",  fontSize=8.5),
        "sm":    S("sm", fontSize=7.5,leading=10),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=7,  alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=7.5,leading=9.5),
        "cdr":   S("cdr",fontSize=7.5,leading=9.5,alignment=TA_RIGHT),
        "cdc":   S("cdc",fontSize=7.5,leading=9.5,alignment=TA_CENTER),
        "bold":  S("b",  fontName="Helvetica-Bold", fontSize=9),
        "note":  S("nt", fontSize=7,  textColor=colors.HexColor("#444444"), leading=9),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    W2 = 180*mm
    story = []

    # Header
    hdr = tbl([[Ps(d["usppi_name"],"co"), Ps("EXPORT INSTRUCTIONS","title")],
               [Ps(f"{d['usppi_address']}  |  EIN: {d['ein']}","sm"),
                Ps(f"Ref: {d['reference']}","sm")]],
              [100*mm,80*mm],
    [("BACKGROUND",(1,0),(1,0),TEAL),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),4)])
    story.append(hdr)
    story.append(HRFlowable(width=W2, thickness=2, color=TEAL))
    story.append(Spacer(1,3*mm))

    # 2-column: Shipper | Consignee
    sc_t = tbl([[
        [Ps("SHIPPER / EXPORTER","lbl"), Ps(d["usppi_name"],"bold"),
         Ps(d["usppi_address"],"sm"), Ps(f"Country: {d['usppi_country'][0]}","sm")],
        [Ps("CONSIGNEE","lbl"), Ps(d["consignee_name"],"bold"),
         Ps(d["consignee_address"],"sm"), Ps(f"Country: {d['consignee_country'][0]}","sm")],
    ]], [90*mm,90*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,-1),WARM),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),6),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(sc_t); story.append(Spacer(1,2*mm))

    # Routing and service block
    route_t = tbl([
        [Ps("Service","lbl"), Ps(d["service"],"val"),
         Ps("Forwarder","lbl"), Ps(d["forwarder"],"val")],
        [Ps("Incoterms","lbl"), Ps(f"{d['incoterm']} {d['named_port']}","val"),
         Ps("Payment","lbl"), Ps(d["payment_terms"],"val")],
        [Ps("Destination","lbl"), Ps(d["destination_country"],"val"),
         Ps("Insurance","lbl"), Ps(f"USD {d['insurance_value']:,.2f}","val")],
        [Ps("ECCN","lbl"), Ps(d["eccn"],"val"),
         Ps("License","lbl"), Ps(f"{d['license_type']}", "val")],
    ], [25*mm,65*mm,25*mm,65*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(0,-1),TEAL_LT),("BACKGROUND",(2,0),(2,-1),TEAL_LT),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),4)])
    story.append(route_t); story.append(Spacer(1,2*mm))

    # Commodity table
    story.append(Ps("COMMODITY DETAILS","lbl"))
    story.append(Spacer(1,1*mm))
    n = len(d["schedule_b_items"])
    com_rows = [[Ps("Description","ch"), Ps("Schedule B","ch"),
                 Ps("D/F","ch"), Ps("Qty","ch"), Ps("Unit","ch"),
                 Ps("Net Wt (KG)","ch"), Ps("Value (USD)","ch")]]
    for it in d["schedule_b_items"]:
        com_rows.append([
            Ps(it["description"],"cd"), Ps(it["schedule_b"],"cdc"),
            Ps(it["dom_for"],"cdc"), Ps(str(it["qty"]),"cdr"),
            Ps(it["unit"],"cdc"), Ps(f"{it['weight_kg']:.2f}","cdr"),
            Ps(f"{it['value_usd']:,.2f}","cdr")])
    total_wt  = sum(i["weight_kg"] for i in d["schedule_b_items"])
    total_val = sum(i["value_usd"] for i in d["schedule_b_items"])
    com_rows.append([Ps("TOTALS","ch"), Ps("","cdc"), Ps("","cdc"),
                     Ps("","cdr"), Ps("","cdc"),
                     Ps(f"{total_wt:.2f}","cdr"), Ps(f"{total_val:,.2f}","cdr")])
    stripe_c = [("BACKGROUND",(0,r),(-1,r),TEAL_LT) for r in range(1,n+1) if r%2==0]
    com_t = Table(com_rows, colWidths=[62*mm,28*mm,10*mm,14*mm,12*mm,24*mm,30*mm], repeatRows=1)
    com_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),TEAL),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),TEAL_LT),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe_c))
    story.append(com_t); story.append(Spacer(1,2*mm))

    # Special handling + routing instructions
    special = random.choice(["Keep upright","Fragile","Keep cool","No stacking",
                              "This side up","Handle with care","Refrigerate in transit"])
    instr_t = tbl([[
        [Ps("ROUTING INSTRUCTIONS","lbl"),
         Ps(f"Forward via: {d['forwarder']}","sm"),
         Ps(f"Notify: {d['notify_party']}","sm"),
         Ps(f"Destination port: {d['named_port']}","sm")],
        [Ps("SPECIAL HANDLING","lbl"),
         Ps(special,"bold"),
         Spacer(1,2*mm),
         Ps(f"DG: {'YES' if d['dangerous_goods'] else 'NO'}","sm")],
    ]], [110*mm,70*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,-1),WARM),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(instr_t); story.append(Spacer(1,2*mm))

    # Signature
    story.append(HRFlowable(width=W2, thickness=.5, color=TEAL))
    story.append(Spacer(1,1*mm))
    sig_t = tbl([[
        Ps(f"Authorized by: {d['signatory']}  |  Title: {d['title']}  |  Date: "
           f"{fake.date_between(start_date='-30d', end_date='today').strftime('%d %b %Y')}","sm"),
        Ps("Signature: _________________________","sm")
    ]], [120*mm,60*mm],
    [("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),2)])
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — Ocean Freight SLI
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    OCN_BLUE  = colors.HexColor("#0D3B6E")
    OCN_LIGHT = colors.HexColor("#E3EAF5")
    OCN_MID   = colors.HexColor("#9BB5D5")

    st = {
        "title": S("t",  fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, textColor=colors.white),
        "sub":   S("su", fontName="Helvetica-Bold", fontSize=8,  alignment=TA_CENTER, textColor=OCN_BLUE),
        "lbl":   S("l",  fontSize=7,  textColor=colors.HexColor("#1A3A6B"), fontName="Helvetica-Bold"),
        "val":   S("v",  fontSize=8.5),
        "sm":    S("sm", fontSize=7,  leading=9),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=7,  alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=7,  leading=9),
        "cdr":   S("cdr",fontSize=7,  leading=9,  alignment=TA_RIGHT),
        "cdc":   S("cdc",fontSize=7,  leading=9,  alignment=TA_CENTER),
        "bold":  S("b",  fontName="Helvetica-Bold", fontSize=8.5, textColor=OCN_BLUE),
        "note":  S("nt", fontSize=6.5,leading=8.5,textColor=colors.HexColor("#444466")),
    }
    def Ps(t, s): return P(t, st[s])

    # Ocean-specific data — read from d if pre-populated by generate_one, else generate
    vessel       = d.get("_vessel")       or random.choice(VESSEL_NAMES)
    voyage       = d.get("_voyage")       or f"{random.randint(100,999)}{''.join(random.choices('NESW',k=1))}"
    booking_ref  = d.get("_booking_ref")  or f"BKG-{random.randint(100000,999999)}"
    bl_number    = d.get("_bl_number")    or random_bl_number()
    pol          = d.get("_pol")          or random.choice(PORTS_SEA)
    pod          = d.get("_pod")          or random.choice(PORTS_SEA)
    if not d.get("_pod"):
        while pod == pol: pod = random.choice(PORTS_SEA)
    container_no = d.get("_container_no") or random_container_number()
    seal_no      = d.get("_seal_no")      or random_seal_number()
    ctr_type     = d.get("_ctr_type")     or random.choice(["20'GP","40'GP","40'HC","45'HC"])

    n_pkgs = sum(i["qty"] for i in d["schedule_b_items"])
    pkg_type = random.choice(PACKAGE_TYPES)
    total_wt = round(sum(i["weight_kg"] for i in d["schedule_b_items"]), 2)
    gross_wt = round(total_wt * random.uniform(1.05, 1.15), 2)
    cbm = d.get("_cbm") or round(n_pkgs * random.uniform(0.02, 0.08), 3)

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    story.append(tbl([
        [Ps("SHIPPER'S LETTER OF INSTRUCTION — OCEAN FREIGHT","title")],
    ], [W],
    [("BACKGROUND",(0,0),(-1,-1),OCN_BLUE),
     ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(tbl([[Ps("NON-NEGOTIABLE  ·  FOR FORWARDER USE ONLY","sub")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),OCN_LIGHT),
         ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    story.append(Spacer(1,1*mm))

    # Parties
    parties_t = tbl([[
        [Ps("SHIPPER (USPPI)","lbl"), Ps(d["usppi_name"],"bold"),
         Ps(d["usppi_address"],"sm"), Ps(f"EIN: {d['ein']}","sm")],
        [Ps("CONSIGNEE","lbl"), Ps(d["consignee_name"],"bold"),
         Ps(d["consignee_address"],"sm")],
        [Ps("NOTIFY PARTY","lbl"), Ps(d["notify_party"],"bold"),
         Spacer(1,1*mm),
         Ps("FORWARDER","lbl"), Ps(d["forwarder"],"val")],
    ]], [62*mm,62*mm,62*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(parties_t); story.append(Spacer(1,1*mm))

    # Ocean routing block
    ocean_data = [
        [Ps("VESSEL","lbl"), Ps(vessel,"val"),
         Ps("VOYAGE","lbl"), Ps(voyage,"val"),
         Ps("BOOKING REF","lbl"), Ps(booking_ref,"bold")],
        [Ps("PORT OF LOADING","lbl"), Ps(pol,"val"),
         Ps("PORT OF DISCHARGE","lbl"), Ps(pod,"val"),
         Ps("B/L NUMBER","lbl"), Ps(bl_number,"val")],
        [Ps("INCOTERMS","lbl"), Ps(f"{d['incoterm']} {pol}","val"),
         Ps("FREIGHT TERMS","lbl"), Ps(d["payment_terms"],"val"),
         Ps("SLI REFERENCE","lbl"), Ps(d["reference"],"val")],
    ]
    ocean_t = Table(ocean_data, colWidths=[28*mm,34*mm,28*mm,34*mm,28*mm,34*mm])
    ocean_t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("BACKGROUND",(0,0),(0,-1),OCN_LIGHT),("BACKGROUND",(2,0),(2,-1),OCN_LIGHT),
        ("BACKGROUND",(4,0),(4,-1),OCN_LIGHT),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(ocean_t); story.append(Spacer(1,1*mm))

    # Container + packing
    ctr_t = tbl([
        [Ps("CONTAINER","lbl"), Ps("SEAL","lbl"), Ps("TYPE","lbl"),
         Ps("NO. PACKAGES","lbl"), Ps("PKG TYPE","lbl"),
         Ps("GROSS WEIGHT","lbl"), Ps("NET WEIGHT","lbl"), Ps("CBM","lbl")],
        [Ps(container_no,"bold"), Ps(seal_no,"val"), Ps(ctr_type,"val"),
         Ps(str(n_pkgs),"val"), Ps(pkg_type,"val"),
         Ps(f"{gross_wt:,.1f} KG","val"), Ps(f"{total_wt:,.1f} KG","val"),
         Ps(f"{cbm:.3f}","val")],
    ], [34*mm,22*mm,14*mm,22*mm,18*mm,24*mm,24*mm,28*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,0),OCN_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),3)])
    story.append(ctr_t); story.append(Spacer(1,1*mm))

    # Marks & Numbers + goods table
    n = len(d["schedule_b_items"])
    goods_rows = [[Ps("Marks & Numbers","ch"), Ps("Description of Goods","ch"),
                   Ps("Schedule B","ch"), Ps("D/F","ch"),
                   Ps("Qty / Unit","ch"), Ps("Net Wt (KG)","ch"), Ps("Value (USD)","ch")]]
    for it in d["schedule_b_items"]:
        goods_rows.append([
            Ps(it["marks"],"cdc"),
            Ps(it["description"],"cd"),
            Ps(it["schedule_b"],"cdc"),
            Ps(it["dom_for"],"cdc"),
            Ps(f"{it['qty']} {it['unit']}","cdr"),
            Ps(f"{it['weight_kg']:.2f}","cdr"),
            Ps(f"{it['value_usd']:,.2f}","cdr")])
    total_val = sum(i["value_usd"] for i in d["schedule_b_items"])
    goods_rows.append([Ps("TOTAL","ch"), Ps("","cd"), Ps("","cdc"),
                       Ps("","cdc"), Ps("","cdr"),
                       Ps(f"{total_wt:.2f}","cdr"), Ps(f"{total_val:,.2f}","cdr")])
    stripe_g = [("BACKGROUND",(0,r),(-1,r),OCN_LIGHT) for r in range(1,n+1) if r%2==0]
    goods_t = Table(goods_rows, colWidths=[24*mm,56*mm,26*mm,10*mm,22*mm,22*mm,26*mm], repeatRows=1)
    goods_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),OCN_BLUE),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),OCN_LIGHT),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe_g))
    story.append(goods_t); story.append(Spacer(1,1*mm))

    # Packing instructions + export control + signature
    pack_note = random.choice(["Stack max 3 high","Pallet wrap all cartons",
                                "Band to pallets with steel strapping","Mark all sides"])
    bot_t = tbl([[
        [Ps("PACKING INSTRUCTIONS","lbl"),
         Ps(pack_note,"bold"),
         Spacer(1,1*mm),
         Ps(f"DG: {'YES — see DGD' if d['dangerous_goods'] else 'NO'}","sm"),
         Ps(f"ECCN: {d['eccn']}  License: {d['license_type']}","sm")],
        [Ps("SIGNATORY DECLARATION","lbl"),
         Ps("I hereby certify that the above is correct and authorize the forwarder "
            "to act on my behalf for this shipment.","note"),
         Spacer(1,3*mm),
         Ps(f"Signed: _________________________ {d['signatory']}","sm"),
         Ps(f"Title: {d['title']}","sm")],
    ]], [93*mm,93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(bot_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS   = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["DHL-US-SLI-Full-Form","Simple-Export-Instructions","Ocean-Freight-SLI"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"sli_{doc_id:04d}.pdf"

    # For fmt3, pre-generate ocean-specific fields and inject into d so that
    # fmt3 uses the exact same values that end up in the annotation.
    ocean_fields = {}
    if fmt_idx == 2:
        vessel      = random.choice(VESSEL_NAMES)
        voyage      = f"{random.randint(100,999)}{''.join(random.choices('NESW',k=1))}"
        booking_ref = f"BKG-{random.randint(100000,999999)}"
        bl_number   = random_bl_number()
        pol         = random.choice(PORTS_SEA)
        pod         = random.choice(PORTS_SEA)
        while pod == pol: pod = random.choice(PORTS_SEA)
        container_no = random_container_number()
        seal_no      = random_seal_number()
        ctr_type     = random.choice(["20'GP","40'GP","40'HC","45'HC"])
        n_pkgs       = sum(i["qty"] for i in d["schedule_b_items"])
        cbm          = round(n_pkgs * random.uniform(0.02, 0.08), 3)
        # Inject with underscore-prefixed keys so fmt3 picks them up
        d["_vessel"] = vessel; d["_voyage"] = voyage
        d["_booking_ref"] = booking_ref; d["_bl_number"] = bl_number
        d["_pol"] = pol; d["_pod"] = pod
        d["_container_no"] = container_no; d["_seal_no"] = seal_no
        d["_ctr_type"] = ctr_type; d["_cbm"] = cbm
        ocean_fields = dict(
            vessel=vessel, voyage=voyage, booking_ref=booking_ref,
            bl_number=bl_number, port_of_loading=pol, port_of_discharge=pod,
            container_number=container_no, seal_number=seal_no,
            container_type=ctr_type, cbm=cbm,
        )

    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Fields common to all three formats
    fields = {
        "reference": d["reference"],
        "usppi_name": d["usppi_name"], "usppi_address": d["usppi_address"],
        "usppi_country": d["usppi_country"][0], "ein": d["ein"],
        "consignee_name": d["consignee_name"], "consignee_address": d["consignee_address"],
        "consignee_country": d["consignee_country"][0],
        "notify_party": d["notify_party"],
        "forwarder": d["forwarder"],
        "incoterm": d["incoterm"],
        "dangerous_goods": d["dangerous_goods"],
        "payment_terms": d["payment_terms"],
        "eccn": d["eccn"],
        "signatory_name": d["signatory"], "signatory_title": d["title"],
        "line_items": d["schedule_b_items"],
        "total_weight_kg": round(sum(i["weight_kg"] for i in d["schedule_b_items"]), 2),
        "total_value_usd": round(sum(i["value_usd"] for i in d["schedule_b_items"]), 2),
    }

    if fmt_idx == 0:
        # fmt1 (DHL-US-SLI-Full-Form): renders service, named_port, insurance_value,
        # license_type, license_number, eccn, destination_country
        fields["service"] = d["service"]
        fields["named_port"] = d["named_port"]
        fields["insurance_value_usd"] = d["insurance_value"]
        fields["license_type"] = d["license_type"]
        fields["license_number"] = d["license_no"]
        fields["destination_country"] = d["destination_country"]

    elif fmt_idx == 1:
        # fmt2 (Simple-Export-Instructions): renders service, named_port, insurance_value,
        # license_type, eccn, destination_country — same set as fmt1
        fields["service"] = d["service"]
        fields["named_port"] = d["named_port"]
        fields["insurance_value_usd"] = d["insurance_value"]
        fields["license_type"] = d["license_type"]
        fields["license_number"] = d["license_no"]
        fields["destination_country"] = d["destination_country"]

    elif fmt_idx == 2:
        # fmt3 (Ocean-Freight-SLI): renders ocean-specific fields only; no
        # service, insurance_value, license_type, license_number, destination_country
        fields.update(ocean_fields)

    ann = {
        "document_id":    fname.replace(".pdf",""),
        "document_class": "Shippers Letter of Instruction",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    4,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf",".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} Shippers Letter of Instruction documents (3 format variants)...")
    for i in range(1, count+1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            print(f"  [{i:04d}] {a['format_variant'][:30]:<30} {f['reference']}  "
                  f"Val: USD {f['total_value_usd']:>10,.2f}  {len(f['line_items'])} items")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
