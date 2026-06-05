"""
Verified Gross Mass (VGM) — 3 distinct real-world format variants.
Format 1: Standard VGM Declaration (Method 1 — full container weighing)
Format 2: VGM Method 2 (sum of packages + tare weight, detailed calculation table)
Format 3: Carrier/Terminal VGM Submission Form (booking/EDI/terminal focus)
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

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "06_Verified_Gross_Mass"
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

CONTAINER_SIZES = {
    "20'GP": {"tare": 2200, "max_payload": 21800},
    "40'GP": {"tare": 3800, "max_payload": 26680},
    "40'HC": {"tare": 4000, "max_payload": 26600},
    "45'HC": {"tare": 4800, "max_payload": 27600},
    "20'RF": {"tare": 3100, "max_payload": 21100},
    "40'RF": {"tare": 4800, "max_payload": 22000},
    "20'OT": {"tare": 2400, "max_payload": 21200},
    "40'OT": {"tare": 4200, "max_payload": 26500},
}
ISO_CODES = {
    "20'GP": "22G0", "40'GP": "42G0", "40'HC": "45G0", "45'HC": "L5G0",
    "20'RF": "22R1", "40'RF": "42R1", "20'OT": "22U0", "40'OT": "42U0",
}
WEIGHING_SCALES = [
    "Certified Static Scale — Serial No.",
    "Calibrated Platform Scale — ID",
    "Approved Weighbridge — Ref",
    "Certified Electronic Scale — Unit",
]
TERMINALS = [
    "DP World Southampton", "APM Terminals Rotterdam", "PSA Singapore Pasir Panjang",
    "Everport Terminal Los Angeles", "HHLA Hamburg Terminal",
    "Qingdao Qianwan Container Terminal", "Dubai Jebel Ali Terminal",
    "Yantian International Container Terminal",
]
SHIPPING_LINES = [
    "Maersk Line", "MSC Mediterranean Shipping", "CMA CGM Group",
    "Evergreen Marine", "COSCO Shipping Lines", "Hapag-Lloyd",
    "ONE (Ocean Network Express)", "Yang Ming Marine Transport",
    "HMM (Hyundai Merchant Marine)",
]


def make_data():
    sc = random_country()
    sn = random_company(); sa = fake.address().replace("\n", ", ") + f", {sc[0]}"

    container_size = random.choice(list(CONTAINER_SIZES.keys()))
    container_no   = random_container_number()
    seal_no        = random_seal_number()
    iso_code       = ISO_CODES[container_size]
    tare_weight    = CONTAINER_SIZES[container_size]["tare"]
    max_payload    = CONTAINER_SIZES[container_size]["max_payload"]

    cargo_weight   = round(random.uniform(2000, max_payload * 0.85), 1)
    packing_wt     = round(random.uniform(50, 500), 1)
    vgm            = round(cargo_weight + packing_wt + tare_weight, 1)

    # Method 2: individual package weights
    n_pkgs = random.randint(4, 20)
    packages = []
    remaining = cargo_weight
    for i in range(n_pkgs):
        if i == n_pkgs - 1:
            pkg_wt = round(remaining, 1)
        else:
            pkg_wt = round(random.uniform(50, remaining / (n_pkgs - i) * 1.5), 1)
            pkg_wt = min(pkg_wt, remaining - (n_pkgs - i - 1) * 20)
            remaining -= pkg_wt
        cat = random.choice(COMMODITY_CATEGORIES)
        n_units = random.randint(1, 20)
        packages.append({
            "item_no":     i + 1,
            "description": cat["description"],
            "pkg_type":    random.choice(PACKAGE_TYPES),
            "n_units":     n_units,
            "gross_wt_kg": max(pkg_wt, 1.0),
        })
    # Recalculate cargo from packages
    actual_cargo_wt = round(sum(p["gross_wt_kg"] for p in packages), 1)
    vgm = round(actual_cargo_wt + packing_wt + tare_weight, 1)

    vessel       = random.choice(VESSEL_NAMES)
    voyage       = f"{random.randint(100,999)}{''.join(random.choices('NESW',k=1))}"
    pol          = random.choice(PORTS_SEA)
    pod          = random.choice(PORTS_SEA)
    while pod == pol: pod = random.choice(PORTS_SEA)
    bl_number    = random_bl_number()
    booking_ref  = f"BKG-{random.randint(100000,999999)}"
    cutoff_date  = fake.date_between(start_date="+1d", end_date="+14d")
    sign_date    = fake.date_between(start_date="-7d", end_date="today")
    vgm_ref      = f"VGM-{random.randint(1000000,9999999)}"
    edi_ref      = f"EDI-{fake.bothify('##??####??##')}"
    terminal     = random.choice(TERMINALS)
    shipping_line= random.choice(SHIPPING_LINES)

    scale_type   = random.choice(WEIGHING_SCALES)
    scale_serial = f"{scale_type.split('—')[1].strip()}-{random.randint(10000,99999)}"
    calibration  = fake.date_between(start_date="-12m", end_date="-1m")

    signatory    = fake.name()
    title        = random.choice(["Logistics Manager","Operations Director","Export Manager",
                                   "Shipping Coordinator","VGM Officer"])

    return dict(
        shipper_name=sn, shipper_address=sa, shipper_country=sc,
        container_no=container_no, seal_no=seal_no,
        container_size=container_size, iso_code=iso_code,
        tare_weight_kg=tare_weight, cargo_weight_kg=actual_cargo_wt,
        packing_materials_kg=packing_wt, vgm_kg=vgm,
        packages=packages, n_packages=len(packages),
        vessel=vessel, voyage=voyage, pol=pol, pod=pod,
        bl_number=bl_number, booking_ref=booking_ref,
        cutoff_date=cutoff_date, sign_date=sign_date,
        vgm_ref=vgm_ref, edi_ref=edi_ref,
        terminal=terminal, shipping_line=shipping_line,
        scale_type=scale_type.split("—")[0].strip(),
        scale_serial=scale_serial, calibration_date=calibration,
        signatory=signatory, title=title,
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — Standard VGM Declaration (Method 1 — full container weighing)
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    SOLAS_BLUE  = colors.HexColor("#1A237E")
    SOLAS_LIGHT = colors.HexColor("#E8EAF6")
    VGM_ORANGE  = colors.HexColor("#E65100")
    LGRAY       = colors.HexColor("#F5F5F5")

    st = {
        "title":  S("t",  fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, textColor=colors.white),
        "sub":    S("su", fontName="Helvetica-Bold", fontSize=9,  alignment=TA_CENTER, textColor=SOLAS_BLUE),
        "lbl":    S("l",  fontSize=7,  textColor=colors.HexColor("#1A237E"), fontName="Helvetica-Bold"),
        "val":    S("v",  fontSize=8.5),
        "sm":     S("sm", fontSize=7,  leading=9),
        "bold":   S("b",  fontName="Helvetica-Bold", fontSize=9),
        "vgm":    S("vg", fontName="Helvetica-Bold", fontSize=14, alignment=TA_RIGHT, textColor=VGM_ORANGE),
        "vgmlbl": S("vl", fontName="Helvetica-Bold", fontSize=9, textColor=VGM_ORANGE),
        "wt":     S("wt", fontName="Helvetica-Bold", fontSize=10, alignment=TA_RIGHT),
        "meth":   S("mt", fontName="Helvetica-Bold", fontSize=8.5, textColor=SOLAS_BLUE),
        "solas":  S("so", fontSize=7,  leading=9, textColor=colors.HexColor("#333366")),
        "note":   S("nt", fontSize=6.5,leading=8.5,textColor=colors.HexColor("#555577")),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    story.append(tbl([
        [Ps("VERIFIED GROSS MASS (VGM) DECLARATION","title")],
    ], [W],
    [("BACKGROUND",(0,0),(-1,-1),SOLAS_BLUE),
     ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(tbl([[Ps("SOLAS Regulation VI/2 — Method 1: Weighing of the Packed Container","sub")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),SOLAS_LIGHT),
         ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    story.append(Spacer(1,1*mm))

    # Shipper + Container details
    top_t = tbl([[
        [Ps("SHIPPER / PACKER","lbl"), Ps(d["shipper_name"],"bold"),
         Ps(d["shipper_address"],"sm"),
         Ps(f"Country: {d['shipper_country'][0]}","sm")],
        [Ps("CONTAINER DETAILS","lbl"),
         Ps(f"Container No:  {d['container_no']}","bold"),
         Ps(f"Seal No:       {d['seal_no']}","sm"),
         Ps(f"Size / Type:   {d['container_size']}","sm"),
         Ps(f"ISO Type Code: {d['iso_code']}","sm")],
        [Ps("SHIPMENT REFERENCE","lbl"),
         Ps(f"Booking Ref:   {d['booking_ref']}","val"),
         Ps(f"B/L Number:    {d['bl_number']}","sm"),
         Ps(f"Vessel:        {d['vessel']}","sm"),
         Ps(f"Voyage:        {d['voyage']}","sm"),
         Ps(f"POL:           {d['pol']}","sm")],
    ]], [62*mm,62*mm,62*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(top_t); story.append(Spacer(1,1*mm))

    # METHOD 1 statement
    m1_text = (
        "METHOD 1: The shipper has obtained the VGM by weighing the packed and sealed container "
        "using calibrated and certified equipment in accordance with the accuracy standards and "
        "requirements as established by the competent authority of the State in which the packing "
        "of the container was completed (SOLAS Regulation VI/2)."
    )
    story.append(tbl([[
        Ps("METHOD 1","meth"),
        Ps(m1_text,"solas"),
    ]], [18*mm,168*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,-1),SOLAS_LIGHT),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
     ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(Spacer(1,2*mm))

    # VGM weight breakdown — large display
    wt_data = [
        [Ps("WEIGHT COMPONENT","lbl"), Ps("WEIGHT (KG)","lbl"), Ps("NOTES","lbl")],
        [Ps("Tare Weight of Container","sm"),
         Ps(f"{d['tare_weight_kg']:,.1f} kg","wt"),
         Ps(f"ISO Type: {d['iso_code']} — {d['container_size']}","sm")],
        [Ps("Cargo Gross Weight","sm"),
         Ps(f"{d['cargo_weight_kg']:,.1f} kg","wt"),
         Ps("All packed goods inside container","sm")],
        [Ps("Packing Materials & Dunnage","sm"),
         Ps(f"{d['packing_materials_kg']:,.1f} kg","wt"),
         Ps("Pallets, strapping, void-fill","sm")],
        [Ps("VERIFIED GROSS MASS (VGM)","vgmlbl"),
         Ps(f"{d['vgm_kg']:,.1f} kg","vgm"),
         Ps(f"Sum of tare + cargo + packing materials","note")],
    ]
    wt_t = Table(wt_data, colWidths=[72*mm,50*mm,64*mm])
    wt_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),SOLAS_BLUE),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("BACKGROUND",(0,-1),(-1,-1),SOLAS_LIGHT),
        ("LINEABOVE",(0,-1),(-1,-1),1.5,VGM_ORANGE),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(wt_t); story.append(Spacer(1,2*mm))

    # Weighing equipment
    weigh_t = tbl([
        [Ps("WEIGHING EQUIPMENT","lbl"), Ps("SCALE SERIAL / REF","lbl"),
         Ps("CALIBRATION DATE","lbl"), Ps("ACCURACY STANDARD","lbl")],
        [Ps(d["scale_type"],"val"), Ps(d["scale_serial"],"val"),
         Ps(d["calibration_date"].strftime("%d %b %Y"),"val"),
         Ps("OIML R-76 / NTEP","val")],
    ], [50*mm,50*mm,40*mm,46*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,0),LGRAY),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),4)])
    story.append(weigh_t); story.append(Spacer(1,2*mm))

    # SOLAS Certification + Signature
    solas_stmt = (
        "I hereby certify that the Verified Gross Mass stated above has been obtained by using Method 1 "
        "(weighing of the packed and sealed container) in accordance with SOLAS Convention, Chapter VI, "
        "Regulation 2, as amended. This declaration is made as required under the SOLAS Amendments. "
        f"The signatory is duly authorized by {d['shipper_name']}."
    )
    cert_t = tbl([[
        [Ps("SOLAS CERTIFICATION","lbl"),
         Ps(solas_stmt,"note"),
         Spacer(1,1*mm),
         Ps(f"Cutoff Date/Time: {d['cutoff_date'].strftime('%d %b %Y')}","sm")],
        [Ps("AUTHORIZED SIGNATORY","lbl"),
         Spacer(1,4*mm),
         Ps(f"Name:  {d['signatory']}","sm"),
         Ps(f"Title: {d['title']}","sm"),
         Ps(f"Date:  {d['sign_date'].strftime('%d %b %Y')}","sm"),
         Spacer(1,2*mm),
         Ps("Signature: _________________________","sm")],
    ]], [100*mm,86*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(cert_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — VGM Method 2 (sum of packages + tare)
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    M2_DARK   = colors.HexColor("#2E3D49")
    M2_LIGHT  = colors.HexColor("#ECEFF1")
    M2_ACCENT = colors.HexColor("#00ACC1")
    M2_VGM    = colors.HexColor("#00695C")

    st = {
        "title":  S("t",  fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, textColor=colors.white),
        "sub":    S("su", fontName="Helvetica-Bold", fontSize=8.5,alignment=TA_CENTER, textColor=M2_DARK),
        "lbl":    S("l",  fontSize=7,  textColor=M2_DARK, fontName="Helvetica-Bold"),
        "val":    S("v",  fontSize=8.5),
        "sm":     S("sm", fontSize=7,  leading=9),
        "bold":   S("b",  fontName="Helvetica-Bold", fontSize=8.5),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=7,  alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=7,  leading=9),
        "cdr":    S("cdr",fontSize=7,  leading=9, alignment=TA_RIGHT),
        "cdc":    S("cdc",fontSize=7,  leading=9, alignment=TA_CENTER),
        "vgm":    S("vg", fontName="Helvetica-Bold", fontSize=13, alignment=TA_RIGHT, textColor=M2_VGM),
        "subtot": S("st", fontName="Helvetica-Bold", fontSize=9,  alignment=TA_RIGHT, textColor=M2_DARK),
        "meth":   S("mt", fontName="Helvetica-Bold", fontSize=8.5, textColor=M2_ACCENT),
        "note":   S("nt", fontSize=6.5,leading=8.5,textColor=colors.HexColor("#445566")),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    story.append(tbl([
        [Ps("VERIFIED GROSS MASS (VGM) — METHOD 2","title")],
    ], [W],
    [("BACKGROUND",(0,0),(-1,-1),M2_DARK),
     ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(tbl([[Ps("SOLAS Reg. VI/2 — Method 2: Sum of Individual Package Weights + Tare","sub")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),M2_LIGHT),
         ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    story.append(Spacer(1,1*mm))

    # Company + Container 2-col
    header_t = tbl([[
        [Ps("SHIPPER / PACKER","lbl"), Ps(d["shipper_name"],"bold"),
         Ps(d["shipper_address"],"sm"),
         Ps(f"Country: {d['shipper_country'][0]}","sm")],
        [Ps("CONTAINER & BOOKING","lbl"),
         Ps(f"Container No:  {d['container_no']}","bold"),
         Ps(f"Seal No:       {d['seal_no']}","sm"),
         Ps(f"Size / Type:   {d['container_size']} (ISO: {d['iso_code']})","sm"),
         Ps(f"Booking Ref:   {d['booking_ref']}","sm"),
         Ps(f"B/L:           {d['bl_number']}","sm"),
         Ps(f"Vessel/Voyage: {d['vessel']} / {d['voyage']}","sm")],
    ]], [93*mm,93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(header_t); story.append(Spacer(1,1*mm))

    # METHOD 2 statement
    m2_text = (
        "METHOD 2: The shipper has obtained the VGM by determining and documenting the weight of all packages "
        "(including dunnage, securing material and packing materials) and adding the tare mass of the container. "
        "All weighing equipment used is certified and calibrated."
    )
    story.append(tbl([[Ps("METHOD 2","meth"), Ps(m2_text,"note")]], [18*mm,168*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,-1),M2_LIGHT),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(Spacer(1,1*mm))

    # Individual package weights table
    n = len(d["packages"])
    pkg_rows = [[Ps("Item","ch"), Ps("Description","ch"), Ps("Pkg Type","ch"),
                 Ps("No. Units","ch"), Ps("Gross Weight (KG)","ch")]]
    for pkg in d["packages"]:
        pkg_rows.append([
            Ps(str(pkg["item_no"]),"cdc"),
            Ps(pkg["description"],"cd"),
            Ps(pkg["pkg_type"],"cdc"),
            Ps(str(pkg["n_units"]),"cdr"),
            Ps(f"{pkg['gross_wt_kg']:,.1f}","cdr")])
    # Sub-total packages row
    pkg_rows.append([
        Ps("SUBTOTAL","ch"),Ps("All Cargo Packages","cd"),Ps("","cdc"),
        Ps("","cdr"),Ps(f"{d['cargo_weight_kg']:,.1f}","cdr")])
    stripe_p = [("BACKGROUND",(0,r),(-1,r),M2_LIGHT) for r in range(1,n+1) if r%2==0]
    pkg_t = Table(pkg_rows, colWidths=[14*mm,82*mm,24*mm,20*mm,46*mm], repeatRows=1)
    pkg_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),M2_DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),M2_LIGHT),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe_p))
    story.append(pkg_t); story.append(Spacer(1,1*mm))

    # Calculation table — how VGM is derived
    calc_rows = [
        [Ps("VGM CALCULATION","lbl"), Ps("COMPONENT","lbl"), Ps("WEIGHT (KG)","lbl")],
        [Ps("Step 1","sm"), Ps("Sum of all cargo package weights","sm"),
         Ps(f"{d['cargo_weight_kg']:,.1f} kg","subtot")],
        [Ps("Step 2","sm"), Ps("Packing materials (pallets, strapping, dunnage, void-fill)","sm"),
         Ps(f"{d['packing_materials_kg']:,.1f} kg","subtot")],
        [Ps("Step 3","sm"), Ps(f"Container tare weight ({d['container_size']}, ISO {d['iso_code']})","sm"),
         Ps(f"{d['tare_weight_kg']:,.1f} kg","subtot")],
        [Ps("= VGM","lbl"),
         Ps("VERIFIED GROSS MASS (Step 1 + Step 2 + Step 3)","bold"),
         Ps(f"{d['vgm_kg']:,.1f} kg","vgm")],
    ]
    calc_t = Table(calc_rows, colWidths=[20*mm,106*mm,60*mm])
    calc_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),M2_LIGHT),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("LINEABOVE",(0,-1),(-1,-1),1.5,M2_VGM),("BACKGROUND",(0,-1),(-1,-1),M2_LIGHT),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(calc_t); story.append(Spacer(1,2*mm))

    # Weighing equipment + certification
    cert_t = tbl([[
        [Ps("WEIGHING EQUIPMENT","lbl"),
         Ps(f"Type: {d['scale_type']}","sm"),
         Ps(f"Serial: {d['scale_serial']}","sm"),
         Ps(f"Calibration: {d['calibration_date'].strftime('%d %b %Y')}","sm"),
         Ps("Standard: OIML R-76 / NTEP","sm")],
        [Ps("AUTHORIZED SIGNATORY","lbl"),
         Ps(f"Name:  {d['signatory']}","sm"),
         Ps(f"Title: {d['title']}","sm"),
         Ps(f"Date:  {d['sign_date'].strftime('%d %b %Y')}","sm"),
         Spacer(1,3*mm),
         Ps("Signature: _________________________","sm")],
    ]], [93*mm,93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(cert_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — Carrier/Terminal VGM Submission Form
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    TRM_GRAY   = colors.HexColor("#37474F")
    TRM_LIGHT  = colors.HexColor("#ECEFF1")
    TRM_ACCENT = colors.HexColor("#546E7A")
    TRM_GREEN  = colors.HexColor("#2E7D32")
    TRM_BOX    = colors.HexColor("#CFD8DC")

    st = {
        "title":  S("t",  fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER, textColor=colors.white),
        "sub":    S("su", fontName="Helvetica-Bold", fontSize=8,  alignment=TA_CENTER, textColor=TRM_GRAY),
        "lbl":    S("l",  fontSize=7,  textColor=TRM_GRAY, fontName="Helvetica-Bold"),
        "val":    S("v",  fontSize=9),
        "sm":     S("sm", fontSize=7,  leading=9),
        "bold":   S("b",  fontName="Helvetica-Bold", fontSize=9.5),
        "vgm":    S("vg", fontName="Helvetica-Bold", fontSize=16, alignment=TA_CENTER, textColor=TRM_GREEN),
        "vgmlbl": S("vl", fontName="Helvetica-Bold", fontSize=8,  alignment=TA_CENTER, textColor=TRM_GREEN),
        "edi":    S("ed", fontName="Helvetica", fontSize=7,  textColor=colors.HexColor("#546E7A"),
                   leading=9),
        "note":   S("nt", fontSize=6.5,leading=8.5,textColor=colors.HexColor("#546E7A")),
        "ref":    S("rf", fontName="Helvetica-Bold", fontSize=10, textColor=TRM_ACCENT),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    story.append(tbl([
        [Ps("VGM SUBMISSION FORM — CARRIER / TERMINAL","title")],
    ], [W],
    [("BACKGROUND",(0,0),(-1,-1),TRM_GRAY),
     ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(tbl([[Ps("SOLAS VGM  ·  Shipping Line Submission  ·  Terminal / Port Authority Copy","sub")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),TRM_LIGHT),
         ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    story.append(Spacer(1,1*mm))

    # VGM Reference Box — prominent
    vgm_ref_t = tbl([[
        [Ps("VGM TRANSMISSION REFERENCE","lbl"), Ps(d["vgm_ref"],"ref")],
        [Ps("EDI REFERENCE","lbl"), Ps(d["edi_ref"],"edi")],
    ], [
        [Ps("BOOKING REFERENCE","lbl"), Ps(d["booking_ref"],"ref")],
        [Ps("CUTOFF DATE","lbl"), Ps(d["cutoff_date"].strftime("%d %b %Y"),"val")],
    ],
    ], [93*mm,93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,-1),TRM_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(vgm_ref_t); story.append(Spacer(1,1*mm))

    # Container details block
    ctr_data = [
        [Ps("CONTAINER NUMBER","lbl"), Ps(d["container_no"],"bold"),
         Ps("SEAL NUMBER","lbl"), Ps(d["seal_no"],"val")],
        [Ps("CONTAINER SIZE / TYPE","lbl"), Ps(d["container_size"],"val"),
         Ps("ISO TYPE CODE","lbl"), Ps(d["iso_code"],"val")],
        [Ps("TARE WEIGHT","lbl"), Ps(f"{d['tare_weight_kg']:,.1f} kg","val"),
         Ps("MAX PAYLOAD","lbl"),
         Ps(f"{CONTAINER_SIZES.get(d['container_size'], {}).get('max_payload', 'N/A'):,} kg","val")],
    ]
    ctr_t = Table(ctr_data, colWidths=[36*mm,57*mm,36*mm,57*mm])
    ctr_t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("BACKGROUND",(0,0),(0,-1),TRM_LIGHT),("BACKGROUND",(2,0),(2,-1),TRM_LIGHT),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),4),
    ]))
    story.append(ctr_t); story.append(Spacer(1,1*mm))

    # Vessel + port + shipping line
    shipping_data = [
        [Ps("SHIPPING LINE","lbl"), Ps(d["shipping_line"],"val"),
         Ps("VESSEL","lbl"), Ps(d["vessel"],"val"),
         Ps("VOYAGE","lbl"), Ps(d["voyage"],"val")],
        [Ps("PORT OF LOADING","lbl"), Ps(d["pol"],"val"),
         Ps("PORT OF DISCHARGE","lbl"), Ps(d["pod"],"val"),
         Ps("B/L NUMBER","lbl"), Ps(d["bl_number"],"val")],
        [Ps("TERMINAL","lbl"), Ps(d["terminal"],"val"),
         Ps("VGM CUTOFF","lbl"), Ps(d["cutoff_date"].strftime("%d %b %Y"),"val"),
         Ps("METHOD","lbl"), Ps(f"Method {random.choice([1,2])}","bold")],
    ]
    ship_t = Table(shipping_data, colWidths=[28*mm,34*mm,28*mm,34*mm,20*mm,42*mm])
    ship_t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("BACKGROUND",(0,0),(0,-1),TRM_LIGHT),("BACKGROUND",(2,0),(2,-1),TRM_LIGHT),
        ("BACKGROUND",(4,0),(4,-1),TRM_LIGHT),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(ship_t); story.append(Spacer(1,2*mm))

    # VGM display — large central box
    vgm_box = tbl([
        [Ps("CARGO WEIGHT","lbl"),
         Ps(f"{d['cargo_weight_kg']:,.1f} kg","val"),
         Ps("PACKING MATERIALS","lbl"),
         Ps(f"{d['packing_materials_kg']:,.1f} kg","val")],
        [Ps("CONTAINER TARE","lbl"),
         Ps(f"{d['tare_weight_kg']:,.1f} kg","val"),
         Ps("VERIFIED GROSS MASS","vgmlbl"),
         Ps(f"{d['vgm_kg']:,.1f} kg","vgm")],
    ], [38*mm,55*mm,44*mm,49*mm],
    [("BOX",(0,0),(-1,-1),1.5,TRM_GREEN),("INNERGRID",(0,0),(-1,-1),.5,TRM_BOX),
     ("BACKGROUND",(2,1),(3,1),TRM_LIGHT),("LINEABOVE",(0,1),(-1,1),1,TRM_GREEN),
     ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
     ("LEFTPADDING",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"MIDDLE")])
    story.append(vgm_box); story.append(Spacer(1,2*mm))

    # Shipper + signature
    sig_t = tbl([[
        [Ps("SHIPPER / AUTHORIZED PARTY","lbl"),
         Ps(d["shipper_name"],"bold"),
         Ps(d["shipper_address"],"sm"),
         Spacer(1,1*mm),
         Ps(f"Weighing Equipment: {d['scale_type']}","sm"),
         Ps(f"Serial: {d['scale_serial']}  |  Calibrated: {d['calibration_date'].strftime('%d %b %Y')}","sm")],
        [Ps("AUTHORIZED SIGNATORY","lbl"),
         Ps(f"Name:  {d['signatory']}","sm"),
         Ps(f"Title: {d['title']}","sm"),
         Ps(f"Date:  {d['sign_date'].strftime('%d %b %Y')}","sm"),
         Spacer(1,3*mm),
         Ps("Signature: _________________________","sm")],
    ]], [93*mm,93*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(sig_t); story.append(Spacer(1,1*mm))

    # EDI note
    edi_note = (
        f"EDI SUBMISSION NOTE: This VGM has been / will be submitted electronically to "
        f"{d['shipping_line']} and {d['terminal']} via EDI message type VERMAS. "
        f"EDI Ref: {d['edi_ref']}  |  VGM Transmission Ref: {d['vgm_ref']}  |  "
        f"Cutoff: {d['cutoff_date'].strftime('%d %b %Y')}"
    )
    story.append(tbl([[Ps(edi_note,"edi")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),TRM_LIGHT),("LEFTPADDING",(0,0),(-1,-1),5),
         ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
         ("BOX",(0,0),(-1,-1),.5,TRM_BOX)]))
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS   = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["VGM-Method1-Full-Container-Weighing",
                "VGM-Method2-Sum-of-Packages",
                "VGM-Carrier-Terminal-Submission"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"vgm_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Fields common to all three formats
    fields = {
        "shipper_name": d["shipper_name"], "shipper_address": d["shipper_address"],
        "shipper_country": d["shipper_country"][0],
        "container_number": d["container_no"],
        "seal_number": d["seal_no"],
        "container_size": d["container_size"],
        "iso_type_code": d["iso_code"],
        "tare_weight_kg": d["tare_weight_kg"],
        "cargo_weight_kg": d["cargo_weight_kg"],
        "packing_materials_kg": d["packing_materials_kg"],
        "vgm_kg": d["vgm_kg"],
        "vessel": d["vessel"], "voyage": d["voyage"],
        "bl_number": d["bl_number"],
        "booking_reference": d["booking_ref"],
        "weighing_scale_type": d["scale_type"],
        "scale_serial": d["scale_serial"],
        "calibration_date": d["calibration_date"].strftime("%Y-%m-%d"),
        "cutoff_date": d["cutoff_date"].strftime("%Y-%m-%d"),
        "signature_date": d["sign_date"].strftime("%Y-%m-%d"),
        "signatory_name": d["signatory"],
        "signatory_title": d["title"],
    }

    if fmt_idx == 0:
        # fmt1 (Method1-Full-Container-Weighing): renders pol but not pod;
        # no packages list, no vgm_ref/edi_ref/terminal/shipping_line
        fields["port_of_loading"] = d["pol"]
        fields["number_of_packages"] = d["n_packages"]

    elif fmt_idx == 1:
        # fmt2 (Method2-Sum-of-Packages): renders individual packages list;
        # no pol/pod, no vgm_ref/edi_ref/terminal/shipping_line
        fields["number_of_packages"] = d["n_packages"]
        fields["packages"] = d["packages"]

    elif fmt_idx == 2:
        # fmt3 (Carrier-Terminal-Submission): renders vgm_ref, edi_ref,
        # terminal, shipping_line, pol, pod — no packages list
        fields["port_of_loading"] = d["pol"]
        fields["port_of_discharge"] = d["pod"]
        fields["vgm_transmission_reference"] = d["vgm_ref"]
        fields["edi_reference"] = d["edi_ref"]
        fields["terminal"] = d["terminal"]
        fields["shipping_line"] = d["shipping_line"]

    ann = {
        "document_id":    fname.replace(".pdf",""),
        "document_class": "Verified Gross Mass",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    6,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf",".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} Verified Gross Mass documents (3 format variants)...")
    for i in range(1, count+1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            print(f"  [{i:04d}] {a['format_variant'][:35]:<35} {f['container_number']}  "
                  f"VGM: {f['vgm_kg']:>8,.1f} kg")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
