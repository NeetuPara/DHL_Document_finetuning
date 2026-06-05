"""
Dangerous Goods Declaration — 3 distinct real-world format variants.
Format 1: IATA DGD Column Format (air transport)
Format 2: IMDG/Sea Dangerous Goods Manifest (ocean freight)
Format 3: Non-Dangerous Goods Declaration / Shipper's Declaration (exempt/not DG)
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

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "05_Dangerous_Goods_Declaration"
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

# Extended DG data
DG_ENTRIES = [
    {"un_no":"UN1263","proper_name":"Paint","class":"3","div":None,
     "pg":"II","hazard_label":"Flammable Liquid","ems":"F-E, S-E","stow":"Category B",
     "marine_pollutant":False,"flashpoint":"-18°C","pi_air":"Y344","sp":""},
    {"un_no":"UN1950","proper_name":"Aerosols, flammable","class":"2.1","div":"2.1",
     "pg":None,"hazard_label":"Flammable Gas","ems":"F-D, S-U","stow":"Category A",
     "marine_pollutant":False,"flashpoint":"N/A","pi_air":"Y203","sp":"SP63"},
    {"un_no":"UN3480","proper_name":"Lithium ion batteries","class":"9","div":None,
     "pg":"II","hazard_label":"Class 9 Miscellaneous","ems":"F-A, S-I","stow":"Category A",
     "marine_pollutant":False,"flashpoint":"N/A","pi_air":"PI 965","sp":"SP188"},
    {"un_no":"UN1993","proper_name":"Flammable liquid, n.o.s. (contains Acetone, Ethanol)","class":"3","div":None,
     "pg":"III","hazard_label":"Flammable Liquid","ems":"F-E, S-E","stow":"Category B",
     "marine_pollutant":False,"flashpoint":"23°C","pi_air":"Y344","sp":""},
    {"un_no":"UN2794","proper_name":"Batteries, wet, filled with acid","class":"8","div":None,
     "pg":None,"hazard_label":"Corrosive","ems":"F-A, S-B","stow":"Category A",
     "marine_pollutant":False,"flashpoint":"N/A","pi_air":"Y820","sp":"SP207"},
    {"un_no":"UN1017","proper_name":"Chlorine","class":"2.3","div":"2.3",
     "pg":None,"hazard_label":"Toxic Gas","ems":"F-C, S-U","stow":"Category D",
     "marine_pollutant":True,"flashpoint":"N/A","pi_air":"Forbidden","sp":""},
    {"un_no":"UN1203","proper_name":"Gasoline (Petrol)","class":"3","div":None,
     "pg":"II","hazard_label":"Flammable Liquid","ems":"F-E, S-E","stow":"Category B",
     "marine_pollutant":False,"flashpoint":"-43°C","pi_air":"Y344","sp":""},
    {"un_no":"UN3077","proper_name":"Environmentally hazardous substance, solid, n.o.s.","class":"9","div":None,
     "pg":"III","hazard_label":"Class 9 Misc / Marine Pollutant","ems":"F-A, S-F","stow":"Category A",
     "marine_pollutant":True,"flashpoint":"N/A","pi_air":"Y956","sp":"SP274"},
    {"un_no":"UN2315","proper_name":"Polychlorinated biphenyls (liquid)","class":"9","div":None,
     "pg":"II","hazard_label":"Class 9 Miscellaneous","ems":"F-A, S-F","stow":"Category A",
     "marine_pollutant":True,"flashpoint":"N/A","pi_air":"Y956","sp":"SP274"},
    {"un_no":"UN1072","proper_name":"Oxygen, compressed","class":"2.2","div":"2.2",
     "pg":None,"hazard_label":"Non-flammable Gas (Oxidizing)","ems":"F-C, S-W","stow":"Category D",
     "marine_pollutant":False,"flashpoint":"N/A","pi_air":"Y206","sp":""},
]

NON_DG_REASONS = [
    ("Lithium Ion Batteries — Section II (PI 967/Section II)", "UN3481", "9"),
    ("Lithium Metal Batteries — Section II (PI 970/Section II)", "UN3091", "9"),
    ("Dry Ice (Carbon Dioxide, solid) — Section I small quantity", "UN1845", "9"),
    ("Magnetized material — not subject to IATA DGR", "N/A", "N/A"),
    ("Non-regulated chemical — not classified as DG per IATA/IMDG", "N/A", "N/A"),
    ("Consumer commodity ORM-D", "N/A", "N/A"),
    ("Excepted quantities (EQ) per IATA DGR 2.6", "Various", "Various"),
]


def make_data():
    sc = random_country(); dc = random_country()
    while dc[1] == sc[1]: dc = random_country()

    sn = random_company(); sa = fake.address().replace("\n", ", ") + f", {sc[0]}"
    cn = random_company(); ca = fake.address().replace("\n", ", ") + f", {dc[0]}"
    emergency_tel = f"+{random.randint(1,99)} {random.randint(100,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"

    # Air
    dep_airport = random.choice(AIRPORTS)
    arr_airport = random.choice(AIRPORTS)
    while arr_airport[1] == dep_airport[1]: arr_airport = random.choice(AIRPORTS)
    awb_number  = random_hawb_number()
    flight_date = fake.date_between(start_date="-30d", end_date="+30d")
    flight_no   = f"{random.choice(['DL','UA','LH','EK','SQ','CX','QR'])}{random.randint(100,9999)}"

    # Sea
    vessel  = random.choice(VESSEL_NAMES)
    voyage  = f"{random.randint(100,999)}{''.join(random.choices('NESW',k=1))}"
    pol     = random.choice(PORTS_SEA)
    pod     = random.choice(PORTS_SEA)
    while pod == pol: pod = random.choice(PORTS_SEA)

    n_dg = random.randint(1, 3)
    dg_entries = random.sample(DG_ENTRIES, n_dg)
    for e in dg_entries:
        e = e.copy()
    filled_entries = []
    for e in dg_entries:
        n_pkgs  = random.randint(1, 50)
        net_qty = round(random.uniform(0.5, 100), 2)
        qty_unit= random.choice(["kg","L","mL","g"])
        auth_no = f"CA-{random.randint(100000,999999)}" if random.random() > 0.5 else "N/A"
        filled_entries.append({
            "un_no":             e["un_no"],
            "proper_name":       e["proper_name"],
            "class":             e["class"],
            "packing_group":     e["pg"] or "N/A",
            "n_packages":        n_pkgs,
            "pkg_type":          random.choice(["UN Specification Box","Fibreboard Box","Steel Drum","Plastic Jerry Can"]),
            "net_qty":           net_qty,
            "qty_unit":          qty_unit,
            "packing_instruction": e["pi_air"],
            "auth_no":           auth_no,
            "special_provision": e["sp"],
            "hazard_label":      e["hazard_label"],
            "marine_pollutant":  e["marine_pollutant"],
            "flashpoint":        e["flashpoint"],
            "ems":               e["ems"],
            "stow_category":     e["stow"],
        })

    signatory   = fake.name()
    sign_date   = fake.date_between(start_date="-30d", end_date="today")
    sign_place  = sc[0].split(",")[0]

    non_dg_reason = random.choice(NON_DG_REASONS)

    return dict(
        shipper_name=sn, shipper_address=sa, shipper_country=sc,
        consignee_name=cn, consignee_address=ca, consignee_country=dc,
        emergency_tel=emergency_tel,
        awb_number=awb_number, flight_no=flight_no, flight_date=flight_date,
        dep_airport=dep_airport, arr_airport=arr_airport,
        vessel=vessel, voyage=voyage, pol=pol, pod=pod,
        dg_entries=filled_entries,
        signatory=signatory, sign_date=sign_date, sign_place=sign_place,
        non_dg_reason=non_dg_reason,
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — IATA DGD Column Format (Air Transport)
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    IATA_RED    = colors.HexColor("#CC0000")
    IATA_GRAY   = colors.HexColor("#F0F0F0")
    IATA_DARK   = colors.HexColor("#1A1A1A")
    IATA_WARN   = colors.HexColor("#FF6600")

    st = {
        "warn":  S("w",  fontName="Helvetica-Bold", fontSize=9,  alignment=TA_CENTER,
                   textColor=colors.white),
        "title": S("t",  fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER,
                   textColor=colors.white),
        "lbl":   S("l",  fontSize=7,  textColor=colors.HexColor("#440000"), fontName="Helvetica-Bold"),
        "val":   S("v",  fontSize=8),
        "sm":    S("sm", fontSize=7,  leading=9),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=7,  leading=9),
        "cdr":   S("cdr",fontSize=7,  leading=9, alignment=TA_RIGHT),
        "cdc":   S("cdc",fontSize=7,  leading=9, alignment=TA_CENTER),
        "bold":  S("b",  fontName="Helvetica-Bold", fontSize=8.5),
        "decl":  S("dc", fontSize=6.5,leading=8.5,textColor=colors.HexColor("#333333")),
        "alert": S("al", fontName="Helvetica-Bold", fontSize=7.5, textColor=IATA_WARN),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    # IATA Warning Header
    story.append(tbl([[
        Ps("WARNING — FAILURE TO COMPLY IN ALL RESPECTS WITH THE APPLICABLE DANGEROUS GOODS "
           "REGULATIONS MAY BE IN BREACH OF APPLICABLE LAW, SUBJECT TO LEGAL PENALTIES. "
           "THIS DECLARATION MUST NOT BE USED FOR EXPLOSIVES (CLASS 1) OR RADIOACTIVE MATERIALS (CLASS 7).", "warn")
    ]], [W],
    [("BACKGROUND",(0,0),(-1,-1),IATA_RED),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
     ("BOX",(0,0),(-1,-1),1,IATA_DARK)]))
    story.append(tbl([[Ps("SHIPPER'S DECLARATION FOR DANGEROUS GOODS (IATA)","title")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),IATA_DARK),
         ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
         ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(Spacer(1,1*mm))

    # Shipper + Consignee + Flight
    top_t = tbl([[
        [Ps("SHIPPER","lbl"), Ps(d["shipper_name"],"bold"),
         Ps(d["shipper_address"],"sm"),
         Ps(f"Country: {d['shipper_country'][0]}","sm"),
         Spacer(1,1*mm),
         Ps(f"Emergency Tel: {d['emergency_tel']}","sm")],
        [Ps("CONSIGNEE","lbl"), Ps(d["consignee_name"],"bold"),
         Ps(d["consignee_address"],"sm"),
         Ps(f"Country: {d['consignee_country'][0]}","sm")],
        [Ps("FLIGHT / TRANSPORT DETAILS","lbl"),
         Ps(f"AWB No: {d['awb_number']}","bold"),
         Ps(f"Flight No: {d['flight_no']}","sm"),
         Ps(f"Date: {d['flight_date'].strftime('%d %b %Y')}","sm"),
         Spacer(1,1*mm),
         Ps(f"Origin: {d['dep_airport'][0]} ({d['dep_airport'][1]})","sm"),
         Ps(f"Destination: {d['arr_airport'][0]} ({d['arr_airport'][1]})","sm")],
    ]], [62*mm,62*mm,62*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(top_t); story.append(Spacer(1,1*mm))

    # Airport pair + transport category
    apt_t = tbl([
        [Ps("AIRPORT OF DEPARTURE","lbl"),
         Ps(f"{d['dep_airport'][0]} ({d['dep_airport'][1]})","val"),
         Ps("AIRPORT OF DESTINATION","lbl"),
         Ps(f"{d['arr_airport'][0]} ({d['arr_airport'][1]})","val"),
         Ps("AIRCRAFT TYPE","lbl"),
         Ps(random.choice(["Passenger and Cargo","Cargo Aircraft Only","Cargo Only"]),"bold")],
    ], [32*mm,42*mm,32*mm,42*mm,30*mm,8*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(0,-1),IATA_GRAY),("BACKGROUND",(2,0),(2,-1),IATA_GRAY),
     ("BACKGROUND",(4,0),(4,-1),IATA_GRAY),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),3)])
    story.append(apt_t); story.append(Spacer(1,1*mm))

    # DG Entries table
    n = len(d["dg_entries"])
    dg_rows = [[Ps("UN No.","ch"), Ps("Proper Shipping Name\n& Technical Name","ch"),
                Ps("Class\n/Div","ch"), Ps("Packing\nGroup","ch"),
                Ps("Qty &\nType of Pkg","ch"), Ps("Net Qty","ch"),
                Ps("Packing\nInstruct.","ch"), Ps("Auth. No.","ch"),
                Ps("Special\nProvision","ch"), Ps("Hazard\nLabel","ch")]]
    for e in d["dg_entries"]:
        dg_rows.append([
            Ps(e["un_no"],"cdc"),
            Ps(e["proper_name"],"cd"),
            Ps(e["class"],"cdc"),
            Ps(e["packing_group"],"cdc"),
            Ps(f"{e['n_packages']} x\n{e['pkg_type']}","cd"),
            Ps(f"{e['net_qty']} {e['qty_unit']}","cdr"),
            Ps(e["packing_instruction"],"cdc"),
            Ps(e["auth_no"],"cdc"),
            Ps(e["special_provision"] or "—","cdc"),
            Ps(e["hazard_label"],"cd")])
    stripe_d = [("BACKGROUND",(0,r),(-1,r),IATA_GRAY) for r in range(1,n+1) if r%2==0]
    dg_t = Table(dg_rows, colWidths=[14*mm,44*mm,12*mm,12*mm,22*mm,16*mm,16*mm,18*mm,14*mm,18*mm], repeatRows=1)
    dg_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),IATA_DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe_d))
    story.append(dg_t); story.append(Spacer(1,2*mm))

    # IATA Declaration text
    decl_text = (
        "I hereby declare that the contents of this consignment are fully and accurately described above by the proper "
        "shipping name, and are classified, packaged, marked and labelled/placarded, and are in all respects in proper "
        "condition for transport according to applicable international and national governmental regulations."
    )
    story.append(tbl([[Ps(decl_text,"decl")]], [W],
        [("BOX",(0,0),(-1,-1),.5,BORDER),("LEFTPADDING",(0,0),(-1,-1),5),
         ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
         ("BACKGROUND",(0,0),(-1,-1),IATA_GRAY)]))
    story.append(Spacer(1,1*mm))

    # Signature block
    sig_t = tbl([[
        [Ps("NAME OF SIGNATORY","lbl"), Ps(d["signatory"],"bold"),
         Spacer(1,1*mm),
         Ps(f"Place: {d['sign_place']}","sm"),
         Ps(f"Date: {d['sign_date'].strftime('%d %b %Y')}","sm")],
        [Ps("SIGNATURE","lbl"),
         Spacer(1,8*mm),
         Ps("_________________________","sm"),
         Ps("(Signature of Shipper or Agent)","decl")],
    ]], [93*mm,93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — IMDG / Sea Dangerous Goods Manifest
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    SEA_BLUE   = colors.HexColor("#003D6B")
    SEA_LIGHT  = colors.HexColor("#DCEEFF")
    SEA_STRIPE = colors.HexColor("#EAF4FF")
    ORANGE     = colors.HexColor("#E65100")

    st = {
        "title": S("t",  fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER, textColor=colors.white),
        "sub":   S("su", fontName="Helvetica-Bold", fontSize=8,  alignment=TA_CENTER, textColor=SEA_BLUE),
        "lbl":   S("l",  fontSize=7,  textColor=SEA_BLUE, fontName="Helvetica-Bold"),
        "val":   S("v",  fontSize=8.5),
        "sm":    S("sm", fontSize=7,  leading=9),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=7,  leading=9),
        "cdr":   S("cdr",fontSize=7,  leading=9, alignment=TA_RIGHT),
        "cdc":   S("cdc",fontSize=7,  leading=9, alignment=TA_CENTER),
        "bold":  S("b",  fontName="Helvetica-Bold", fontSize=8.5, textColor=SEA_BLUE),
        "mp":    S("mp", fontName="Helvetica-Bold", fontSize=7.5, textColor=ORANGE),
        "decl":  S("dc", fontSize=6.5,leading=8.5,textColor=colors.HexColor("#222244")),
    }
    def Ps(t, s): return P(t, st[s])

    # Sea-specific container data
    container_no = random_container_number()
    seal_no      = random_seal_number()
    ctr_type     = random.choice(["20'GP","40'GP","40'HC","20'OT"])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    story.append(tbl([
        [Ps("DANGEROUS GOODS MANIFEST — IMDG CODE (SEA TRANSPORT)","title")],
    ], [W],
    [("BACKGROUND",(0,0),(-1,-1),SEA_BLUE),
     ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(tbl([[Ps("INTERNATIONAL MARITIME DANGEROUS GOODS CODE  ·  OCEAN FREIGHT","sub")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),SEA_LIGHT),
         ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    story.append(Spacer(1,1*mm))

    # Vessel + port block
    vessel_data = [
        [Ps("VESSEL","lbl"), Ps(d["vessel"],"bold"),
         Ps("VOYAGE","lbl"), Ps(d["voyage"],"val"),
         Ps("PORT OF LOADING","lbl"), Ps(d["pol"],"val")],
        [Ps("PORT OF DISCHARGE","lbl"), Ps(d["pod"],"val"),
         Ps("B/L NUMBER","lbl"), Ps(random_bl_number(),"val"),
         Ps("DATE","lbl"), Ps(d["sign_date"].strftime("%d %b %Y"),"val")],
    ]
    v_t = Table(vessel_data, colWidths=[28*mm,38*mm,28*mm,38*mm,28*mm,26*mm])
    v_t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("BACKGROUND",(0,0),(0,-1),SEA_LIGHT),("BACKGROUND",(2,0),(2,-1),SEA_LIGHT),
        ("BACKGROUND",(4,0),(4,-1),SEA_LIGHT),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(v_t); story.append(Spacer(1,1*mm))

    # Shipper + Consignee
    sc_t = tbl([[
        [Ps("SHIPPER","lbl"), Ps(d["shipper_name"],"bold"), Ps(d["shipper_address"],"sm"),
         Ps(f"Emergency Tel: {d['emergency_tel']}","sm")],
        [Ps("CONSIGNEE","lbl"), Ps(d["consignee_name"],"bold"), Ps(d["consignee_address"],"sm")],
        [Ps("CONTAINER","lbl"), Ps(container_no,"bold"),
         Ps(f"Seal: {seal_no}","sm"), Ps(f"Type: {ctr_type}","sm")],
    ]], [62*mm,62*mm,62*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(sc_t); story.append(Spacer(1,1*mm))

    # IMDG DG table — extended columns
    n = len(d["dg_entries"])
    imdg_rows = [[Ps("UN No.","ch"), Ps("Proper Shipping Name","ch"),
                  Ps("IMDG\nClass","ch"), Ps("Packing\nGroup","ch"),
                  Ps("Flashpoint","ch"), Ps("Marine\nPollutant","ch"),
                  Ps("EmS Code","ch"), Ps("Stowage\nCategory","ch"),
                  Ps("No. Pkgs\n& Type","ch"), Ps("Net Qty\n(kg/L)","ch")]]
    for e in d["dg_entries"]:
        mp_text = "YES" if e["marine_pollutant"] else "NO"
        imdg_rows.append([
            Ps(e["un_no"],"cdc"),
            Ps(e["proper_name"],"cd"),
            Ps(e["class"],"cdc"),
            Ps(e["packing_group"],"cdc"),
            Ps(e["flashpoint"],"cdc"),
            Ps(mp_text, "mp" if e["marine_pollutant"] else "cdc"),
            Ps(e["ems"],"cdc"),
            Ps(e["stow_category"],"cdc"),
            Ps(f"{e['n_packages']}\n{e['pkg_type']}","cd"),
            Ps(f"{e['net_qty']} {e['qty_unit']}","cdr")])
    stripe_i = [("BACKGROUND",(0,r),(-1,r),SEA_STRIPE) for r in range(1,n+1) if r%2==0]
    imdg_t = Table(imdg_rows,
                   colWidths=[14*mm,40*mm,12*mm,12*mm,16*mm,14*mm,16*mm,18*mm,22*mm,22*mm],
                   repeatRows=1)
    imdg_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),SEA_BLUE),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe_i))
    story.append(imdg_t); story.append(Spacer(1,2*mm))

    # Certification
    decl_t = tbl([[
        Ps("MASTER'S DECLARATION: I hereby certify that the dangerous goods listed above are properly "
           "classified, packed, marked, labelled and are in proper condition for carriage by sea "
           "in accordance with the applicable provisions of the IMDG Code.","decl"),
        [Ps("SHIPPER'S DECLARATION","lbl"),
         Ps(f"Signed: {d['signatory']}","sm"),
         Ps(f"Date: {d['sign_date'].strftime('%d %b %Y')}","sm"),
         Ps(f"Place: {d['sign_place']}","sm"),
         Spacer(1,3*mm),
         Ps("Signature: _________________________","sm")],
    ]], [100*mm,86*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(0,0),SEA_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(decl_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — Non-Dangerous Goods Declaration / Shipper's Declaration
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    NDG_GREEN  = colors.HexColor("#1B5E20")
    NDG_LIGHT  = colors.HexColor("#E8F5E9")
    NDG_MID    = colors.HexColor("#A5D6A7")
    CHECK_BG   = colors.HexColor("#F1F8E9")

    st = {
        "title": S("t",  fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, textColor=colors.white),
        "sub":   S("su", fontName="Helvetica-Bold", fontSize=8.5,alignment=TA_CENTER, textColor=NDG_GREEN),
        "lbl":   S("l",  fontSize=7.5,textColor=NDG_GREEN, fontName="Helvetica-Bold"),
        "val":   S("v",  fontSize=8.5),
        "sm":    S("sm", fontSize=7.5,leading=10),
        "bold":  S("b",  fontName="Helvetica-Bold", fontSize=9, textColor=NDG_GREEN),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=7,  alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=7.5,leading=9.5),
        "cdr":   S("cdr",fontSize=7.5,leading=9.5,alignment=TA_RIGHT),
        "cdc":   S("cdc",fontSize=7.5,leading=9.5,alignment=TA_CENTER),
        "chk":   S("ck", fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER,
                   textColor=NDG_GREEN),
        "decl":  S("dc", fontSize=7,  leading=9.5,textColor=colors.HexColor("#1A1A1A")),
        "cert":  S("ct", fontName="Helvetica-Bold", fontSize=8, textColor=NDG_GREEN),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    W3 = 180*mm
    story = []

    story.append(tbl([
        [Ps("SHIPPER'S DECLARATION — NON-DANGEROUS GOODS","title")],
    ], [W3],
    [("BACKGROUND",(0,0),(-1,-1),NDG_GREEN),
     ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(tbl([[Ps("Declaration that goods are NOT dangerous or are EXEMPT from DG regulations","sub")]], [W3],
        [("BACKGROUND",(0,0),(-1,-1),NDG_LIGHT),
         ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(Spacer(1,2*mm))

    # Reference + AWB
    ref_t = tbl([
        [Ps("AWB / REFERENCE","lbl"), Ps(d["awb_number"],"bold"),
         Ps("DATE","lbl"), Ps(d["sign_date"].strftime("%d %b %Y"),"val"),
         Ps("ORIGIN","lbl"), Ps(f"{d['dep_airport'][0]} ({d['dep_airport'][1]})","val")],
        [Ps("DESTINATION","lbl"), Ps(f"{d['arr_airport'][0]} ({d['arr_airport'][1]})","val"),
         Ps("FLIGHT","lbl"), Ps(d["flight_no"],"val"),
         Ps("EMERGENCY TEL","lbl"), Ps(d["emergency_tel"],"val")],
    ], [28*mm,48*mm,20*mm,38*mm,28*mm,24*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(0,-1),NDG_LIGHT),("BACKGROUND",(2,0),(2,-1),NDG_LIGHT),
     ("BACKGROUND",(4,0),(4,-1),NDG_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),3)])
    story.append(ref_t); story.append(Spacer(1,2*mm))

    # Shipper + Consignee
    sc_t = tbl([[
        [Ps("SHIPPER","lbl"), Ps(d["shipper_name"],"bold"),
         Ps(d["shipper_address"],"sm"),
         Ps(f"Country: {d['shipper_country'][0]}","sm")],
        [Ps("CONSIGNEE","lbl"), Ps(d["consignee_name"],"bold"),
         Ps(d["consignee_address"],"sm"),
         Ps(f"Country: {d['consignee_country'][0]}","sm")],
    ]], [90*mm,90*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),6),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(sc_t); story.append(Spacer(1,2*mm))

    # Commodity description table
    reason = d["non_dg_reason"]
    cat    = random.choice(COMMODITY_CATEGORIES)
    n_pkgs = random.randint(1, 100)
    wt     = round(n_pkgs * random.uniform(*cat["unit_weight_kg"]), 2)

    goods_t = tbl([
        [Ps("COMMODITY DESCRIPTION","ch"), Ps("UN No. (if any)","ch"),
         Ps("DG Class (if any)","ch"), Ps("No. Pkgs","ch"),
         Ps("Net Wt (KG)","ch"), Ps("Basis for Exemption","ch")],
        [Ps(cat["description"],"cd"),
         Ps(reason[1],"cdc"),
         Ps(reason[2],"cdc"),
         Ps(str(n_pkgs),"cdr"),
         Ps(f"{wt:.2f}","cdr"),
         Ps(reason[0],"cd")],
    ], [54*mm,20*mm,20*mm,16*mm,20*mm,56*mm],
    [("BACKGROUND",(0,0),(-1,0),NDG_GREEN),("TEXTCOLOR",(0,0),(-1,0),colors.white),
     ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(goods_t); story.append(Spacer(1,2*mm))

    # Checkbox declaration blocks
    chk_items = [
        (True,  "These goods are NOT classified as dangerous goods under IATA Dangerous Goods Regulations (DGR) "
                 "or IMDG Code."),
        (True,  "These goods do NOT contain any restricted or prohibited articles."),
        (random.random()>0.5,
                 "If batteries are present, they comply with Section II of PI 965/966/967 (IATA DGR)."),
        (random.random()>0.5,
                 "If dry ice is present, quantity does not exceed limits for excepted quantities."),
        (True,  "No radioactive materials (Class 7) or explosive materials (Class 1) are present."),
    ]
    chk_rows = []
    for checked, text in chk_items:
        chk_rows.append([
            Ps("X" if checked else "□","chk"),
            Ps(text,"sm")])
    chk_t = Table(chk_rows, colWidths=[10*mm,170*mm])
    chk_t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("BACKGROUND",(0,0),(-1,-1),CHECK_BG),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(chk_t); story.append(Spacer(1,2*mm))

    # UN Negative Statement
    neg_stmt = (
        f"I/We hereby declare that the goods described herein are NOT classified as dangerous goods "
        f"under applicable transport regulations (IATA DGR / IMDG Code / ADR). "
        f"The shipment does not contain any items listed in the IATA Dangerous Goods List or the IMDG Code. "
        f"Goods are: {cat['description']}. Basis: {reason[0]}."
    )
    story.append(tbl([[Ps(neg_stmt,"decl")]], [W3],
        [("BOX",(0,0),(-1,-1),.5,BORDER),("LEFTPADDING",(0,0),(-1,-1),5),
         ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
         ("BACKGROUND",(0,0),(-1,-1),NDG_LIGHT)]))
    story.append(Spacer(1,2*mm))

    # Signatory
    sig_t = tbl([[
        [Ps("AUTHORIZED SIGNATORY","lbl"), Ps(d["signatory"],"bold"),
         Ps(f"Date: {d['sign_date'].strftime('%d %b %Y')}","sm"),
         Ps(f"Place: {d['sign_place']}","sm")],
        [Ps("SHIPPER'S DECLARATION","lbl"),
         Spacer(1,6*mm),
         Ps("Signature: _________________________","sm"),
         Ps("(Shipper or Authorized Agent)","decl")],
    ]], [93*mm,87*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS   = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["IATA-DGD-Air-Column-Format","IMDG-Sea-DG-Manifest","Non-DG-Shippers-Declaration"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"dgd_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Fields common to all three formats
    fields = {
        "shipper_name": d["shipper_name"], "shipper_address": d["shipper_address"],
        "shipper_country": d["shipper_country"][0],
        "consignee_name": d["consignee_name"], "consignee_address": d["consignee_address"],
        "consignee_country": d["consignee_country"][0],
        "emergency_telephone": d["emergency_tel"],
        "dg_entries": d["dg_entries"],
        "signatory_name": d["signatory"],
        "signature_date": d["sign_date"].strftime("%Y-%m-%d"),
        "signature_place": d["sign_place"],
    }

    if fmt_idx == 0:
        # fmt1 (IATA-Air): renders awb_number, flight_no, flight_date,
        # dep_airport, arr_airport — no vessel/voyage/pol/pod
        fields["awb_number"] = d["awb_number"]
        fields["flight_number"] = d["flight_no"]
        fields["flight_date"] = d["flight_date"].strftime("%Y-%m-%d")
        fields["departure_airport_code"] = d["dep_airport"][1]
        fields["departure_airport_name"] = d["dep_airport"][0]
        fields["destination_airport_code"] = d["arr_airport"][1]
        fields["destination_airport_name"] = d["arr_airport"][0]

    elif fmt_idx == 1:
        # fmt2 (IMDG-Sea): renders vessel, voyage, pol, pod — no flight/airport fields
        fields["vessel"] = d["vessel"]
        fields["voyage"] = d["voyage"]
        fields["port_of_loading"] = d["pol"]
        fields["port_of_discharge"] = d["pod"]

    elif fmt_idx == 2:
        # fmt3 (Non-DG-Shippers-Declaration): renders awb_number, flight_no,
        # dep_airport, arr_airport — no vessel/voyage/pol/pod; adds non_dg_reason
        fields["awb_number"] = d["awb_number"]
        fields["flight_number"] = d["flight_no"]
        fields["departure_airport_code"] = d["dep_airport"][1]
        fields["departure_airport_name"] = d["dep_airport"][0]
        fields["destination_airport_code"] = d["arr_airport"][1]
        fields["destination_airport_name"] = d["arr_airport"][0]
        fields["non_dg_reason"] = d["non_dg_reason"][0]

    ann = {
        "document_id":    fname.replace(".pdf",""),
        "document_class": "Dangerous Goods Declaration",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    5,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf",".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} Dangerous Goods Declaration documents (3 format variants)...")
    for i in range(1, count+1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            n_dg = len(f["dg_entries"])
            ref = f.get("awb_number") or f.get("vessel", "—")
            print(f"  [{i:04d}] {a['format_variant'][:30]:<30} {ref}  "
                  f"DG entries: {n_dg}")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
