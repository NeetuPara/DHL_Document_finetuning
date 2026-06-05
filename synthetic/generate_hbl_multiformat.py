"""
House Bill of Lading — 3 distinct real-world format variants.
Format 1: Standard Ocean HBL (DHL Global Forwarding style)
Format 2: FIATA FBL Multimodal Transport Bill of Lading
Format 3: Short-Form Straight BOL (simplified 1-page)
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

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "02_House_Bill_of_Lading"
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

CONTAINER_TYPES = ["20'GP", "40'GP", "40'HC", "20'RF", "40'RF", "45'HC", "20'OT", "40'OT"]
HS_CODES = [cat["hs_code"] for cat in COMMODITY_CATEGORIES]
DESCRIPTIONS = [cat["description"] for cat in COMMODITY_CATEGORIES]


def make_data():
    sc = random_country(); cc = random_country()
    while cc[1] == sc[1]: cc = random_country()
    nc = random_country()

    sn = random_company(); sa = fake.address().replace("\n", ", ") + f", {sc[0]}"
    cn = random_company(); ca = fake.address().replace("\n", ", ") + f", {cc[0]}"
    nn = random_company(); na = fake.address().replace("\n", ", ") + f", {nc[0]}"

    bl_number   = random_bl_number()
    vessel      = random.choice(VESSEL_NAMES)
    voyage      = f"{random.randint(100,999)}{''.join(random.choices('NESW',k=1))}"
    pol         = random.choice(PORTS_SEA)
    pod         = random.choice(PORTS_SEA)
    while pod == pol: pod = random.choice(PORTS_SEA)
    place_of_receipt  = random.choice([pol, random.choice(PORTS_SEA)])
    place_of_delivery = random.choice([pod, random.choice(PORTS_SEA)])
    issue_date  = fake.date_between(start_date="-2y", end_date="today")
    issue_place = pol.split(",")[0]
    freight_terms = random.choice(["PREPAID", "COLLECT"])
    originals   = random.randint(1, 3)
    incoterm    = random.choice(INCOTERMS)

    n_containers = random.randint(1, 4)
    containers = []
    for _ in range(n_containers):
        containers.append({
            "container_no": random_container_number(),
            "seal_no":      random_seal_number(),
            "size_type":    random.choice(CONTAINER_TYPES),
        })

    cat = random.choice(COMMODITY_CATEGORIES)
    description  = cat["description"]
    hs_code      = cat["hs_code"]
    n_packages   = random.randint(10, 500)
    pkg_type     = random.choice(PACKAGE_TYPES)
    gross_weight = round(random.uniform(500, 24000), 1)
    net_weight   = round(gross_weight * random.uniform(0.88, 0.97), 1)
    cbm          = round(n_packages * random.uniform(0.03, 0.12), 3)
    marks        = f"{random.choice(['ABC','XYZ','GLB'])}/{random.randint(1,50)}"

    return dict(
        bl_number=bl_number, vessel=vessel, voyage=voyage,
        pol=pol, pod=pod, place_of_receipt=place_of_receipt,
        place_of_delivery=place_of_delivery,
        issue_date=issue_date, issue_place=issue_place,
        freight_terms=freight_terms, originals=originals, incoterm=incoterm,
        sn=sn, sa=sa, sc=sc,
        cn=cn, ca=ca, cc=cc,
        nn=nn, na=na, nc=nc,
        containers=containers,
        description=description, hs_code=hs_code,
        n_packages=n_packages, pkg_type=pkg_type,
        gross_weight_kg=gross_weight, net_weight_kg=net_weight,
        cbm=cbm, marks=marks,
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — Standard Ocean HBL (DHL Global Forwarding style)
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    DHL_RED  = colors.HexColor("#D40511")
    DHL_GRAY = colors.HexColor("#F2F2F2")
    DARK     = colors.HexColor("#333333")

    st = {
        "title":  S("t",  fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER, textColor=colors.white),
        "sub":    S("su", fontName="Helvetica-Bold", fontSize=9,  alignment=TA_CENTER, textColor=DHL_RED),
        "lbl":    S("l",  fontSize=7,  textColor=colors.HexColor("#555555")),
        "val":    S("v",  fontName="Helvetica-Bold", fontSize=8),
        "sm":     S("sm", fontSize=7,  leading=9),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=7,  alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=7,  leading=9),
        "cdr":    S("cdr",fontSize=7,  leading=9,  alignment=TA_RIGHT),
        "cdc":    S("cdc",fontSize=7,  leading=9,  alignment=TA_CENTER),
        "bold":   S("b",  fontName="Helvetica-Bold", fontSize=8),
        "fnote":  S("fn", fontSize=6.5,textColor=colors.HexColor("#666666")),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    # Banner
    story.append(tbl([[Ps("HOUSE BILL OF LADING","title")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),DHL_RED),
         ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
         ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(tbl([[Ps("NON-NEGOTIABLE UNLESS CONSIGNED TO ORDER","sub")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),DHL_GRAY),
         ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    story.append(Spacer(1,1*mm))

    # 3-column: Shipper | Consignee | Notify Party
    three_col = tbl([[
        [Ps("SHIPPER / EXPORTER","lbl"), Ps(d["sn"],"val"), Ps(d["sa"],"sm"),
         Spacer(1,1*mm), Ps(f"Country: {d['sc'][0]}","sm")],
        [Ps("CONSIGNEE (if 'ORDER', notify party must be completed)","lbl"),
         Ps(d["cn"],"val"), Ps(d["ca"],"sm"),
         Spacer(1,1*mm), Ps(f"Country: {d['cc'][0]}","sm")],
        [Ps("NOTIFY PARTY / ALSO NOTIFY","lbl"),
         Ps(d["nn"],"val"), Ps(d["na"],"sm"),
         Spacer(1,1*mm), Ps(f"Country: {d['nc'][0]}","sm")],
    ]], [62*mm, 62*mm, 62*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(three_col); story.append(Spacer(1,1*mm))

    # BL number + issue block
    bl_data = [
        [Ps("B/L NUMBER","lbl"), Ps(d["bl_number"],"bold"),
         Ps("ISSUE DATE","lbl"), Ps(d["issue_date"].strftime("%d %b %Y"),"val"),
         Ps("PLACE OF ISSUE","lbl"), Ps(d["issue_place"],"val")],
        [Ps("VESSEL","lbl"), Ps(d["vessel"],"val"),
         Ps("VOYAGE NO.","lbl"), Ps(d["voyage"],"val"),
         Ps("ORIGINALS ISSUED","lbl"), Ps(str(d["originals"]),"val")],
        [Ps("PORT OF LOADING","lbl"), Ps(d["pol"],"val"),
         Ps("PORT OF DISCHARGE","lbl"), Ps(d["pod"],"val"),
         Ps("FREIGHT TERMS","lbl"), Ps(d["freight_terms"],"bold")],
    ]
    bl_t = Table(bl_data, colWidths=[28*mm,34*mm,28*mm,34*mm,28*mm,34*mm])
    bl_t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("BACKGROUND",(0,0),(0,-1),DHL_GRAY),("BACKGROUND",(2,0),(2,-1),DHL_GRAY),
        ("BACKGROUND",(4,0),(4,-1),DHL_GRAY),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(bl_t); story.append(Spacer(1,1*mm))

    # Container table
    n_c = len(d["containers"])
    con_rows = [[Ps("Container No.","ch"), Ps("Seal No.","ch"), Ps("Size / Type","ch")]]
    for c in d["containers"]:
        con_rows.append([Ps(c["container_no"],"cdc"), Ps(c["seal_no"],"cdc"), Ps(c["size_type"],"cdc")])
    stripe_c = [("BACKGROUND",(0,r),(-1,r),DHL_GRAY) for r in range(1,n_c+1) if r%2==0]
    con_t = Table(con_rows, colWidths=[66*mm,60*mm,60*mm], repeatRows=1)
    con_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),
    ] + stripe_c))
    story.append(con_t); story.append(Spacer(1,1*mm))

    # Goods table
    goods_rows = [
        [Ps("Marks & Numbers","ch"), Ps("No. of Packages","ch"),
         Ps("Description of Goods","ch"), Ps("HS Code","ch"),
         Ps("Gross Weight (KG)","ch"), Ps("Net Weight (KG)","ch"), Ps("CBM","ch")],
        [Ps(d["marks"],"cdc"), Ps(f"{d['n_packages']} {d['pkg_type']}","cdc"),
         Ps(d["description"],"cd"), Ps(d["hs_code"],"cdc"),
         Ps(f"{d['gross_weight_kg']:,.1f}","cdr"),
         Ps(f"{d['net_weight_kg']:,.1f}","cdr"),
         Ps(f"{d['cbm']:.3f}","cdr")],
        [Ps("TOTAL","ch"),
         Ps(f"{d['n_packages']}","cdr"), Ps("","cd"), Ps("","cdc"),
         Ps(f"{d['gross_weight_kg']:,.1f}","cdr"),
         Ps(f"{d['net_weight_kg']:,.1f}","cdr"),
         Ps(f"{d['cbm']:.3f}","cdr")],
    ]
    goods_t = Table(goods_rows, colWidths=[28*mm,30*mm,52*mm,22*mm,24*mm,24*mm,6*mm])
    goods_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,2),(-1,2),DHL_GRAY),("FONTNAME",(0,2),(-1,2),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(goods_t); story.append(Spacer(1,2*mm))

    # Freight + signature
    sig_t = tbl([
        [Ps("FREIGHT & CHARGES","lbl"), Ps("INCOTERMS","lbl"), Ps("SIGNED BY","lbl")],
        [Ps(f"{d['freight_terms']}","bold"),
         Ps(d["incoterm"],"bold"),
         Ps(d["sn"],"sm")],
        [Ps("","sm"), Ps("","sm"),
         Ps(f"Signed: _________________________ Date: {d['issue_date'].strftime('%d %b %Y')}","sm")],
        [Ps(f"Place of Receipt: {d['place_of_receipt']}","sm"),
         Ps(f"Place of Delivery: {d['place_of_delivery']}","sm"),
         Ps(f"As agent for the Carrier","fnote")],
    ], [62*mm,62*mm,62*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,0),DHL_GRAY),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(sig_t)
    story.append(Spacer(1,1*mm))
    story.append(P(f"B/L No: {d['bl_number']}  |  This B/L is non-negotiable unless consigned to order  |  Issued at {d['issue_place']}",
                   st["fnote"]))
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — FIATA FBL Multimodal Transport Bill of Lading
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    FIATA_BLUE  = colors.HexColor("#003399")
    FIATA_LIGHT = colors.HexColor("#E8EEFF")
    FIATA_MID   = colors.HexColor("#99AACC")

    st = {
        "title":  S("t",  fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, textColor=colors.white),
        "fiata":  S("fi", fontName="Helvetica-Bold", fontSize=10, textColor=FIATA_BLUE, alignment=TA_CENTER),
        "lbl":    S("l",  fontSize=6.5, textColor=colors.HexColor("#334477"), fontName="Helvetica-Bold"),
        "val":    S("v",  fontSize=8),
        "sm":     S("sm", fontSize=7,   leading=9),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=7, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=7,   leading=9),
        "cdr":    S("cdr",fontSize=7,   leading=9, alignment=TA_RIGHT),
        "cdc":    S("cdc",fontSize=7,   leading=9, alignment=TA_CENTER),
        "bold":   S("b",  fontName="Helvetica-Bold", fontSize=8.5),
        "note":   S("nt", fontSize=6,   textColor=colors.HexColor("#666688"), leading=8),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    # Title block
    story.append(tbl([
        [Ps("FIATA MULTIMODAL TRANSPORT BILL OF LADING","title")],
        [Ps("FBL  ─  Negotiable  ─  Combined Transport Document","fiata")],
    ], [W],
    [("BACKGROUND",(0,0),(-1,0),FIATA_BLUE),("BACKGROUND",(0,1),(-1,1),FIATA_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(Spacer(1,1*mm))

    # Shipper + Consignee in 2-col
    two_col = tbl([[
        [Ps("1. SHIPPER / EXPORTER","lbl"), Ps(d["sn"],"bold"),
         Ps(d["sa"],"sm"), Ps(f"Country: {d['sc'][0]}","sm")],
        [Ps("2. CONSIGNEE","lbl"), Ps(d["cn"],"bold"),
         Ps(d["ca"],"sm"), Ps(f"Country: {d['cc'][0]}","sm")],
    ]], [93*mm, 93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),8),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(two_col)

    # Notify + Pre-carriage
    notify_row = tbl([[
        [Ps("3. NOTIFY PARTY","lbl"), Ps(d["nn"],"bold"), Ps(d["na"],"sm")],
        [Ps("4. PRE-CARRIAGE BY","lbl"), Ps("Road / Rail","val"),
         Ps("5. PLACE OF RECEIPT","lbl"), Ps(d["place_of_receipt"],"val")],
    ]], [93*mm, 93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(notify_row)

    # Vessel + ports block
    vessel_data = [
        [Ps("6. OCEAN VESSEL","lbl"), Ps(d["vessel"],"val"),
         Ps("7. VOYAGE NO.","lbl"), Ps(d["voyage"],"val"),
         Ps("8. B/L NUMBER","lbl"), Ps(d["bl_number"],"bold")],
        [Ps("9. PORT OF LOADING","lbl"), Ps(d["pol"],"val"),
         Ps("10. PORT OF DISCHARGE","lbl"), Ps(d["pod"],"val"),
         Ps("11. PLACE OF DELIVERY","lbl"), Ps(d["place_of_delivery"],"val")],
        [Ps("12. DATE OF ISSUE","lbl"), Ps(d["issue_date"].strftime("%d %b %Y"),"val"),
         Ps("13. PLACE OF ISSUE","lbl"), Ps(d["issue_place"],"val"),
         Ps("14. FREIGHT TERMS","lbl"), Ps(d["freight_terms"],"bold")],
    ]
    v_t = Table(vessel_data, colWidths=[28*mm,37*mm,28*mm,37*mm,28*mm,28*mm])
    v_t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("BACKGROUND",(0,0),(0,-1),FIATA_LIGHT),("BACKGROUND",(2,0),(2,-1),FIATA_LIGHT),
        ("BACKGROUND",(4,0),(4,-1),FIATA_LIGHT),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(v_t); story.append(Spacer(1,1*mm))

    # Container + goods combined table (FIATA style)
    n_c = len(d["containers"])
    c_rows = [[Ps("Container No.","ch"), Ps("Seal No.","ch"), Ps("Type","ch"),
               Ps("No. Pkgs","ch"), Ps("Description of Goods","ch"),
               Ps("HS Code","ch"), Ps("Gross Wt KG","ch"), Ps("CBM","ch")]]
    for i, c in enumerate(d["containers"]):
        if i == 0:
            c_rows.append([
                Ps(c["container_no"],"cdc"), Ps(c["seal_no"],"cdc"), Ps(c["size_type"],"cdc"),
                Ps(str(d["n_packages"]),"cdr"),
                Ps(d["description"],"cd"),
                Ps(d["hs_code"],"cdc"),
                Ps(f"{d['gross_weight_kg']:,.1f}","cdr"),
                Ps(f"{d['cbm']:.3f}","cdr")])
        else:
            c_rows.append([
                Ps(c["container_no"],"cdc"), Ps(c["seal_no"],"cdc"), Ps(c["size_type"],"cdc"),
                Ps("","cdc"), Ps("(continued)","cd"), Ps("","cdc"), Ps("","cdr"), Ps("","cdr")])
    stripe_c2 = [("BACKGROUND",(0,r),(-1,r),FIATA_LIGHT) for r in range(1,n_c+1) if r%2==0]
    cg_t = Table(c_rows, colWidths=[30*mm,22*mm,16*mm,18*mm,46*mm,20*mm,20*mm,14*mm], repeatRows=1)
    cg_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),FIATA_BLUE),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe_c2))
    story.append(cg_t); story.append(Spacer(1,2*mm))

    # Terms + certification
    cert_t = tbl([[
        [Ps("15. FREIGHT & CHARGES","lbl"),
         Ps(f"Freight: {d['freight_terms']}","val"),
         Spacer(1,1*mm),
         Ps(f"Incoterms: {d['incoterm']}","sm"),
         Spacer(1,1*mm),
         Ps(f"No. of Originals: {d['originals']}","sm")],
        [Ps("16. CERTIFICATION","lbl"),
         Ps("The undersigned, on behalf of the Freight Forwarder, certifies that the above "
            "particulars are correct and that the goods are received in apparent good order and condition.","note"),
         Spacer(1,2*mm),
         Ps(f"Issued at: {d['issue_place']}", "sm"),
         Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}","sm"),
         Ps("Signature: _________________________","sm")],
    ]], [62*mm, 124*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(0,0),FIATA_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(cert_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — Short-Form Straight BOL (simplified 1-page)
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    GRN   = colors.HexColor("#1A6B3A")
    LGRAY = colors.HexColor("#F0F0F0")
    MGRN  = colors.HexColor("#EAF4EE")

    st = {
        "title": S("t",  fontName="Helvetica-Bold", fontSize=14, alignment=TA_CENTER, textColor=colors.white),
        "sub":   S("su", fontSize=8,  alignment=TA_CENTER, textColor=GRN),
        "lbl":   S("l",  fontSize=7,  textColor=colors.HexColor("#336644"), fontName="Helvetica-Bold"),
        "val":   S("v",  fontSize=8.5),
        "sm":    S("sm", fontSize=7.5,leading=10),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=7.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=7.5,leading=9),
        "cdr":   S("cdr",fontSize=7.5,leading=9, alignment=TA_RIGHT),
        "cdc":   S("cdc",fontSize=7.5,leading=9, alignment=TA_CENTER),
        "bold":  S("b",  fontName="Helvetica-Bold", fontSize=9),
        "note":  S("nt", fontSize=6.5,textColor=colors.HexColor("#555555")),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    # Title
    story.append(tbl([[Ps("STRAIGHT BILL OF LADING — SHORT FORM","title")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),GRN),
         ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
         ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(tbl([[Ps("NOT NEGOTIABLE  ·  ORIGINAL","sub")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),MGRN),
         ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    story.append(Spacer(1,2*mm))

    # Simple grid: B/L # and date on right
    hdr_grid = tbl([
        [Ps("B/L NUMBER","lbl"), Ps(d["bl_number"],"bold"),
         Ps("DATE","lbl"),       Ps(d["issue_date"].strftime("%d %b %Y"),"val")],
        [Ps("FREIGHT TERMS","lbl"), Ps(d["freight_terms"],"val"),
         Ps("INCOTERMS","lbl"),  Ps(d["incoterm"],"val")],
        [Ps("ORIGINALS","lbl"),  Ps(str(d["originals"]),"val"),
         Ps("PLACE OF ISSUE","lbl"), Ps(d["issue_place"],"val")],
    ], [28*mm, 65*mm, 28*mm, 65*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(0,-1),LGRAY),("BACKGROUND",(2,0),(2,-1),LGRAY),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),3)])
    story.append(hdr_grid); story.append(Spacer(1,1*mm))

    # Shipper / Consignee side by side
    parties = tbl([[
        [Ps("SHIPPER","lbl"), Ps(d["sn"],"val"), Ps(d["sa"],"sm"),
         Ps(f"Country: {d['sc'][0]}","sm")],
        [Ps("CONSIGNEE","lbl"), Ps(d["cn"],"val"), Ps(d["ca"],"sm"),
         Ps(f"Country: {d['cc'][0]}","sm")],
    ]], [93*mm, 93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),6),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(parties); story.append(Spacer(1,1*mm))

    # Routing in simple grid
    routing = tbl([
        [Ps("PORT OF LOADING","lbl"), Ps(d["pol"],"val"),
         Ps("PORT OF DISCHARGE","lbl"), Ps(d["pod"],"val")],
        [Ps("VESSEL","lbl"), Ps(d["vessel"],"val"),
         Ps("VOYAGE","lbl"), Ps(d["voyage"],"val")],
        [Ps("PLACE OF RECEIPT","lbl"), Ps(d["place_of_receipt"],"val"),
         Ps("PLACE OF DELIVERY","lbl"), Ps(d["place_of_delivery"],"val")],
    ], [36*mm, 57*mm, 36*mm, 57*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(0,-1),MGRN),("BACKGROUND",(2,0),(2,-1),MGRN),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),4)])
    story.append(routing); story.append(Spacer(1,1*mm))

    # Condensed items table
    items_rows = [
        [Ps("Marks & Numbers","ch"), Ps("Packages","ch"), Ps("Pkg Type","ch"),
         Ps("Description of Goods","ch"), Ps("HS Code","ch"),
         Ps("Gross Wt (KG)","ch"), Ps("Net Wt (KG)","ch"), Ps("CBM","ch")],
        [Ps(d["marks"],"cdc"),
         Ps(str(d["n_packages"]),"cdr"),
         Ps(d["pkg_type"],"cdc"),
         Ps(d["description"],"cd"),
         Ps(d["hs_code"],"cdc"),
         Ps(f"{d['gross_weight_kg']:,.1f}","cdr"),
         Ps(f"{d['net_weight_kg']:,.1f}","cdr"),
         Ps(f"{d['cbm']:.3f}","cdr")],
    ]
    # Container rows
    for c in d["containers"]:
        items_rows.append([
            Ps(c["container_no"],"cdc"), Ps("","cdr"),
            Ps(c["size_type"],"cdc"), Ps(f"Seal: {c['seal_no']}","cd"),
            Ps("","cdc"), Ps("","cdr"), Ps("","cdr"), Ps("","cdr")])
    items_t = Table(items_rows,
                    colWidths=[28*mm,18*mm,16*mm,52*mm,22*mm,20*mm,20*mm,10*mm],
                    repeatRows=1)
    n_items = len(items_rows) - 1
    stripe_i = [("BACKGROUND",(0,r),(-1,r),LGRAY) for r in range(1,n_items+1) if r%2==0]
    items_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),GRN),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ] + stripe_i))
    story.append(items_rows and items_t); story.append(Spacer(1,2*mm))

    # Declaration
    decl = tbl([[
        Ps("RECEIVED in apparent good order and condition the goods as described. "
           f"This Straight Bill of Lading is NOT NEGOTIABLE. Freight {d['freight_terms']}. "
           f"Issued at {d['issue_place']} on {d['issue_date'].strftime('%d %b %Y')}.","note"),
        [Ps("Carrier Signature:","lbl"), Spacer(1,4*mm),
         Ps("_______________________________","sm"),
         Ps(f"Date: {d['issue_date'].strftime('%d %b %Y')}","sm")],
    ]], [110*mm, 76*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(decl)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS   = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["Standard-Ocean-HBL","FIATA-FBL-Multimodal","Short-Form-Straight-BOL"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"hbl_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    ann = {
        "document_id":    fname.replace(".pdf",""),
        "document_class": "House Bill of Lading",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    2,
        "fields": {
            "bl_number": d["bl_number"],
            "shipper_name": d["sn"], "shipper_address": d["sa"], "shipper_country": d["sc"][0],
            "consignee_name": d["cn"], "consignee_address": d["ca"], "consignee_country": d["cc"][0],
            "notify_party_name": d["nn"], "notify_party_address": d["na"],
            "vessel": d["vessel"], "voyage": d["voyage"],
            "port_of_loading": d["pol"], "port_of_discharge": d["pod"],
            "place_of_receipt": d["place_of_receipt"], "place_of_delivery": d["place_of_delivery"],
            "issue_date": d["issue_date"].strftime("%Y-%m-%d"),
            "issue_place": d["issue_place"],
            "freight_terms": d["freight_terms"],
            "originals_issued": d["originals"],
            "incoterm": d["incoterm"],
            "containers": d["containers"],
            "description_of_goods": d["description"],
            "hs_code": d["hs_code"],
            "number_of_packages": d["n_packages"],
            "package_type": d["pkg_type"],
            "gross_weight_kg": d["gross_weight_kg"],
            "net_weight_kg": d["net_weight_kg"],
            "cbm": d["cbm"],
            "marks_and_numbers": d["marks"],
        }
    }
    (ANN_DIR / fname.replace(".pdf",".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} House Bill of Lading documents (3 format variants)...")
    for i in range(1, count+1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            print(f"  [{i:04d}] {a['format_variant'][:30]:<30} {f['bl_number']}  "
                  f"GW: {f['gross_weight_kg']:>8,.1f} kg  {len(f['containers'])} ctrs")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
