"""
Certificate of Origin — 3 distinct real-world format variants.
Format 1: General Chamber of Commerce COO
Format 2: FTA/USMCA Numbered Fields Certificate
Format 3: EUR.1 Movement Certificate (EU-style)
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

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "03_Certificate_of_Origin"
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

FTA_AGREEMENTS = [
    "USMCA", "NAFTA", "EU-Japan EPA", "CPTPP", "RCEP",
    "US-Korea FTA (KORUS)", "ASEAN FTA", "Australia-US FTA",
    "EU-Canada CETA", "UK-Australia FTA",
]
PREFERENCE_CRITERIA = ["A", "B", "C", "D", "E", "F"]
COUNTRIES = [
    ("United States", "US"), ("Germany", "DE"), ("China", "CN"),
    ("United Kingdom", "GB"), ("Japan", "JP"), ("France", "FR"),
    ("Netherlands", "NL"), ("Singapore", "SG"), ("India", "IN"),
    ("Brazil", "BR"), ("Australia", "AU"), ("Canada", "CA"),
    ("South Korea", "KR"), ("Italy", "IT"), ("Mexico", "MX"),
]


def make_data():
    ec = random_country(); dc = random_country()
    while dc[1] == ec[1]: dc = random_country()
    pc_entry = random_country()

    en = random_company(); ea = fake.address().replace("\n", ", ") + f", {ec[0]}"
    cn = random_company(); ca = fake.address().replace("\n", ", ") + f", {dc[0]}"
    pn = random_company()

    doc_no       = f"COO-{fake.date_this_decade().strftime('%Y%m')}-{random.randint(1000,9999)}"
    bl_awb       = random.choice([random_bl_number(), random_hawb_number()])
    fta_agreement= random.choice(FTA_AGREEMENTS)
    issue_date   = fake.date_between(start_date="-2y", end_date="today")
    from datetime import timedelta
    blanket_start= fake.date_between(start_date=issue_date - timedelta(days=180), end_date=issue_date)
    blanket_end  = fake.date_between(start_date=issue_date, end_date=issue_date + timedelta(days=365))

    n_goods = random.randint(1, 6)
    goods = []
    chosen_cats = random.sample(COMMODITY_CATEGORIES, min(n_goods, len(COMMODITY_CATEGORIES)))
    for cat in chosen_cats:
        qty   = random.randint(10, 500)
        unit  = cat["unit"]
        wt    = round(qty * random.uniform(*cat["unit_weight_kg"]), 2)
        val   = round(qty * random.uniform(*cat["unit_value_range"]), 2)
        goods.append({
            "description":      cat["description"],
            "hs_code":          cat["hs_code"],
            "qty":              qty,
            "unit":             unit,
            "weight_kg":        wt,
            "origin_criterion": random.choice(PREFERENCE_CRITERIA),
            "value":            val,
        })

    certifier   = fake.name()
    signatory   = fake.name()
    chamber     = random.choice(["Chamber of Commerce", "Board of Trade",
                                  "Trade Association", "Export Council"])
    chamber_no  = f"CH-{random.randint(100000,999999)}"

    return dict(
        exporter_name=en, exporter_address=ea, exporter_country=ec,
        consignee_name=cn, consignee_address=ca, consignee_country=dc,
        producer_name=pn, producer_country=pc_entry,
        country_of_origin=ec[0], country_of_destination=dc[0],
        doc_no=doc_no, bl_awb=bl_awb,
        fta_agreement=fta_agreement,
        blanket_start=blanket_start, blanket_end=blanket_end,
        issue_date=issue_date, goods=goods,
        certifier=certifier, signatory=signatory,
        chamber=chamber, chamber_no=chamber_no,
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — General Chamber of Commerce COO
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    CHBR_BLUE  = colors.HexColor("#1A3A6B")
    CHBR_LIGHT = colors.HexColor("#E5ECF7")
    GOLD       = colors.HexColor("#C8A84B")

    st = {
        "title": S("t",  fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER, textColor=colors.white),
        "sub":   S("su", fontName="Helvetica-Bold", fontSize=9,  alignment=TA_CENTER, textColor=CHBR_BLUE),
        "lbl":   S("l",  fontSize=7,  textColor=colors.HexColor("#334477"), fontName="Helvetica-Bold"),
        "val":   S("v",  fontSize=8),
        "sm":    S("sm", fontSize=7,  leading=9),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=7,  alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=7,  leading=9),
        "cdr":   S("cdr",fontSize=7,  leading=9, alignment=TA_RIGHT),
        "cdc":   S("cdc",fontSize=7,  leading=9, alignment=TA_CENTER),
        "bold":  S("b",  fontName="Helvetica-Bold", fontSize=9, textColor=CHBR_BLUE),
        "note":  S("nt", fontSize=6.5, textColor=colors.HexColor("#555577")),
        "certbold": S("cb", fontName="Helvetica-Bold", fontSize=7.5),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    # Header
    story.append(tbl([
        [Ps("CERTIFICATE OF ORIGIN","title")],
        [Ps(f"Issued by the {d['chamber']}","sub")],
    ], [W],
    [("BACKGROUND",(0,0),(-1,0),CHBR_BLUE),("BACKGROUND",(0,1),(-1,1),CHBR_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(Spacer(1,1*mm))

    # Exporter + Consignee + Doc details
    top_t = tbl([[
        [Ps("SHIPPER / EXPORTER","lbl"), Ps(d["exporter_name"],"bold"),
         Ps(d["exporter_address"],"sm"),
         Ps(f"Country of Origin: {d['country_of_origin']}","sm")],
        [Ps("CONSIGNEE","lbl"), Ps(d["consignee_name"],"bold"),
         Ps(d["consignee_address"],"sm"),
         Ps(f"Country of Destination: {d['country_of_destination']}","sm")],
        [Ps("CERTIFICATE DETAILS","lbl"),
         Ps(f"Certificate No: {d['doc_no']}","val"),
         Spacer(1,1*mm),
         Ps(f"B/L or AWB: {d['bl_awb']}","sm"),
         Spacer(1,1*mm),
         Ps(f"Date of Issue: {d['issue_date'].strftime('%d %b %Y')}","sm"),
         Spacer(1,1*mm),
         Ps(f"Chamber Ref: {d['chamber_no']}","sm")],
    ]], [68*mm, 68*mm, 50*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),6),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(top_t); story.append(Spacer(1,1*mm))

    # Goods table: Marks&Nos | No.Pkgs | Description | Gross Wt | CBM
    n = len(d["goods"])
    g_rows = [[Ps("Marks & Nos.","ch"), Ps("No. of Pkgs","ch"),
               Ps("Description of Goods","ch"), Ps("HS Code","ch"),
               Ps("Gross Weight (KG)","ch"), Ps("CBM / Volume","ch")]]
    for i, g in enumerate(d["goods"]):
        mark = f"{random.choice(['ABC','XYZ','COO'])}/{i+1}"
        cbm  = round(g["qty"] * random.uniform(0.02, 0.08), 3)
        g_rows.append([
            Ps(mark,"cdc"),
            Ps(f"{g['qty']} {g['unit']}","cdr"),
            Ps(g["description"],"cd"),
            Ps(g["hs_code"],"cdc"),
            Ps(f"{g['weight_kg']:,.2f}","cdr"),
            Ps(f"{cbm:.3f}","cdr")])
    # Total row
    total_wt = sum(g["weight_kg"] for g in d["goods"])
    g_rows.append([Ps("TOTAL","ch"), Ps("","cdr"),
                   Ps("","cd"), Ps("","cdc"),
                   Ps(f"{total_wt:,.2f}","cdr"), Ps("","cdr")])
    stripe_g = [("BACKGROUND",(0,r),(-1,r),CHBR_LIGHT) for r in range(1,n+1) if r%2==0]
    g_t = Table(g_rows, colWidths=[28*mm,22*mm,66*mm,22*mm,26*mm,22*mm], repeatRows=1)
    g_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),CHBR_BLUE),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),CHBR_LIGHT),
        ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe_g))
    story.append(g_t); story.append(Spacer(1,2*mm))

    # Dual certification block: Shipper + Chamber
    cert_t = tbl([[
        [Ps("SHIPPER'S DECLARATION","lbl"),
         Ps("The undersigned hereby declares that the above-mentioned goods "
            f"originated in {d['country_of_origin']} and that the particulars "
            "given are true, correct and complete.","note"),
         Spacer(1,4*mm),
         Ps(f"Signature: _________________________","sm"),
         Ps(f"Name: {d['certifier']}","sm"),
         Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}","sm")],
        [Ps("CHAMBER OF COMMERCE CERTIFICATION","lbl"),
         Ps(f"Certified by: {d['chamber']}","certbold"),
         Spacer(1,1*mm),
         Ps(f"Certificate No: {d['doc_no']}","sm"),
         Ps(f"Date Certified: {d['issue_date'].strftime('%d %b %Y')}","sm"),
         Spacer(1,4*mm),
         Ps("Official Stamp:","sm"),
         Spacer(1,6*mm),
         Ps("Authorized Signature: _________________","sm")],
    ]], [93*mm, 93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(cert_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — FTA / USMCA Numbered Fields Certificate
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    FTA_GREEN  = colors.HexColor("#1B5E20")
    FTA_LIGHT  = colors.HexColor("#E8F5E9")
    FTA_MID    = colors.HexColor("#A5D6A7")

    st = {
        "title":  S("t",  fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, textColor=colors.white),
        "agree":  S("ag", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=FTA_GREEN),
        "fno":    S("fn", fontName="Helvetica-Bold", fontSize=8,  textColor=FTA_GREEN),
        "lbl":    S("l",  fontSize=6.5, textColor=colors.HexColor("#2E5530"), fontName="Helvetica-Bold"),
        "val":    S("v",  fontSize=8),
        "sm":     S("sm", fontSize=7,   leading=9),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=7,  alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=7,   leading=9),
        "cdr":    S("cdr",fontSize=7,   leading=9,  alignment=TA_RIGHT),
        "cdc":    S("cdc",fontSize=7,   leading=9,  alignment=TA_CENTER),
        "bold":   S("b",  fontName="Helvetica-Bold", fontSize=8),
        "cert":   S("ct", fontSize=6.5, textColor=colors.HexColor("#555555"), leading=9),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    story.append(tbl([
        [Ps(f"CERTIFICATE OF ORIGIN","title")],
        [Ps(f"{d['fta_agreement']} — Free Trade Agreement","agree")],
    ], [W],
    [("BACKGROUND",(0,0),(-1,0),FTA_GREEN),("BACKGROUND",(0,1),(-1,1),FTA_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(Spacer(1,1*mm))

    # Numbered fields 1-6 in grid
    field_rows = [
        [Ps("1. EXPORTER","fno"),
         [Ps("Exporter / Producer:","lbl"), Ps(d["exporter_name"],"val"),
          Ps(d["exporter_address"],"sm"), Ps(f"Country: {d['exporter_country'][0]}","sm")],
         Ps("2. BLANKET PERIOD","fno"),
         [Ps("From:","lbl"), Ps(d["blanket_start"].strftime("%d %b %Y"),"val"),
          Spacer(1,1*mm),
          Ps("To:","lbl"),   Ps(d["blanket_end"].strftime("%d %b %Y"),"val")]],
        [Ps("3. PRODUCER","fno"),
         [Ps("Producer Name:","lbl"), Ps(d["producer_name"],"val"),
          Ps(f"Country: {d['producer_country'][0]}","sm")],
         Ps("4. IMPORTER / CONSIGNEE","fno"),
         [Ps(d["consignee_name"],"val"), Ps(d["consignee_address"],"sm"),
          Ps(f"Country: {d['consignee_country'][0]}","sm")]],
        [Ps("5. CERTIFICATE REFERENCE","fno"),
         [Ps(f"Certificate No: {d['doc_no']}","bold"),
          Ps(f"B/L or AWB: {d['bl_awb']}","sm"),
          Ps(f"Date of Issue: {d['issue_date'].strftime('%d %b %Y')}","sm")],
         Ps("6. COUNTRY OF ORIGIN","fno"),
         [Ps(f"Country: {d['country_of_origin']}","bold"),
          Ps(f"Destination: {d['country_of_destination']}","sm"),
          Ps(f"Agreement: {d['fta_agreement']}","sm")]],
    ]
    f_t = Table(field_rows, colWidths=[8*mm,85*mm,8*mm,85*mm])
    f_t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("BACKGROUND",(0,0),(0,-1),FTA_LIGHT),("BACKGROUND",(2,0),(2,-1),FTA_LIGHT),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    story.append(f_t); story.append(Spacer(1,1*mm))

    # Goods table with Preference Criterion
    n = len(d["goods"])
    g_rows = [[Ps("7. Description of Goods","ch"), Ps("8. HS Tariff","ch"),
               Ps("9. Pref. Criterion","ch"), Ps("10. Qty & Unit","ch"),
               Ps("Net Weight (KG)","ch"), Ps("Value","ch")]]
    for g in d["goods"]:
        cur = random.choice(CURRENCIES)
        g_rows.append([
            Ps(g["description"],"cd"),
            Ps(g["hs_code"],"cdc"),
            Ps(g["origin_criterion"],"cdc"),
            Ps(f"{g['qty']} {g['unit']}","cdr"),
            Ps(f"{g['weight_kg']:,.2f}","cdr"),
            Ps(f"{cur} {g['value']:,.2f}","cdr")])
    stripe_g2 = [("BACKGROUND",(0,r),(-1,r),FTA_LIGHT) for r in range(1,n+1) if r%2==0]
    g_t2 = Table(g_rows, colWidths=[60*mm,22*mm,20*mm,22*mm,24*mm,38*mm], repeatRows=1)
    g_t2.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),FTA_GREEN),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe_g2))
    story.append(g_t2); story.append(Spacer(1,1*mm))

    # Preference criteria legend
    legend_text = ("Preference Criteria: A = Wholly obtained/produced  "
                   "B = Tariff change (CTH/CTSH)  "
                   "C = Regional Value Content  "
                   "D = Specific process rule")
    story.append(tbl([[Ps(legend_text,"cert")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),FTA_LIGHT),
         ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
         ("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(Spacer(1,1*mm))

    # Full FTA certification text + signature
    cert_text = (
        f"I certify that the goods described in this Certificate of Origin are originating goods "
        f"under the terms of {d['fta_agreement']} and that the information contained in this document "
        "is true and accurate, and I assume responsibility for proving such representations. "
        f"I understand that I am liable for any false statements or material omissions made on or in "
        "connection with this document."
    )
    cert_t2 = tbl([[
        Ps(cert_text,"cert"),
        [Ps("11. AUTHORIZED SIGNATURE","fno"),
         Spacer(1,4*mm),
         Ps("Signature: _________________________","sm"),
         Ps(f"Name: {d['certifier']}","sm"),
         Ps(f"Title: {random.choice(['Export Manager','Director','Compliance Officer'])}","sm"),
         Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}","sm"),
         Ps(f"Company: {d['exporter_name']}","sm")]
    ]], [100*mm, 86*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(cert_t2)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — EUR.1 Movement Certificate (EU-style)
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    EUR_DARK  = colors.HexColor("#003087")
    EUR_LIGHT = colors.HexColor("#E6EEF9")
    EUR_GOLD  = colors.HexColor("#FFD700")
    STAR_BLUE = colors.HexColor("#002060")

    st = {
        "title":  S("t",  fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER, textColor=colors.white),
        "sub":    S("su", fontName="Helvetica-Bold", fontSize=8,  alignment=TA_CENTER, textColor=EUR_DARK),
        "boxno":  S("bn", fontName="Helvetica-Bold", fontSize=7,  textColor=EUR_DARK),
        "lbl":    S("l",  fontSize=6.5, textColor=EUR_DARK, fontName="Helvetica-Bold"),
        "val":    S("v",  fontSize=8),
        "sm":     S("sm", fontSize=7,   leading=9),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=7,  alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=7,   leading=9),
        "cdr":    S("cdr",fontSize=7,   leading=9, alignment=TA_RIGHT),
        "cdc":    S("cdc",fontSize=7,   leading=9, alignment=TA_CENTER),
        "cert":   S("ct", fontSize=6.5, leading=9, textColor=colors.HexColor("#333355")),
        "check":  S("ck", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER),
        "eu":     S("eu", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.white, alignment=TA_CENTER),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    # EUR.1 title bar
    story.append(tbl([
        [Ps("EUR.1  MOVEMENT CERTIFICATE","title"), Ps("EUROPEAN UNION","eu")],
    ], [140*mm, 46*mm],
    [("BACKGROUND",(0,0),(-1,-1),EUR_DARK),
     ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,colors.HexColor("#6688CC"))]))
    story.append(tbl([[
        Ps("Movement Certificate — Preferential Trade  ·  Not valid as a commercial document","sub"),
    ]], [W],
    [("BACKGROUND",(0,0),(-1,-1),EUR_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    story.append(Spacer(1,1*mm))

    # Boxes 1-6 in a structured grid
    box_grid = [
        [Ps("1. EXPORTER (Name, full address, country)","boxno"),
         Ps("2. MOVEMENT CERTIFICATE No.","boxno"),
         Ps("3. CONSIGNEE (Name, full address, country)","boxno")],
        [[Ps(d["exporter_name"],"val"), Ps(d["exporter_address"],"sm"),
          Ps(d["exporter_country"][0],"sm")],
         [Ps(d["doc_no"],"val"),
          Spacer(1,2*mm),
          Ps(f"B/L or AWB: {d['bl_awb']}","sm"),
          Ps(f"FTA: {d['fta_agreement']}","sm"),
          Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}","sm")],
         [Ps(d["consignee_name"],"val"), Ps(d["consignee_address"],"sm"),
          Ps(d["consignee_country"][0],"sm")]],
    ]
    bx_t = Table(box_grid, colWidths=[68*mm,50*mm,68*mm])
    bx_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),EUR_LIGHT),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    story.append(bx_t)

    # Boxes 4-6
    box2 = tbl([
        [Ps("4. COUNTRY OF ORIGIN","boxno"), Ps("5. COUNTRY OF DESTINATION","boxno"),
         Ps("6. TRANSPORT DETAILS","boxno")],
        [[Ps(d["country_of_origin"],"val")],
         [Ps(d["country_of_destination"],"val")],
         [Ps(f"Mode: {random.choice(['Sea', 'Air', 'Road', 'Rail'])}","sm"),
          Ps(f"Vessel/Flight: {random.choice(VESSEL_NAMES)}","sm")]],
    ], [62*mm,62*mm,62*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,0),EUR_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(box2)

    # Box 7: Goods description
    story.append(tbl([[Ps("7. DESCRIPTION OF GOODS","boxno")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),EUR_LIGHT),
         ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
         ("LEFTPADDING",(0,0),(-1,-1),4),("BOX",(0,0),(-1,-1),.5,BORDER)]))
    n = len(d["goods"])
    g_rows = [[Ps("Item","ch"), Ps("Description of Goods","ch"), Ps("HS Code","ch"),
               Ps("Qty","ch"), Ps("Unit","ch"), Ps("Net Wt (KG)","ch"),
               Ps("Origin Criterion","ch")]]
    for i, g in enumerate(d["goods"], 1):
        g_rows.append([
            Ps(str(i),"cdc"),
            Ps(g["description"],"cd"),
            Ps(g["hs_code"],"cdc"),
            Ps(str(g["qty"]),"cdr"),
            Ps(g["unit"],"cdc"),
            Ps(f"{g['weight_kg']:,.2f}","cdr"),
            Ps(g["origin_criterion"],"cdc")])
    stripe_e = [("BACKGROUND",(0,r),(-1,r),EUR_LIGHT) for r in range(1,n+1) if r%2==0]
    g_t3 = Table(g_rows, colWidths=[10*mm,60*mm,22*mm,14*mm,12*mm,24*mm,44*mm], repeatRows=1)
    g_t3.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),EUR_DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe_e))
    story.append(g_t3); story.append(Spacer(1,1*mm))

    # Boxes 8-9: Cumulation + Derogation checkboxes
    chk_yes  = random.choice(["YES","NO","NO"])
    chk_der  = random.choice(["YES","NO","NO"])
    box89 = tbl([
        [Ps("8. CUMULATION","boxno"), Ps("9. DEROGATION","boxno"),
         Ps("10. REMARKS","boxno")],
        [[Ps(f"Cumulation applied: {chk_yes}","sm"),
          Ps("(tick if applicable)","cert")],
         [Ps(f"Derogation applied: {chk_der}","sm"),
          Ps("(ref: if applicable)","cert")],
         [Ps(f"FTA Agreement: {d['fta_agreement']}","sm"),
          Ps(f"Originals issued: {random.randint(1,3)}","sm")]],
    ], [62*mm,62*mm,62*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,0),EUR_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(box89); story.append(Spacer(1,1*mm))

    # Boxes 11-12: Exporter declaration + Customs endorsement
    decl_cert = tbl([[
        [Ps("11. EXPORTER'S DECLARATION","boxno"),
         Ps("I, the undersigned, declare that the goods described in this certificate "
            f"originate in {d['country_of_origin']} and satisfy the conditions required for the "
            f"obtaining of this certificate under {d['fta_agreement']}.","cert"),
         Spacer(1,3*mm),
         Ps(f"Place and date: {d['issue_place'] if hasattr(d, 'issue_place') else d['exporter_country'][0]}, "
            f"{d['issue_date'].strftime('%d %b %Y')}","sm"),
         Spacer(1,1*mm),
         Ps(f"Signature: _________________________ {d['certifier']}","sm")],
        [Ps("12. CUSTOMS ENDORSEMENT","boxno"),
         Ps("Customs Authority / Issuing Body:","lbl"),
         Ps(f"{d['chamber']}","val"),
         Spacer(1,2*mm),
         Ps("Stamp:","lbl"),
         Spacer(1,6*mm),
         Ps("Official Signature: _________________________","sm"),
         Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}","sm")],
    ]], [93*mm, 93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(decl_cert)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS   = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["Chamber-of-Commerce-COO","FTA-USMCA-Numbered-Fields","EUR1-Movement-Certificate"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"coo_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Base fields present in all formats
    fields = {
        "document_number": d["doc_no"],
        "exporter_name": d["exporter_name"], "exporter_address": d["exporter_address"],
        "exporter_country": d["exporter_country"][0],
        "consignee_name": d["consignee_name"], "consignee_address": d["consignee_address"],
        "consignee_country": d["consignee_country"][0],
        "country_of_origin": d["country_of_origin"],
        "country_of_destination": d["country_of_destination"],
        "bl_or_awb": d["bl_awb"],
        "issue_date": d["issue_date"].strftime("%Y-%m-%d"),
        "certifier_name": d["certifier"],
        "goods": d["goods"],
    }
    # signatory is generated but never rendered in any format's PDF — omitted everywhere

    if fmt_idx == 0:  # fmt1 — Chamber of Commerce COO
        fields["chamber"] = d["chamber"]
        fields["chamber_reference"] = d["chamber_no"]

    if fmt_idx == 1:  # fmt2 — FTA / USMCA Numbered Fields
        fields["fta_agreement"] = d["fta_agreement"]
        fields["blanket_period_from"] = d["blanket_start"].strftime("%Y-%m-%d")
        fields["blanket_period_to"] = d["blanket_end"].strftime("%Y-%m-%d")
        fields["producer_name"] = d["producer_name"]
        fields["producer_country"] = d["producer_country"][0]

    if fmt_idx == 2:  # fmt3 — EUR.1 Movement Certificate
        fields["fta_agreement"] = d["fta_agreement"]
        fields["chamber"] = d["chamber"]

    ann = {
        "document_id":    fname.replace(".pdf",""),
        "document_class": "Certificate of Origin",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    3,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf",".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} Certificate of Origin documents (3 format variants)...")
    for i in range(1, count+1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            print(f"  [{i:04d}] {a['format_variant'][:30]:<30} {f['document_number']}  "
                  f"Origin: {f['country_of_origin']}")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
