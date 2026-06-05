"""
Generates multi-page single-document PDFs (continuation pages).
A Commercial Invoice with 15 line items naturally overflows to page 2 —
pages 1 and 2 are the SAME invoice, not two different invoices.

These are stored in Synthetic_Data_MultiPage/<class>/ and used by the
splitting packet generator as multi-page document blocks.
"""
import json, random, argparse
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_line_items, random_invoice_number, random_vat_number,
    random_dhl_account, random_bl_number, random_container_number,
    random_seal_number, random_hawb_number,
    INCOTERMS, CURRENCIES, PAYMENT_TERMS, EXPORT_TYPES,
    PORTS_SEA, VESSEL_NAMES, PACKAGE_TYPES, COMMODITY_CATEGORIES)

BASE   = Path(__file__).parent.parent
MP_DIR = BASE / "Synthetic_Data_MultiPage"   # separate folder — never touches Synthetic_Data/

BORDER = colors.HexColor("#555555")
LN     = colors.HexColor("#CCCCCC")

def S(n, **k):
    d = dict(fontName="Helvetica", fontSize=8, leading=10,
             textColor=colors.black, spaceAfter=0, spaceBefore=0)
    d.update(k); return ParagraphStyle(n, **d)

def P(t, s): return Paragraph(str(t), s)


# ══════════════════════════════════════════════════════════════════════════
# Commercial Invoice — 12-18 line items → 2 pages
# ══════════════════════════════════════════════════════════════════════════
def gen_ci_multipage(doc_id, out_dir, ann_dir):
    sc = random_country(); rc = random_country()
    while rc[1] == sc[1]: rc = random_country()
    sn = random_company(); sa = fake.address().replace("\n", ", ") + f", {sc[0]}"
    sp = fake.phone_number(); sv = random_vat_number(sc[1])
    rn = random_company(); ra = fake.address().replace("\n", ", ") + f", {rc[0]}"
    rp = fake.phone_number(); rv = random_vat_number(rc[1]); racct = random_dhl_account()
    dt  = fake.date_between(start_date="-2y", end_date="today")
    inv = random_invoice_number(); ref = f"REF-{random.randint(100000,999999)}"
    awb = f"{random.randint(100,999)}-{random.randint(10000000,99999999)}"
    cur = random.choice(CURRENCIES); inc = random.choice(INCOTERMS)
    pay = random.choice(PAYMENT_TERMS); exp = random.choice(EXPORT_TYPES)
    gst = random.choice(["Shipper","Receiver","Third Party"])
    # Force many items (with replacement) to guarantee 2-3 page overflow
    n_force = random.randint(40, 60)
    items = []
    for _ in range(n_force):
        cat = random.choice(COMMODITY_CATEGORIES)
        qty = random.randint(5,200)
        uv  = round(random.uniform(*cat["unit_value_range"]), 2)
        uw  = round(random.uniform(*cat["unit_weight_kg"]), 3)
        items.append({"description":cat["description"],"hs_code":cat["hs_code"],
                      "unit":cat["unit"],"qty":qty,"unit_value":uv,
                      "total_value":round(qty*uv,2),"unit_weight_kg":uw,
                      "total_weight_kg":round(qty*uw,2),
                      "country_of_origin":random_country()[0],
                      "part_no":f"PN-{random.randint(10000,99999)}",
                      "eccn":"EAR99","duty_rate":0.0,"duty_amount":0.0,
                      "marks":f"MK/{random.randint(1,99)}",
                      "n_packages":random.randint(1,10),"pkg_type":"CTN"})
    tv = round(sum(i["total_value"]     for i in items), 2)
    tn = round(sum(i["total_weight_kg"] for i in items), 2)
    tg = round(tn * random.uniform(1.05, 1.25), 2)
    tp = random.randint(len(items), len(items) * 15)
    sig = fake.name(); pos = random.choice(["Export Manager","Trade Director","Logistics Manager"])
    consultant = fake.name()

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
        "glbl":  S("gl", fontSize=8), "gval": S("gv", fontName="Helvetica-Bold", fontSize=8.5),
        "decl":  S("dc", fontSize=7.5, leading=10), "sig": S("sg", fontSize=8),
    }
    def Ps(t, s): return P(t, st[s])

    fname = f"ci_mp_{doc_id:04d}.pdf"
    W = 186*mm; LW, RW = 88*mm, 98*mm

    doc = SimpleDocTemplate(str(out_dir / fname), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    story = []

    # Title banner
    story.append(Table([[Ps("COMMERCIAL INVOICE","title")]], [W],
        rowHeights=[10*mm]))
    story[-1].setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#D40511")),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("BOX",(0,0),(-1,-1),.5,BORDER)]))
    story.append(Spacer(1,1*mm))

    # Header
    def addr(hdr, name, addr_str, phone, vat, extra=None):
        r=[Ps(hdr,"lbl"),Ps(name,"val"),Ps(addr_str,"sm"),
           Spacer(1,1*mm),Ps(f"Phone: {phone}","sm"),Ps(f"VAT/GST: {vat}","sm")]
        if extra:
            for k,v in extra.items(): r.append(Ps(f"{k}: {v}","sm"))
        return r

    hdr = [
        [addr("SHIPPER",sn,sa,sp,sv), [Spacer(1,4*mm),Ps("Commercial Invoice","title"),Spacer(1,4*mm)]],
        ["",""],["",""],
        [addr("RECEIVER",rn,ra,rp,rv,{"DHL Acct":racct}),
         [Ps("Date:","lbl"),Ps(dt.strftime("%d %b %Y"),"val")]],
        ["", [Ps("Invoice Number:","lbl"),Ps(inv,"val")]],
        ["", [Ps("Shipment Reference:","lbl"),Ps(ref,"val")]],
        [[Ps("Airway Bill Number:","lbl"),Ps(awb,"val")],
         [Ps("Incoterms:","lbl"),Ps(f"{inc}  |  Currency: {cur}","val")]],
    ]
    ht = Table(hdr, colWidths=[LW, RW])
    ht.setStyle(TableStyle([
        ("SPAN",(0,0),(0,2)),("SPAN",(1,0),(1,2)),("SPAN",(0,3),(0,5)),
        ("SPAN",(0,6),(1,6)),
        ("BACKGROUND",(1,0),(1,2),colors.HexColor("#D0D0D0")),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP"),
        ("VALIGN",(1,0),(1,2),"MIDDLE"),
    ]))
    story.append(ht); story.append(Spacer(1,1*mm))

    # Items table — many rows = overflows to page 2
    CW = [8*mm,50*mm,10*mm,10*mm,20*mm,17*mm,17*mm,17*mm,17*mm,20*mm]
    rows = [[Ps("No.","ch"),Ps("Full Description of Goods","ch"),Ps("Qty.","ch"),
             Ps("UOM","ch"),Ps("Commodity Code","ch"),Ps(f"Unit Value ({cur})","ch"),
             Ps("Subtotal Value","ch"),Ps("Unit Wt (KG)","ch"),
             Ps("Subtotal Wt (KG)","ch"),Ps("Country of Origin","ch")]]
    for i,it in enumerate(items,1):
        rows.append([Ps(i,"cdc"),Ps(it["description"],"cd"),Ps(it["qty"],"cdr"),
                     Ps(it["unit"],"cdc"),Ps(it["hs_code"],"cdc"),
                     Ps(f"{it['unit_value']:,.2f}","cdr"),Ps(f"{it['total_value']:,.2f}","cdr"),
                     Ps(f"{it['unit_weight_kg']:.3f}","cdr"),
                     Ps(f"{it['total_weight_kg']:.2f}","cdr"),
                     Ps(it["country_of_origin"],"cd")])
    ni = len(items)
    rows.append([Ps(f"Total Declared Value: {cur} {tv:,.2f}","tlbl"),
                 "","","","","",
                 Ps(f"Total Net Weight: {tn:,.3f} KG | Pieces: {tp} | Gross Wt: {tg:,.3f} KG","tlbl"),
                 "","",""])
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    stripe = [("BACKGROUND",(0,r),(-1,r),colors.HexColor("#FAFAFA"))
              for r in range(1,ni+1) if r%2==0]
    it_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("SPAN",(0,ni+1),(5,ni+1)),("SPAN",(6,ni+1),(9,ni+1)),
        ("BACKGROUND",(0,ni+1),(-1,ni+1),colors.HexColor("#F5F5F5")),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ] + stripe))
    story.append(it_t); story.append(Spacer(1,2*mm))

    # GST + signature (may appear on page 2)
    gst_t = Table([[Ps("Payer of GST/VAT:","glbl"),Ps(gst,"gval"),
                    Ps("Currency Code:","glbl"),Ps(cur,"gval")],
                   [Ps("Type of Export:","glbl"),Ps(exp,"gval"),
                    Ps("Payment Terms:","glbl"),Ps(pay,"gval")]],
                  [36*mm,46*mm,30*mm,74*mm])
    gst_t.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),
        ("INNERGRID",(0,0),(-1,-1),.3,LN),("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4)]))
    story.append(gst_t); story.append(Spacer(1,2*mm))

    sig_t = Table([[Ps("I/We hereby certify that the information on this invoice is true and correct.","decl"),Ps("","decl")],
                   [Spacer(1,5*mm),Spacer(1,5*mm)],
                   [Ps("Signature: ___________________________","sig"),Ps("Company Stamp:","sig")],
                   [Ps(f"Position: {pos}","sig"),Ps("","sig")],
                   [Ps(f"Shipping Consultant: {consultant}","sig"),Ps(sn,"sig")]],
                  [W*0.55, W*0.45])
    sig_t.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),
        ("INNERGRID",(0,0),(-1,-1),.3,LN),("SPAN",(0,0),(-1,0)),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(sig_t)

    doc.build(story)

    ann = {"document_id": fname.replace(".pdf",""), "document_class": "Commercial Invoice",
           "class_index": 1, "is_multipage": True,
           "fields": {"shipper_name":sn,"shipper_address":sa,"shipper_phone":sp,"shipper_vat":sv,
                      "shipper_country":sc[0],"receiver_name":rn,"receiver_address":ra,
                      "receiver_phone":rp,"receiver_vat":rv,"receiver_dhl_account":racct,
                      "receiver_country":rc[0],"invoice_date":dt.strftime("%Y-%m-%d"),
                      "invoice_number":inv,"shipment_reference":ref,"airway_bill_number":awb,
                      "currency":cur,"incoterm":inc,"payment_terms":pay,"export_type":exp,
                      "gst_vat_payer":gst,"total_declared_value":tv,"total_net_weight_kg":tn,
                      "total_gross_weight_kg":tg,"total_pieces":tp,
                      "signatory_name":sig,"signatory_position":pos,"line_items":items}}
    (ann_dir / fname.replace(".pdf",".json")).write_text(json.dumps(ann, indent=2))
    return fname


# ══════════════════════════════════════════════════════════════════════════
# Packing List — 15-25 items → 2-3 pages
# ══════════════════════════════════════════════════════════════════════════
def gen_pl_multipage(doc_id, out_dir, ann_dir):
    sc = random_country(); rc = random_country()
    while rc[1] == sc[1]: rc = random_country()
    sn = random_company(); sa = fake.address().replace("\n",", ")+f", {sc[0]}"
    rn = random_company(); ra = fake.address().replace("\n",", ")+f", {rc[0]}"
    inv = random_invoice_number(); ref = f"PL-{random.randint(100000,999999)}"
    bl  = random_bl_number(); dt = fake.date_between(start_date="-2y", end_date="today")
    mode = random.choice(["Air Freight","Ocean Freight","Express Courier"])
    inc  = random.choice(INCOTERMS)

    # Force many items with replacement → overflow (40-60 items = 2-3 pages)
    n_items = random.randint(40, 60)
    chosen  = random.choices(COMMODITY_CATEGORIES, k=n_items)
    items   = []
    pkg_no  = 1
    for cat in chosen:
        n = random.randint(1,15); pt = random.choice(PACKAGE_TYPES)
        nw = round(random.uniform(1,30)*n,2); gw = round(nw*random.uniform(1.05,1.15),2)
        l,w,h = random.randint(20,120),random.randint(15,80),random.randint(10,60)
        cbm = round(n*(l/100)*(w/100)*(h/100),3)
        items.append({"pkg_no":f"{pkg_no}-{pkg_no+n-1}","n_pkgs":n,"pkg_type":pt,
                      "description":cat["description"],"hs_code":cat["hs_code"],
                      "net_weight":nw,"gross_weight":gw,
                      "dims":f"{l}x{w}x{h}cm","cbm":cbm,"origin":sc[0]})
        pkg_no+=n
    tp = sum(i["n_pkgs"] for i in items)
    tn = round(sum(i["net_weight"]   for i in items),2)
    tg = round(sum(i["gross_weight"] for i in items),2)
    tc = round(sum(i["cbm"]          for i in items),3)

    st = {"title":S("t",fontName="Helvetica-Bold",fontSize=13,alignment=TA_CENTER),
          "lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
          "val":S("v",fontName="Helvetica-Bold",fontSize=8),
          "sm":S("sm",fontSize=7,leading=9),
          "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER),
          "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,leading=9,alignment=TA_RIGHT),
          "cdc":S("cdc",fontSize=7,leading=9,alignment=TA_CENTER),}
    def Ps(t,s): return P(t,st[s])

    fname = f"pl_mp_{doc_id:04d}.pdf"
    W = 186*mm
    doc = SimpleDocTemplate(str(out_dir/fname), pagesize=A4,
                            leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story = []
    story.append(Table([[Ps("PACKING LIST","title")]],[W]))
    story[-1].setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#EEEEEE")),
        ("BOX",(0,0),(-1,-1),.8,BORDER),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(Spacer(1,2*mm))

    hdr = Table([[
        [Ps("SHIPPER","lbl"),Ps(sn,"val"),Ps(sa,"sm")],
        [Ps("CONSIGNEE","lbl"),Ps(rn,"val"),Ps(ra,"sm")],
        [Ps("Invoice No:","lbl"),Ps(inv,"val"),Spacer(1,1*mm),
         Ps("PL Ref:","lbl"),Ps(ref,"val"),Spacer(1,1*mm),
         Ps("Date:","lbl"),Ps(dt.strftime("%d %b %Y"),"val"),Spacer(1,1*mm),
         Ps("B/L - AWB:","lbl"),Ps(bl,"val"),Spacer(1,1*mm),
         Ps(f"Mode: {mode}  |  Incoterms: {inc}","sm")]
    ]],[62*mm,62*mm,62*mm])
    hdr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(hdr); story.append(Spacer(1,1*mm))

    CW=[18*mm,10*mm,18*mm,48*mm,20*mm,18*mm,18*mm,18*mm,18*mm]
    rows=[[Ps("Mark & No.","ch"),Ps("Pkgs","ch"),Ps("Type","ch"),Ps("Description of Goods","ch"),
           Ps("HS Code","ch"),Ps("Net Wt KG","ch"),Ps("Gross Wt KG","ch"),Ps("Dimensions","ch"),Ps("CBM","ch")]]
    for it in items:
        rows.append([Ps(it["pkg_no"],"cdc"),Ps(it["n_pkgs"],"cdc"),Ps(it["pkg_type"],"cdc"),
                     Ps(it["description"],"cd"),Ps(it["hs_code"],"cdc"),
                     Ps(f"{it['net_weight']:,.2f}","cdr"),Ps(f"{it['gross_weight']:,.2f}","cdr"),
                     Ps(it["dims"],"cdc"),Ps(f"{it['cbm']:.3f}","cdr")])
    rows.append([Ps("TOTAL","ch"),Ps(str(tp),"cdc"),Ps("","cdc"),Ps("","cd"),Ps("","cdc"),
                 Ps(f"{tn:,.2f}","cdr"),Ps(f"{tg:,.2f}","cdr"),Ps("","cdc"),Ps(f"{tc:.3f}","cdr")])
    ni=len(items); stripe=[("BACKGROUND",(0,r),(-1,r),colors.HexColor("#FAFAFA")) for r in range(1,ni+1) if r%2==0]
    it_t=Table(rows,colWidths=CW,repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EEEEEE")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]+stripe))
    story.append(it_t)
    story.append(Spacer(1,3*mm))
    story.append(Ps(f"Prepared by: {fake.name()}  |  Position: Logistics Coordinator  |  Date: {dt.strftime('%d %b %Y')}","sm"))
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Packing List",
         "class_index":8,"is_multipage":True,
         "fields":{"shipper_name":sn,"consignee_name":rn,"invoice_number":inv,
                   "reference":ref,"bl_awb":bl,"date":dt.strftime("%Y-%m-%d"),
                   "mode":mode,"incoterms":inc,"total_packages":tp,
                   "total_net_weight_kg":tn,"total_gross_weight_kg":tg,"total_cbm":tc,"items":items}}
    (ann_dir/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return fname


# ══════════════════════════════════════════════════════════════════════════
# Cargo Manifest — 20-30 entries → 2-3 pages (landscape)
# ══════════════════════════════════════════════════════════════════════════
def gen_manifest_multipage(doc_id, out_dir, ann_dir):
    from reportlab.lib.pagesizes import landscape
    m_type   = random.choice(["Air Freight","Ocean Freight"])
    manifest_no = f"MFT-{random.randint(100000,999999)}"
    dt  = fake.date_between(start_date="-2y", end_date="today")
    vessel  = random.choice(VESSEL_NAMES) if m_type=="Ocean Freight" else f"{random.choice(['DL','LH','EK'])}{random.randint(100,999)}"
    agent   = random.choice(["DHL Global Forwarding","Kuehne + Nagel","DB Schenker"])
    pol     = random.choice(PORTS_SEA); pod = random.choice(PORTS_SEA)
    while pod==pol: pod=random.choice(PORTS_SEA)
    n_entries = random.randint(45, 65)  # force 2-3 pages in landscape
    entries   = []
    for _ in range(n_entries):
        sc=random_country(); dc=random_country()
        entries.append({
            "ref_no": random_bl_number() if m_type=="Ocean Freight" else random_hawb_number(),
            "shipper": random_company(), "consignee": random_company(),
            "origin":sc[0][:14],"destination":dc[0][:14],
            "n_pkgs": random.randint(1,50), "pkg_type":random.choice(["CTN","PLT","DRM"]),
            "description": random.choice(["General Cargo","Electronics","Machinery","Textiles","Chemicals"]),
            "gross_weight":round(random.uniform(50,5000),1),
            "cbm":round(random.uniform(0.5,20),2)})
    tw = round(sum(e["gross_weight"] for e in entries),1)
    tc = round(sum(e["cbm"]          for e in entries),2)
    tp = sum(e["n_pkgs"]             for e in entries)

    st={"title":S("t",fontName="Helvetica-Bold",fontSize=10,alignment=TA_CENTER,textColor=colors.white),
        "lbl":S("l",fontSize=7,textColor=colors.HexColor("#444444")),
        "val":S("v",fontName="Helvetica-Bold",fontSize=7.5),
        "ch":S("ch",fontName="Helvetica-Bold",fontSize=6.5,alignment=TA_CENTER,textColor=colors.white),
        "cd":S("cd",fontSize=6.5,leading=8.5),"cdr":S("cdr",fontSize=6.5,leading=8.5,alignment=TA_RIGHT),
        "cdc":S("cdc",fontSize=6.5,leading=8.5,alignment=TA_CENTER),}
    def Ps(t,s): return P(t,st[s])

    fname = f"manifest_mp_{doc_id:04d}.pdf"
    PW = 277*mm  # landscape A4
    doc = SimpleDocTemplate(str(out_dir/fname), pagesize=landscape(A4),
                            leftMargin=10*mm,rightMargin=10*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]
    story.append(Table([[Ps(f"CARGO MANIFEST — {m_type.upper()}","title")]],[PW]))
    story[-1].setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#1a1a2e")),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(Spacer(1,2*mm))

    mh=Table([[Ps("MANIFEST NO.","lbl"),Ps(manifest_no,"val"),
               Ps("VESSEL / FLIGHT","lbl"),Ps(vessel,"val"),
               Ps("DATE","lbl"),Ps(dt.strftime("%d %b %Y"),"val"),
               Ps("AGENT","lbl"),Ps(agent,"val")],
              [Ps("PORT OF LOADING","lbl"),Ps(pol,"val"),
               Ps("PORT OF DISCHARGE","lbl"),Ps(pod,"val"),
               Ps("TOTAL PACKAGES","lbl"),Ps(str(tp),"val"),
               Ps("TOTAL GROSS WT (KG)","lbl"),Ps(f"{tw:,.1f}","val")]],
             [30*mm,36*mm,28*mm,38*mm,26*mm,20*mm,40*mm,26*mm])
    mh.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),3),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,-1),colors.HexColor("#EEEEEE")),("BACKGROUND",(6,0),(6,-1),colors.HexColor("#EEEEEE"))]))
    story.append(mh); story.append(Spacer(1,1*mm))

    CW=[24*mm,38*mm,36*mm,20*mm,20*mm,10*mm,10*mm,34*mm,17*mm,15*mm,17*mm]
    cols=[[Ps("AWB/B/L No.","ch"),Ps("Shipper","ch"),Ps("Consignee","ch"),
           Ps("Country\nOrigin","ch"),Ps("Country\nDest","ch"),
           Ps("Pkgs","ch"),Ps("Type","ch"),Ps("Description","ch"),
           Ps("Gross Wt\n(KG)","ch"),Ps("CBM","ch"),Ps("Remarks","ch")]]
    for e in entries:
        cols.append([Ps(e["ref_no"],"cd"),Ps(e["shipper"],"cd"),Ps(e["consignee"],"cd"),
                     Ps(e["origin"],"cdc"),Ps(e["destination"],"cdc"),
                     Ps(e["n_pkgs"],"cdc"),Ps(e["pkg_type"],"cdc"),Ps(e["description"],"cd"),
                     Ps(f"{e['gross_weight']:,.1f}","cdr"),Ps(f"{e['cbm']:.2f}","cdr"),Ps("","cd")])
    cols.append([Ps("TOTALS","ch")]+[Ps("","cdc")]*4+[Ps(str(tp),"cdc")]+
                [Ps("","cdc"),Ps("","cd"),Ps(f"{tw:,.1f}","cdr"),Ps(f"{tc:.2f}","cdr"),Ps("","cd")])
    ne=len(entries); stripe=[("BACKGROUND",(0,r),(-1,r),colors.HexColor("#F4F4F4")) for r in range(1,ne+1) if r%2==0]
    it=Table(cols,colWidths=CW,repeatRows=1)
    it.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EEEEEE")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),1.5),("BOTTOMPADDING",(0,0),(-1,-1),1.5),
        ("LEFTPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]+stripe))
    story.append(it)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Cargo Manifest",
         "class_index":10,"is_multipage":True,
         "fields":{"manifest_no":manifest_no,"manifest_type":m_type,"transport":vessel,
                   "date":dt.strftime("%Y-%m-%d"),"from_location":pol,"to_location":pod,
                   "agent":agent,"total_entries":ne,"total_packages":tp,
                   "total_gross_weight_kg":tw,"total_cbm":tc,"entries":entries}}
    (ann_dir/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return fname


# ══════════════════════════════════════════════════════════════════════════
# Registry + generate
# ══════════════════════════════════════════════════════════════════════════
MULTIPAGE_GENERATORS = {
    "01": ("Commercial Invoice",   gen_ci_multipage,       "01_Commercial_Invoice"),
    "08": ("Packing List",         gen_pl_multipage,       "08_Packing_List"),
    "10": ("Cargo Manifest",       gen_manifest_multipage, "10_Cargo_Manifest"),
}

def generate(count_per_class: int = 500):
    """Generate multi-page documents for CI, PL, and Cargo Manifest."""
    print(f"Generating {count_per_class} multi-page docs per class "
          f"into {MP_DIR}/")
    for cls_idx, (cls_name, gen_fn, folder) in MULTIPAGE_GENERATORS.items():
        out_dir = MP_DIR / folder / "pdfs"
        ann_dir = MP_DIR / folder / "annotations"
        out_dir.mkdir(parents=True, exist_ok=True)
        ann_dir.mkdir(parents=True, exist_ok=True)
        for f in list(out_dir.glob("*.pdf")) + list(ann_dir.glob("*.json")):
            f.unlink()
        print(f"\n  [{cls_idx}] {cls_name} ({count_per_class} docs)...")
        for i in range(1, count_per_class + 1):
            fname = gen_fn(i, out_dir, ann_dir)
            if i <= 3 or i % 100 == 0:
                import fitz; d = fitz.open(str(out_dir/fname))
                print(f"    [{i:04d}] {fname}  ({len(d)} pages)")
                d.close()
    print(f"\nDone. Multi-page docs in: {MP_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=500,
                   help="Docs per class (default 500)")
    generate(p.parse_args().count)
