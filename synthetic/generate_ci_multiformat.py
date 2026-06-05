"""
Commercial Invoice — 4 distinct real-world format variants.
Format 1: DHL Express / Freight Forwarder style
Format 2: Corporate Trade Finance style (bank details, subtotals, duty breakdown)
Format 3: Marks & Numbers / Ocean Freight style (3-party header, container details)
Format 4: Modern E-Commerce / ERP style (SKU-based, digital refs, QR placeholder)
Generates 1000 diverse documents distributed across all 4 formats.
"""
import json, random, argparse
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable, KeepTogether)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_line_items, random_invoice_number, random_vat_number,
    random_dhl_account, INCOTERMS, CURRENCIES, PAYMENT_TERMS, EXPORT_TYPES,
    PORTS_SEA, AIRPORTS, VESSEL_NAMES, COMMODITY_CATEGORIES)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "01_Commercial_Invoice"
PDF_DIR, ANN_DIR = OUT_DIR / "pdfs", OUT_DIR / "annotations"

W = 186*mm   # usable page width

# ── Shared style helpers ──────────────────────────────────────────────────
def S(n, **k):
    d = dict(fontName="Helvetica", fontSize=8, leading=10,
             textColor=colors.black, spaceAfter=0, spaceBefore=0)
    d.update(k); return ParagraphStyle(n, **d)

def P(t, s): return Paragraph(str(t), s)

def tbl(data, colWidths, style_cmds, repeat=0):
    t = Table(data, colWidths=colWidths, repeatRows=repeat)
    t.setStyle(TableStyle(style_cmds)); return t

BORDER = colors.HexColor("#555555"); LN = colors.HexColor("#CCCCCC")

# ── Synthetic data builder ────────────────────────────────────────────────
def make_data():
    sc = random_country(); rc = random_country()
    while rc[1] == sc[1]: rc = random_country()
    nc = random_country()  # notify party country

    # Add more variety: extra company fields
    sn = random_company(); sa = fake.address().replace("\n", ", ") + f", {sc[0]}"
    sp = fake.phone_number(); sv = random_vat_number(sc[1]); sfax = fake.phone_number()
    semail = fake.company_email(); sregno = fake.bothify("REG##########")

    rn = random_company(); ra = fake.address().replace("\n", ", ") + f", {rc[0]}"
    rp = fake.phone_number(); rv = random_vat_number(rc[1]); racct = random_dhl_account()

    nn = random_company(); na = fake.address().replace("\n", ", ") + f", {nc[0]}"

    inv_date = fake.date_between(start_date="-2y", end_date="today")
    due_date = fake.date_between(start_date=inv_date, end_date="+90d")
    inv_no   = random_invoice_number()
    po_no    = f"PO-{random.randint(10000,99999)}"
    ref      = f"REF-{random.randint(100000,999999)}"
    awb_no   = f"{random.randint(100,999)}-{random.randint(10000000,99999999)}"
    bkg_ref  = f"BKG-{random.randint(100000,999999)}"

    cur = random.choice(CURRENCIES); inc = random.choice(INCOTERMS)
    pay = random.choice(PAYMENT_TERMS); exp = random.choice(EXPORT_TYPES)
    gst = random.choice(["Shipper","Receiver","Third Party"])
    b3p = random.choice(["Yes","No","No","No"])
    cmt = random.choice(["","","Fragile - handle with care",
                          f"PO# {random.randint(10000,99999)}",
                          "Sample - No commercial value",
                          "Diplomatic shipment",
                          f"Letter of Credit No: LC-{random.randint(100000,999999)}"])

    # More line items for complexity
    n_items = random.randint(2, 10)
    items = random_line_items(n_items)

    # Add part numbers, duty rates, ECCNs for richer data
    eccn_codes = ["EAR99","5E992","3A992","7A994","9A515","2B350"]
    duty_rates  = [0.0, 0.0, 2.5, 3.7, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0]
    for it in items:
        it["part_no"]    = f"PN-{random.randint(10000,99999)}"
        it["eccn"]       = random.choice(eccn_codes)
        it["duty_rate"]  = random.choice(duty_rates)
        it["duty_amount"] = round(it["total_value"] * it["duty_rate"] / 100, 2)
        it["marks"]      = f"{random.choice(['ABC','XYZ','GLB'])}/{random.randint(1,50)}"
        it["n_packages"] = random.randint(1,20)
        it["pkg_type"]   = random.choice(["CTN","PLT","DRM","CAS"])

    tv   = round(sum(i["total_value"]     for i in items), 2)
    tn   = round(sum(i["total_weight_kg"] for i in items), 2)
    tg   = round(tn * random.uniform(1.05, 1.25), 2)
    tp   = sum(i["n_packages"] for i in items)
    td   = round(sum(i["duty_amount"] for i in items), 2)

    # Freight and insurance for financial formats
    freight_val  = round(random.uniform(50, 2000), 2)
    ins_val      = round(tv * random.uniform(0.001, 0.005), 2)
    total_inv    = round(tv + freight_val + ins_val, 2)

    # Bank details for trade finance format
    bank_name    = random.choice(["HSBC","Citibank","Deutsche Bank","BNP Paribas",
                                   "Standard Chartered","Bank of America","Barclays"])
    bank_account = fake.bothify("######-####-######")
    bank_swift   = fake.bothify("????US##")
    bank_iban    = fake.bothify("US##????######################")

    mode = random.choice(["Air Freight","Ocean Freight","Road Freight","Express Courier"])
    pol  = random.choice(PORTS_SEA) if "Ocean" in mode else random.choice(AIRPORTS)[0]
    pod  = random.choice(PORTS_SEA) if "Ocean" in mode else random.choice(AIRPORTS)[0]
    while pod == pol: pod = random.choice(PORTS_SEA if "Ocean" in mode else AIRPORTS)[0 if "Ocean" in mode else 0]

    sig_name = fake.name()
    sig_pos  = random.choice(["Export Manager","Trade Compliance Officer","Finance Director",
                               "Logistics Manager","Operations Director","CFO"])
    consultant = fake.name()

    return dict(
        sc=sc, rc=rc, nc=nc,
        sn=sn, sa=sa, sp=sp, sv=sv, sfax=sfax, semail=semail, sregno=sregno,
        rn=rn, ra=ra, rp=rp, rv=rv, racct=racct,
        nn=nn, na=na,
        inv_date=inv_date, due_date=due_date, inv_no=inv_no, po_no=po_no,
        ref=ref, awb_no=awb_no, bkg_ref=bkg_ref,
        cur=cur, inc=inc, pay=pay, exp=exp, gst=gst, b3p=b3p, cmt=cmt,
        items=items, tv=tv, tn=tn, tg=tg, tp=tp, td=td,
        freight_val=freight_val, ins_val=ins_val, total_inv=total_inv,
        bank_name=bank_name, bank_account=bank_account,
        bank_swift=bank_swift, bank_iban=bank_iban,
        mode=mode, pol=pol, pod=pod,
        sig_name=sig_name, sig_pos=sig_pos, consultant=consultant,
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — DHL Express / Freight Forwarder style
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    TITLE_BG = colors.HexColor("#D40511"); HDR_BG = colors.HexColor("#EEEEEE")
    LW, RW = 88*mm, 98*mm
    st = {
        "title": S("t", fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER, textColor=colors.white),
        "lbl":   S("l", fontSize=7, textColor=colors.HexColor("#555555")),
        "val":   S("v", fontName="Helvetica-Bold", fontSize=8),
        "sm":    S("sm", fontSize=7, leading=9),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=7, alignment=TA_CENTER),
        "cd":    S("cd", fontSize=7, leading=9),
        "cdr":   S("cdr", fontSize=7, leading=9, alignment=TA_RIGHT),
        "cdc":   S("cdc", fontSize=7, leading=9, alignment=TA_CENTER),
        "tlbl":  S("tl", fontName="Helvetica-Bold", fontSize=7.5),
        "glbl":  S("gl", fontSize=8),
        "gval":  S("gv", fontName="Helvetica-Bold", fontSize=8.5),
    }
    def Ps(t, s): return P(t, st[s])
    def lv(l, v): return [Ps(l,"lbl"), Ps(v,"val")]
    def addr_blk(hdr, name, addr, phone, vat):
        return [Ps(hdr,"lbl"),Ps(name,"val"),Ps(addr,"sm"),Spacer(1,1*mm),
                Ps(f"Phone: {phone}","sm"), Ps(f"VAT/GST No: {vat}","sm")]

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    # Banner
    story.append(tbl([[Ps("COMMERCIAL INVOICE","title")]], [W],
        [("BACKGROUND",(0,0),(-1,-1),TITLE_BG),("TOPPADDING",(0,0),(-1,-1),5),
         ("BOTTOMPADDING",(0,0),(-1,-1),5),("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(Spacer(1,1*mm))

    # Header: shipper | title bg | receiver | date fields
    hdr_data = [
        [addr_blk("SHIPPER / EXPORTER", d["sn"], d["sa"], d["sp"], d["sv"]),
         [Spacer(1,4*mm), Ps("Commercial Invoice","title"), Spacer(1,4*mm)]],
        ["",""],["",""],
        [addr_blk("RECEIVER / CONSIGNEE", d["rn"], d["ra"], d["rp"], d["rv"]),
         lv("Date:", d["inv_date"].strftime("%d %b %Y"))],
        ["", lv("Invoice Number:", d["inv_no"])],
        ["", lv("Shipment Reference:", d["ref"])],
        [[Ps("Bill to Third Party:", "lbl"), Ps(d["b3p"],"val")],
         [Ps("Comments:", "lbl"), Ps(d["cmt"],"sm")]],
        [lv("Airway Bill Number:", d["awb_no"]), ""],
    ]
    ht = Table(hdr_data, colWidths=[LW, RW], rowHeights=[None]*8)
    ht.setStyle(TableStyle([
        ("SPAN",(0,0),(0,2)),("SPAN",(1,0),(1,2)),
        ("SPAN",(0,3),(0,5)),
        ("SPAN",(0,6),(1,6)),("SPAN",(0,7),(1,7)),
        ("BACKGROUND",(1,0),(1,2),colors.HexColor("#D0D0D0")),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP"),
        ("VALIGN",(1,0),(1,2),"MIDDLE"),
    ]))
    story.append(ht); story.append(Spacer(1,1*mm))

    # Items table — 10 columns
    CW = [8*mm,50*mm,10*mm,10*mm,20*mm,17*mm,17*mm,17*mm,17*mm,20*mm]
    rows = [[Ps("No.","ch"),Ps("Full Description of Goods","ch"),Ps("Qty.","ch"),
             Ps("UOM","ch"),Ps("Commodity\nCode","ch"),Ps(f"Unit Value\n({d['cur']})","ch"),
             Ps("Subtotal\nValue","ch"),Ps("Unit Net\nWeight","ch"),
             Ps("Subtotal\nWeight","ch"),Ps("Country of\nOrigin","ch")]]
    for i,it in enumerate(d["items"],1):
        rows.append([Ps(i,"cdc"),Ps(it["description"],"cd"),Ps(it["qty"],"cdr"),
                     Ps(it["unit"],"cdc"),Ps(it["hs_code"],"cdc"),
                     Ps(f"{it['unit_value']:,.2f}","cdr"),Ps(f"{it['total_value']:,.2f}","cdr"),
                     Ps(f"{it['unit_weight_kg']:.3f}","cdr"),Ps(f"{it['total_weight_kg']:.2f}","cdr"),
                     Ps(it["country_of_origin"],"cd")])
    for _ in range(max(0,5-len(d["items"]))): rows.append([Ps("","cd")]*10)
    n_data = len(d["items"]) + max(0,5-len(d["items"])); tr1=n_data+1; tr2=tr1+1
    rows.append([Ps(f"Total Declared Value:   {d['cur']} {d['tv']:,.2f}","tlbl"),
                 "","","","","",Ps(f"Total Net Weight:   {d['tn']:,.3f} KG","tlbl"),"","",""])
    rows.append([Ps(f"Total Pieces:   {d['tp']}","tlbl"),
                 "","","","","",Ps(f"Total Gross Weight:   {d['tg']:,.3f} KG","tlbl"),"","",""])
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    its  = TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("SPAN",(0,tr1),(5,tr1)),("SPAN",(6,tr1),(9,tr1)),
        ("SPAN",(0,tr2),(5,tr2)),("SPAN",(6,tr2),(9,tr2)),
        ("BACKGROUND",(0,tr1),(-1,tr2),colors.HexColor("#F5F5F5")),
    ])
    for r in range(1,len(d["items"])+1):
        if r%2==0: its.add("BACKGROUND",(0,r),(-1,r),colors.HexColor("#FAFAFA"))
    it_t.setStyle(its)
    story.append(it_t); story.append(Spacer(1,2*mm))

    # GST row
    gst_t = tbl([[Ps("Payer of GST/VAT:","glbl"),Ps(d["gst"],"gval"),
                  Ps("Currency Code:","glbl"),Ps(d["cur"],"gval")],
                 [Ps("Type of Export:","glbl"),Ps(d["exp"],"gval"),
                  Ps("Incoterm:","glbl"),Ps(d["inc"],"gval")],
                 [Ps("Terms of Payment:","glbl"),Ps(d["pay"],"gval"),Ps("","glbl"),Ps("","gval")]],
                [36*mm,46*mm,30*mm,74*mm],
                [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
                 ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
                 ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"MIDDLE")])
    story.append(gst_t); story.append(Spacer(1,2*mm))

    # Signature
    decl = ("I/We hereby certify that the information of this invoice is true and correct "
            "and that the contents of this shipment are as stated above.")
    sig_t = tbl([[Ps(decl,"sm"),Ps("","sm")],[Spacer(1,6*mm),Spacer(1,6*mm)],
                 [Ps("Signature: ___________________________","sm"),Ps("Company Stamp:","sm")],
                 [Ps(f"Position in Company:  {d['sig_pos']}","sm"),Ps("","sm")],
                 [Ps(f"Shipping Consultant:  {d['consultant']}","sm"),Ps(d["sn"],"sm")]],
                [W*0.55, W*0.45],
                [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
                 ("SPAN",(0,0),(-1,0)),("TOPPADDING",(0,0),(-1,-1),3),
                 ("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),5)])
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — Corporate Trade Finance style (bank details, duty breakdown)
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    CORP_BG = colors.HexColor("#003366"); CORP_LIGHT = colors.HexColor("#E6EEF7")
    st = {
        "co_name": S("cn", fontName="Helvetica-Bold", fontSize=14, textColor=colors.HexColor("#003366")),
        "co_addr": S("ca", fontSize=7.5, textColor=colors.HexColor("#444444")),
        "invoice": S("inv", fontName="Helvetica-Bold", fontSize=16, alignment=TA_RIGHT, textColor=colors.HexColor("#003366")),
        "inv_no":  S("ino", fontSize=9, alignment=TA_RIGHT, textColor=colors.HexColor("#555555")),
        "sec_hdr": S("sh", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white),
        "lbl":     S("l", fontSize=7.5, textColor=colors.HexColor("#666666")),
        "val":     S("v", fontName="Helvetica-Bold", fontSize=8.5),
        "sm":      S("sm", fontSize=7.5, leading=10),
        "ch":      S("ch", fontName="Helvetica-Bold", fontSize=7.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":      S("cd", fontSize=7.5, leading=9),
        "cdr":     S("cdr", fontSize=7.5, leading=9, alignment=TA_RIGHT),
        "cdc":     S("cdc", fontSize=7.5, leading=9, alignment=TA_CENTER),
        "total":   S("tot", fontName="Helvetica-Bold", fontSize=9, alignment=TA_RIGHT),
        "grand":   S("grd", fontName="Helvetica-Bold", fontSize=11, alignment=TA_RIGHT, textColor=colors.HexColor("#003366")),
        "foot":    S("ft", fontSize=7, textColor=colors.HexColor("#777777")),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    W2 = 180*mm
    story = []

    # Company letterhead
    lh = tbl([[Ps(d["sn"],"co_name"), Ps("COMMERCIAL INVOICE","invoice")],
              [Ps(f"{d['sa']}\nTel: {d['sp']}  |  Email: {d['semail']}","co_addr"),
               Ps(f"Invoice No: {d['inv_no']}\nDate: {d['inv_date'].strftime('%d %B %Y')}\nDue Date: {d['due_date'].strftime('%d %B %Y')}","inv_no")]],
             [110*mm, 70*mm],
             [("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),0),
              ("BOTTOMPADDING",(0,0),(-1,-1),4)])
    story.append(lh)
    story.append(HRFlowable(width=W2, thickness=2, color=CORP_BG))
    story.append(Spacer(1,4*mm))

    # Bill to / Ship to / Reference block
    ref_block = tbl([
        [Ps("BILL TO","sec_hdr"), Ps("SHIP TO","sec_hdr"),
         Ps("SHIPMENT REFERENCE","sec_hdr")],
        [[Ps(d["rn"],"val"),Ps(d["ra"],"sm"),Ps(f"Tel: {d['rp']}","sm"),Ps(f"VAT: {d['rv']}","sm")],
         [Ps(d["rn"],"val"),Ps(d["ra"],"sm")],
         [Ps(f"PO Number:","lbl"),Ps(d["po_no"],"val"),Spacer(1,1*mm),
          Ps(f"AWB / B/L No:","lbl"),Ps(d["awb_no"],"val"),Spacer(1,1*mm),
          Ps(f"Mode of Transport:","lbl"),Ps(d["mode"],"val"),Spacer(1,1*mm),
          Ps(f"Incoterms:","lbl"),Ps(f"{d['inc']} {d['pol']}","val")]]
    ], [65*mm, 65*mm, 50*mm],
    [("BACKGROUND",(0,0),(-1,0),CORP_BG),("TEXTCOLOR",(0,0),(-1,0),colors.white),
     ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
     ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(ref_block); story.append(Spacer(1,3*mm))

    # Detailed items table — 11 columns including Part No and Duty
    CW2 = [6*mm,16*mm,38*mm,18*mm,12*mm,10*mm,10*mm,18*mm,18*mm,18*mm,16*mm]
    hdrs = [[Ps("No.","ch"),Ps("Part No.","ch"),Ps("Description of Goods","ch"),
             Ps("HS Code","ch"),Ps("Country\nOrigin","ch"),Ps("Qty","ch"),Ps("UOM","ch"),
             Ps(f"Unit Price\n{d['cur']}","ch"),Ps(f"Total Value\n{d['cur']}","ch"),
             Ps("Wt (KG)","ch"),Ps("Duty Rate","ch")]]
    rows2 = hdrs
    for i,it in enumerate(d["items"],1):
        rows2.append([
            Ps(i,"cdc"),Ps(it["part_no"],"cdc"),
            Ps(f"{it['description']}\n[ECCN: {it['eccn']}]","cd"),
            Ps(it["hs_code"],"cdc"),Ps(it["country_of_origin"][:12],"cdc"),
            Ps(it["qty"],"cdr"),Ps(it["unit"],"cdc"),
            Ps(f"{it['unit_value']:,.2f}","cdr"),Ps(f"{it['total_value']:,.2f}","cdr"),
            Ps(f"{it['total_weight_kg']:.2f}","cdr"),
            Ps(f"{it['duty_rate']:.1f}%","cdc")])
    stripe2 = [("BACKGROUND",(0,r),(-1,r),CORP_LIGHT) for r in range(1,len(d["items"])+1) if r%2==0]
    it2 = Table(rows2, colWidths=CW2, repeatRows=1)
    it2.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),CORP_BG),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe2))
    story.append(it2); story.append(Spacer(1,2*mm))

    # Financial summary: Goods / Freight / Insurance / Duty / TOTAL
    fin = tbl([
        [Ps("","sm"),Ps("","sm"),Ps(f"Goods Value:","lbl"),Ps(f"{d['cur']} {d['tv']:,.2f}","total")],
        [Ps("","sm"),Ps("","sm"),Ps(f"Freight Charges:","lbl"),Ps(f"{d['cur']} {d['freight_val']:,.2f}","total")],
        [Ps("","sm"),Ps("","sm"),Ps(f"Insurance:","lbl"),Ps(f"{d['cur']} {d['ins_val']:,.2f}","total")],
        [Ps("","sm"),Ps("","sm"),Ps(f"Estimated Duties:","lbl"),Ps(f"{d['cur']} {d['td']:,.2f}","total")],
        [Ps("Total Net Weight:","lbl"),Ps(f"{d['tn']:,.2f} KG","val"),
         Ps("TOTAL INVOICE VALUE:","lbl"),Ps(f"{d['cur']} {d['total_inv']:,.2f}","grand")],
    ], [50*mm,40*mm,50*mm,40*mm],
    [("BOX",(2,0),(3,-1),.8,CORP_BG),("INNERGRID",(2,0),(3,-1),.3,LN),
     ("BACKGROUND",(2,-1),(3,-1),CORP_LIGHT),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),4)])
    story.append(fin); story.append(Spacer(1,3*mm))

    # Banking details
    bank_t = tbl([
        [Ps("BANKING DETAILS FOR PAYMENT","sec_hdr"),"",""],
        [Ps("Bank Name:","lbl"),Ps(d["bank_name"],"val"),Ps("SWIFT/BIC:","lbl")],
        [Ps("Account Number:","lbl"),Ps(d["bank_account"],"val"),Ps(d["bank_swift"],"val")],
        [Ps("IBAN:","lbl"),Ps(d["bank_iban"],"val"),Ps("","sm")],
        [Ps("Currency:","lbl"),Ps(d["cur"],"val"),Ps(f"Payment Terms: {d['pay']}","sm")],
    ], [40*mm,80*mm,60*mm],
    [("SPAN",(0,0),(-1,0)),("BACKGROUND",(0,0),(-1,0),CORP_BG),
     ("TEXTCOLOR",(0,0),(-1,0),colors.white),
     ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(bank_t); story.append(Spacer(1,3*mm))

    # Declaration + signature
    decl_t = tbl([[
        Ps("DECLARATION: I/We hereby certify that the information on this invoice is true and correct, "
           f"that all goods were produced in {d['sc'][0]}, and that this invoice complies with applicable "
           "trade regulations. Authorized signatory below.","sm"),
        [Ps("Signature: ___________________________","sm"),
         Ps(f"Name: {d['sig_name']}","sm"),
         Ps(f"Title: {d['sig_pos']}","sm"),
         Ps(f"Date: {d['inv_date'].strftime('%d %B %Y')}","sm")]
    ]], [110*mm, 70*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(decl_t)
    story.append(Spacer(1,2*mm))
    story.append(P(f"Page 1 of 1  |  {d['sn']}  |  {d['inv_no']}  |  Generated: {d['inv_date'].strftime('%d %b %Y')}",
                   st["foot"]))
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — Marks & Numbers / Ocean Freight style (3-party, complex table)
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    BG_DARK = colors.HexColor("#2C3E50"); BG_STRIPE = colors.HexColor("#F2F3F4")
    st = {
        "title": S("t", fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER, textColor=colors.white),
        "co":    S("co", fontName="Helvetica-Bold", fontSize=10, textColor=colors.HexColor("#2C3E50")),
        "lbl":   S("l", fontSize=7, textColor=colors.HexColor("#666666"), fontName="Helvetica-Bold"),
        "val":   S("v", fontSize=8),
        "sm":    S("sm", fontSize=7, leading=9),
        "ch":    S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":    S("cd", fontSize=7, leading=8.5),
        "cdr":   S("cdr", fontSize=7, leading=8.5, alignment=TA_RIGHT),
        "cdc":   S("cdc", fontSize=7, leading=8.5, alignment=TA_CENTER),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    # Title bar
    story.append(tbl([[Ps("COMMERCIAL INVOICE","title")]],[W],
        [("BACKGROUND",(0,0),(-1,-1),BG_DARK),
         ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
         ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(Spacer(1,2*mm))

    # 3-party header (shipper | consignee | notify)
    h3 = tbl([[
        [Ps("SHIPPER / EXPORTER","lbl"),Ps(d["sn"],"val"),Ps(d["sa"],"sm"),
         Ps(f"Tel: {d['sp']} | Fax: {d['sfax']}","sm"),Ps(f"VAT: {d['sv']}","sm"),Ps(f"Reg: {d['sregno']}","sm")],
        [Ps("CONSIGNEE","lbl"),Ps(d["rn"],"val"),Ps(d["ra"],"sm"),
         Ps(f"Tel: {d['rp']}","sm"),Ps(f"VAT: {d['rv']}","sm"),
         Ps(f"DHL Acct: {d['racct']}","sm")],
        [Ps("NOTIFY PARTY","lbl"),Ps(d["nn"],"val"),Ps(d["na"],"sm")],
    ]], [62*mm,62*mm,62*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(h3); story.append(Spacer(1,1*mm))

    # Shipment reference block
    ref_data = [
        [Ps("INVOICE NUMBER","lbl"),Ps(d["inv_no"],"val"),
         Ps("INVOICE DATE","lbl"),Ps(d["inv_date"].strftime("%d %b %Y"),"val"),
         Ps("BOOKING REF","lbl"),Ps(d["bkg_ref"],"val")],
        [Ps("AWB / B-L NUMBER","lbl"),Ps(d["awb_no"],"val"),
         Ps("PORT OF LOADING","lbl"),Ps(d["pol"],"val"),
         Ps("PORT OF DISCHARGE","lbl"),Ps(d["pod"],"val")],
        [Ps("MODE OF TRANSPORT","lbl"),Ps(d["mode"],"val"),
         Ps("INCOTERMS","lbl"),Ps(f"{d['inc']}","val"),
         Ps("BILL TO 3RD PARTY","lbl"),Ps(d["b3p"],"val")],
    ]
    ref_t = Table(ref_data, colWidths=[30*mm,32*mm,30*mm,32*mm,30*mm,32*mm])
    ref_t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("BACKGROUND",(0,0),(0,-1),BG_STRIPE),("BACKGROUND",(2,0),(2,-1),BG_STRIPE),
        ("BACKGROUND",(4,0),(4,-1),BG_STRIPE),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(ref_t); story.append(Spacer(1,1*mm))

    # Complex items table — marks & numbers + packages + 9 data cols
    CW3 = [16*mm,10*mm,10*mm,44*mm,18*mm,12*mm,10*mm,18*mm,18*mm,18*mm,12*mm]
    hdrs3 = [[Ps("Marks &\nNumbers","ch"),Ps("No.\nPkgs","ch"),Ps("Pkg\nType","ch"),
              Ps("Description of Goods & HS Code","ch"),Ps("Country\nof Origin","ch"),
              Ps("Qty","ch"),Ps("UOM","ch"),
              Ps(f"Unit Value\n({d['cur']})","ch"),Ps(f"Total Value\n({d['cur']})","ch"),
              Ps("Net Wt\n(KG)","ch"),Ps("Gross Wt\n(KG)","ch")]]
    rows3 = hdrs3
    for it in d["items"]:
        rows3.append([
            Ps(it["marks"],"cdc"),Ps(it["n_packages"],"cdr"),Ps(it["pkg_type"],"cdc"),
            Ps(f"{it['description']}\nHS: {it['hs_code']}","cd"),
            Ps(it["country_of_origin"][:14],"cdc"),
            Ps(it["qty"],"cdr"),Ps(it["unit"],"cdc"),
            Ps(f"{it['unit_value']:,.2f}","cdr"),Ps(f"{it['total_value']:,.2f}","cdr"),
            Ps(f"{it['total_weight_kg']:.2f}","cdr"),
            Ps(f"{round(it['total_weight_kg']*1.08,2):.2f}","cdr")])
    # Summary row
    rows3.append([
        Ps("TOTAL","ch"),Ps(d["tp"],"cdr"),Ps("","cdc"),Ps("","cd"),Ps("","cdc"),
        Ps("","cdr"),Ps("","cdc"),
        Ps("","cdr"),Ps(f"{d['cur']} {d['tv']:,.2f}","cdr"),
        Ps(f"{d['tn']:,.2f}","cdr"),Ps(f"{d['tg']:,.2f}","cdr")])
    stripe3 = [("BACKGROUND",(0,r),(-1,r),BG_STRIPE) for r in range(1,len(d["items"])+1) if r%2==0]
    it3 = Table(rows3, colWidths=CW3, repeatRows=1)
    it3.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),BG_DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),BG_STRIPE),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"TOP"),
    ] + stripe3))
    story.append(it3); story.append(Spacer(1,2*mm))

    # Terms + declaration
    td2 = tbl([[
        [Ps("TERMS & CONDITIONS","lbl"),
         Ps(f"Currency: {d['cur']}","sm"),Ps(f"Payment: {d['pay']}","sm"),
         Ps(f"Export Type: {d['exp']}","sm"),Ps(f"GST/VAT Payer: {d['gst']}","sm")],
        [Ps("DECLARATION","lbl"),
         Ps("We declare that the goods described herein are of the origin stated and "
            "that the particulars given are true, complete and correct.","sm"),
         Spacer(1,3*mm),
         Ps(f"Signed: {d['sig_name']} ({d['sig_pos']})","sm"),
         Ps(f"Date: {d['inv_date'].strftime('%d %b %Y')}","sm")],
    ]], [90*mm,96*mm],
    [("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
     ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")])
    story.append(td2)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 4 — Modern E-Commerce / ERP / Digital style
# ═══════════════════════════════════════════════════════════════════════════
def fmt4(doc_id, d, path):
    ACC = colors.HexColor("#FF6B35"); ACC2 = colors.HexColor("#FFF0E8"); GRAY = colors.HexColor("#F8F9FA")
    DRK = colors.HexColor("#2D3436")
    st = {
        "brand": S("br", fontName="Helvetica-Bold", fontSize=18, textColor=DRK),
        "tagline": S("tg", fontSize=8, textColor=colors.HexColor("#636E72")),
        "h1":   S("h1", fontName="Helvetica-Bold", fontSize=11, textColor=ACC),
        "h2":   S("h2", fontName="Helvetica-Bold", fontSize=9, textColor=DRK),
        "lbl":  S("l", fontSize=7.5, textColor=colors.HexColor("#636E72")),
        "val":  S("v", fontName="Helvetica-Bold", fontSize=8.5, textColor=DRK),
        "sm":   S("sm", fontSize=7.5, leading=10, textColor=DRK),
        "ch":   S("ch", fontName="Helvetica-Bold", fontSize=7.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":   S("cd", fontSize=7.5, leading=9),
        "cdr":  S("cdr", fontSize=7.5, leading=9, alignment=TA_RIGHT),
        "cdc":  S("cdc", fontSize=7.5, leading=9, alignment=TA_CENTER),
        "disc": S("dc", fontSize=8, textColor=colors.HexColor("#E17055")),
        "subtot": S("st", fontName="Helvetica-Bold", fontSize=9.5, alignment=TA_RIGHT, textColor=DRK),
        "grand": S("gr", fontName="Helvetica-Bold", fontSize=12, alignment=TA_RIGHT, textColor=ACC),
        "meta": S("mt", fontSize=7, textColor=colors.HexColor("#B2BEC3")),
    }
    def Ps(t, s): return P(t, st[s])
    doc_id_str = f"INV-{d['inv_no']}"
    qr_text = f"REF:{d['inv_no']}|DATE:{d['inv_date'].strftime('%Y%m%d')}|AMT:{d['cur']}{d['tv']}"

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    W4 = 180*mm
    story = []

    # Header with brand + QR placeholder
    hdr4 = tbl([[
        [Ps(d["sn"],"brand"), Ps("Global Trade & Logistics","tagline"),
         Spacer(1,2*mm),Ps(f"Reg: {d['sregno']}  |  VAT: {d['sv']}","sm"),
         Ps(f"{d['sa']}","sm")],
        [Ps("INVOICE","h1"), Spacer(1,2*mm),
         Ps(f"# {d['inv_no']}","val"),
         Ps(f"Date: {d['inv_date'].strftime('%d %b %Y')}","sm"),
         Ps(f"Due: {d['due_date'].strftime('%d %b %Y')}","disc"),
         Spacer(1,3*mm),
         tbl([[Ps(f" {qr_text[:30]}...","meta")]],[50*mm],
             [("BOX",(0,0),(-1,-1),1,DRK),("TOPPADDING",(0,0),(-1,-1),4),
              ("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),3)])]
    ]], [105*mm, 75*mm],
    [("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),0),
     ("BOTTOMPADDING",(0,0),(-1,-1),4)])
    story.append(hdr4)
    story.append(HRFlowable(width=W4, thickness=2, color=ACC))
    story.append(Spacer(1,4*mm))

    # From / To card
    ft = tbl([[
        [Ps("FROM","lbl"), Ps(d["sn"],"h2"), Ps(d["sa"],"sm"),
         Ps(f"Email: {d['semail']}","sm"), Ps(f"Tel: {d['sp']}","sm")],
        [Ps("TO","lbl"), Ps(d["rn"],"h2"), Ps(d["ra"],"sm"),
         Ps(f"Account: {d['racct']}","sm"), Ps(f"VAT: {d['rv']}","sm")],
        [Ps("SHIPMENT","lbl"),
         Ps(f"Mode: {d['mode']}","sm"),Ps(f"Origin: {d['pol']}","sm"),
         Ps(f"Dest: {d['pod']}","sm"),Ps(f"Incoterms: {d['inc']}","sm"),
         Ps(f"Export Type: {d['exp']}","sm")],
    ]], [62*mm,62*mm,56*mm],
    [("BOX",(0,0),(-1,-1),0,colors.white),("INNERGRID",(0,0),(-1,-1),.3,LN),
     ("BACKGROUND",(0,0),(-1,-1),GRAY),
     ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
     ("LEFTPADDING",(0,0),(-1,-1),6),("VALIGN",(0,0),(-1,-1),"TOP"),
     ("BOX",(0,0),(-1,-1),.5,colors.HexColor("#DEE2E6"))])
    story.append(ft); story.append(Spacer(1,4*mm))

    # SKU-based items table
    story.append(Ps("LINE ITEMS","h2")); story.append(Spacer(1,1*mm))
    CW4 = [14*mm,16*mm,46*mm,20*mm,14*mm,12*mm,20*mm,22*mm,16*mm]
    hdrs4 = [[Ps("#","ch"),Ps("SKU / Part","ch"),Ps("Product Description","ch"),
              Ps("HS Code","ch"),Ps("Origin","ch"),Ps("Qty","ch"),Ps("Unit","ch"),
              Ps(f"Price ({d['cur']})","ch"),Ps(f"Total ({d['cur']})","ch")]]
    rows4 = hdrs4
    for i,it in enumerate(d["items"],1):
        rows4.append([
            Ps(i,"cdc"),Ps(it["part_no"],"cdc"),
            Ps(it["description"],"cd"),Ps(it["hs_code"],"cdc"),
            Ps(it["country_of_origin"][:8],"cdc"),Ps(it["qty"],"cdr"),
            Ps(it["unit"],"cdc"),Ps(f"{it['unit_value']:,.2f}","cdr"),
            Ps(f"{it['total_value']:,.2f}","cdr")])
    stripe4 = [("BACKGROUND",(0,r),(-1,r),ACC2) for r in range(1,len(d["items"])+1) if r%2==0]
    it4 = Table(rows4, colWidths=CW4, repeatRows=1)
    it4.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),DRK),
        ("BOX",(0,0),(-1,-1),.5,colors.HexColor("#DEE2E6")),
        ("INNERGRID",(0,0),(-1,-1),.3,colors.HexColor("#DEE2E6")),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ] + stripe4))
    story.append(it4); story.append(Spacer(1,3*mm))

    # Summary totals on right
    summ = tbl([
        [Ps("","sm"),Ps("Subtotal:","lbl"),Ps(f"{d['cur']} {d['tv']:,.2f}","subtot")],
        [Ps("","sm"),Ps(f"Freight ({d['mode']}):","lbl"),Ps(f"{d['cur']} {d['freight_val']:,.2f}","subtot")],
        [Ps("","sm"),Ps("Insurance:","lbl"),Ps(f"{d['cur']} {d['ins_val']:,.2f}","subtot")],
        [Ps("","sm"),Ps("Est. Duties:","lbl"),Ps(f"{d['cur']} {d['td']:,.2f}","subtot")],
        [Ps("","sm"),Ps("TOTAL DUE:","h2"),Ps(f"{d['cur']} {d['total_inv']:,.2f}","grand")],
        [Ps("","sm"),Ps(f"Payment Terms: {d['pay']}","lbl"),
         Ps(f"Due: {d['due_date'].strftime('%d %b %Y')}","disc")],
    ], [70*mm,55*mm,55*mm],
    [("BOX",(1,0),(2,-1),.5,colors.HexColor("#DEE2E6")),
     ("BACKGROUND",(1,-2),(2,-2),GRAY),("BACKGROUND",(1,-1),(2,-1),colors.white),
     ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
     ("LEFTPADDING",(1,0),(2,-1),5)])
    story.append(summ); story.append(Spacer(1,3*mm))

    # Footer declaration
    story.append(HRFlowable(width=W4, thickness=.5, color=colors.HexColor("#DEE2E6")))
    story.append(Spacer(1,2*mm))
    foot_t = tbl([[
        Ps("DECLARATION: All goods are correctly described. This invoice is true and accurate. "
           f"Exporter: {d['sn']} | Authorized by: {d['sig_name']}, {d['sig_pos']}","sm"),
        Ps(f"Invoice: {d['inv_no']}\nDate: {d['inv_date'].strftime('%d %b %Y')}\nPage 1/1","meta")
    ]], [130*mm,50*mm],
    [("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),0)])
    story.append(foot_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS = [fmt1, fmt2, fmt3, fmt4]
FORMAT_NAMES = ["DHL-Express-Style","Corporate-Trade-Finance",
                "Marks-Numbers-Ocean-Freight","Modern-ECommerce-ERP"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 4   # rotate through all 4 formats evenly
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"commercial_invoice_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Base fields present in all formats
    fields = {
        "shipper_name": d["sn"], "shipper_address": d["sa"],
        "shipper_phone": d["sp"], "shipper_vat": d["sv"],
        "shipper_country": d["sc"][0],
        "receiver_name": d["rn"], "receiver_address": d["ra"],
        "receiver_phone": d["rp"], "receiver_vat": d["rv"],
        "receiver_country": d["rc"][0],
        "invoice_date": d["inv_date"].strftime("%Y-%m-%d"),
        "invoice_number": d["inv_no"],
        "airway_bill_number": d["awb_no"],
        "currency": d["cur"], "incoterm": d["inc"],
        "payment_terms": d["pay"], "export_type": d["exp"],
        "mode_of_transport": d["mode"],
        "port_of_loading": d["pol"], "port_of_discharge": d["pod"],
        "total_declared_value": d["tv"], "total_net_weight_kg": d["tn"],
        "total_gross_weight_kg": d["tg"], "total_pieces": d["tp"],
        "signatory_position": d["sig_pos"],
        "line_items": d["items"],
    }

    if fmt_idx == 0:  # fmt1 — DHL Express style
        fields["shipment_reference"] = d["ref"]
        fields["bill_to_third_party"] = d["b3p"]
        fields["comments"] = d["cmt"]
        fields["gst_vat_payer"] = d["gst"]
        fields["signatory_consultant"] = d["consultant"]

    if fmt_idx == 1:  # fmt2 — Corporate Trade Finance
        fields["shipper_email"] = d["semail"]
        fields["due_date"] = d["due_date"].strftime("%Y-%m-%d")
        fields["po_number"] = d["po_no"]
        fields["receiver_dhl_account"] = d["racct"]
        fields["total_duty"] = d["td"]
        fields["freight_value"] = d["freight_val"]
        fields["insurance_value"] = d["ins_val"]
        fields["total_invoice_value"] = d["total_inv"]
        fields["bank_name"] = d["bank_name"]
        fields["bank_swift"] = d["bank_swift"]
        fields["signatory_name"] = d["sig_name"]

    if fmt_idx == 2:  # fmt3 — Marks & Numbers / Ocean Freight
        fields["shipper_fax"] = d["sfax"]
        fields["shipper_regno"] = d["sregno"]
        fields["receiver_dhl_account"] = d["racct"]
        fields["notify_party"] = d["nn"]
        fields["booking_reference"] = d["bkg_ref"]
        fields["bill_to_third_party"] = d["b3p"]
        fields["gst_vat_payer"] = d["gst"]
        fields["signatory_name"] = d["sig_name"]

    if fmt_idx == 3:  # fmt4 — Modern E-Commerce / ERP
        fields["shipper_email"] = d["semail"]
        fields["shipper_regno"] = d["sregno"]
        fields["due_date"] = d["due_date"].strftime("%Y-%m-%d")
        fields["receiver_dhl_account"] = d["racct"]
        fields["total_duty"] = d["td"]
        fields["freight_value"] = d["freight_val"]
        fields["insurance_value"] = d["ins_val"]
        fields["total_invoice_value"] = d["total_inv"]
        fields["signatory_name"] = d["sig_name"]

    ann = {
        "document_id":    fname.replace(".pdf",""),
        "document_class": "Commercial Invoice",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    1,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf",".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n:0 for n in FORMAT_NAMES}
    print(f"Generating {count} Commercial Invoice documents (4 format variants)...")
    for i in range(1, count+1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            print(f"  [{i:04d}] {a['format_variant'][:25]:<25} {f['invoice_number']}  "
                  f"{f['currency']} {f['total_declared_value']:>10,.2f}  {len(f['line_items'])} items")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
