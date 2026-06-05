"""
Extends multi-page single-doc generation to remaining 9 classes.
These 2-page PDFs give the model CONTINUATION examples for every class —
not just CI, PL, Manifest (which were already done).

Page 1 = START  (full header + first portion of content)
Page 2 = CONTINUATION (rest of content + footer/signature)

Real-world justification for multi-page:
  HBL:  10+ containers with long cargo descriptions
  SLI:  20+ commodity lines with Schedule B codes
  DGD:  5+ DG entries (each entry is large) → overflows
  COO:  Multiple pages of goods table
  HAWB: Consolidated AWB with many sub-shipments
  VGM:  Multiple containers per submission (5+)
  EEI:  15+ HTS line items → overflows CBP 7501
  POA:  Multi-jurisdiction authorization + exhibits
  CN23: Many items with full descriptions

Saved to: Synthetic_Data_MultiPage/<class>/pdfs/
"""
import json, random, argparse
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_bl_number, random_container_number, random_seal_number,
    random_hawb_number, random_mawb_number, random_invoice_number,
    random_vat_number, VESSEL_NAMES, PORTS_SEA, AIRPORTS,
    COMMODITY_CATEGORIES, UN_NUMBERS, PACKAGE_TYPES, INCOTERMS,
    CURRENCIES, PAYMENT_TERMS, EXPORT_TYPES)

BASE   = Path(__file__).parent.parent
MP_DIR = BASE / "Synthetic_Data_MultiPage"

BORDER = colors.HexColor("#555555"); LN = colors.HexColor("#CCCCCC")

def S(n, **k):
    d = dict(fontName="Helvetica", fontSize=8, leading=10,
             textColor=colors.black, spaceAfter=0, spaceBefore=0)
    d.update(k); return ParagraphStyle(n, **d)

def P(t, s): return Paragraph(str(t), s)

def tbl_style(t, cmds):
    t.setStyle(TableStyle(cmds)); return t


# ══════════════════════════════════════════════════════════════════════════
# HBL — 10-15 containers with detailed cargo → 2 pages
# ══════════════════════════════════════════════════════════════════════════
def gen_hbl(doc_id, out_dir, ann_dir):
    sc=random_country(); rc=random_country()
    while rc[1]==sc[1]: rc=random_country()
    nc=random_country()
    sn=random_company(); sa=fake.address().replace("\n",", ")+f", {sc[0]}"
    cn=random_company(); ca=fake.address().replace("\n",", ")+f", {rc[0]}"
    nn=random_company(); na=fake.address().replace("\n",", ")+f", {nc[0]}"
    bl=random_bl_number()
    pol=random.choice(PORTS_SEA); pod=random.choice(PORTS_SEA)
    while pod==pol: pod=random.choice(PORTS_SEA)
    vessel=random.choice(VESSEL_NAMES); voyage=f"{random.randint(100,999)}N"
    dt=fake.date_between(start_date="-2y", end_date="today")
    freight=random.choice(["PREPAID","COLLECT"])
    # Force many containers → overflow
    n_ctrs = random.randint(25, 40)  # force 2-page overflow
    containers = []
    for _ in range(n_ctrs):
        cat = random.choice(COMMODITY_CATEGORIES)
        containers.append({
            "container_no": random_container_number(),
            "seal_no": random_seal_number(),
            "type": random.choice(["20'GP","40'GP","40'HC","45'HC"]),
            "pkgs": random.randint(10,200),
            "description": cat["description"],
            "hs_code": cat["hs_code"],
            "gross_wt": round(random.uniform(500,28000),1),
            "cbm": round(random.uniform(5,67),2),
            "origin": sc[0],
            "marks": f"{random.choice(['ABC','XYZ'])}/{random.randint(1,99)}",
        })
    tw=round(sum(c["gross_wt"] for c in containers),1)
    tc=round(sum(c["cbm"]      for c in containers),2)
    tp=sum(c["pkgs"]           for c in containers)
    st={"title":S("t",fontName="Helvetica-Bold",fontSize=12,alignment=TA_CENTER,textColor=colors.white),
        "lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
        "val":S("v",fontName="Helvetica-Bold",fontSize=8),
        "sm":S("sm",fontSize=7,leading=9),
        "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER,textColor=colors.white),
        "cd":S("cd",fontSize=7,leading=9),
        "cdr":S("cdr",fontSize=7,leading=9,alignment=TA_RIGHT),
        "cdc":S("cdc",fontSize=7,leading=9,alignment=TA_CENTER),}
    def Ps(t,s): return P(t,st[s])

    fname=f"hbl_mp_{doc_id:04d}.pdf"
    W=186*mm
    doc=SimpleDocTemplate(str(out_dir/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]
    story.append(Table([[Ps("HOUSE BILL OF LADING","title")]],[W]))
    story[-1].setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#1a1a2e")),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(Spacer(1,1*mm))
    # BL/Date/Freight row
    hr=Table([[Ps("B/L NUMBER","lbl"),Ps(bl,"val"),Ps("DATE OF ISSUE","lbl"),Ps(dt.strftime("%d %b %Y"),"val"),
               Ps("FREIGHT TERMS","lbl"),Ps(freight,"val")]],
             colWidths=[28*mm,52*mm,28*mm,38*mm,24*mm,16*mm])
    hr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,0),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,0),colors.HexColor("#EEEEEE"))]))
    story.append(hr); story.append(Spacer(1,1*mm))
    # Parties
    pt=Table([[
        [Ps("SHIPPER",  "lbl"),Ps(sn,"val"),Ps(sa,"sm")],
        [Ps("CONSIGNEE","lbl"),Ps(cn,"val"),Ps(ca,"sm")],
        [Ps("NOTIFY PARTY","lbl"),Ps(nn,"val"),Ps(na,"sm")],
    ]],[62*mm,62*mm,62*mm])
    pt.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(pt); story.append(Spacer(1,1*mm))
    # Routing
    rt=Table([[Ps("VESSEL / VOYAGE","lbl"),Ps(f"{vessel} / {voyage}","val"),
               Ps("PORT OF LOADING","lbl"),Ps(pol,"val"),
               Ps("PORT OF DISCHARGE","lbl"),Ps(pod,"val")]],
             colWidths=[34*mm,52*mm,28*mm,38*mm,28*mm,6*mm])
    rt.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,0),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,0),colors.HexColor("#EEEEEE"))]))
    story.append(rt); story.append(Spacer(1,1*mm))
    # Container table (many rows = overflow)
    CW=[26*mm,20*mm,14*mm,12*mm,44*mm,18*mm,22*mm,18*mm,12*mm]
    rows=[[Ps("Container No.","ch"),Ps("Seal No.","ch"),Ps("Type","ch"),Ps("Pkgs","ch"),
           Ps("Description & HS Code","ch"),Ps("Gross Wt (KG)","ch"),Ps("CBM","ch"),
           Ps("Country of Origin","ch"),Ps("Marks","ch")]]
    for c in containers:
        rows.append([Ps(c["container_no"],"cdc"),Ps(c["seal_no"],"cdc"),Ps(c["type"],"cdc"),
                     Ps(c["pkgs"],"cdr"),Ps(f"{c['description']}\nHS: {c['hs_code']}","cd"),
                     Ps(f"{c['gross_wt']:,.1f}","cdr"),Ps(f"{c['cbm']:.2f}","cdr"),
                     Ps(c["origin"],"cdc"),Ps(c["marks"],"cdc")])
    rows.append([Ps("TOTAL","ch"),Ps("","cdc"),Ps("","cdc"),Ps(f"{tp:,}","cdr"),
                 Ps("","cd"),Ps(f"{tw:,.1f}","cdr"),Ps(f"{tc:.2f}","cdr"),Ps("","cdc"),Ps("","cdc")])
    nc=len(containers)
    stripe=[("BACKGROUND",(0,r),(-1,r),colors.HexColor("#FAFAFA")) for r in range(1,nc+1) if r%2==0]
    ct=Table(rows,colWidths=CW,repeatRows=1)
    ct.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EEEEEE")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ]+stripe))
    story.append(ct); story.append(Spacer(1,2*mm))
    story.append(Ps(f"Issued by DHL Global Forwarding  |  Signed: _______________  |  Place: {random.choice(PORTS_SEA).split(',')[0]}","sm"))
    doc.build(story)
    ann={"document_id":fname.replace(".pdf",""),"document_class":"House Bill of Lading",
         "class_index":2,"is_multipage":True,
         "fields":{"bl_number":bl,"shipper_name":sn,"consignee_name":cn,"notify_party":nn,
                   "vessel":vessel,"voyage":voyage,"pol":pol,"pod":pod,"freight":freight,
                   "date":dt.strftime("%Y-%m-%d"),"n_containers":nc,"total_packages":tp,
                   "total_gross_wt_kg":tw,"total_cbm":tc}}
    (ann_dir/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return fname


# ══════════════════════════════════════════════════════════════════════════
# SLI — 20+ commodity lines → 2 pages
# ══════════════════════════════════════════════════════════════════════════
def gen_sli(doc_id, out_dir, ann_dir):
    sc=random_country(); dc=random_country()
    while dc[1]==sc[1]: dc=random_country()
    usppi=random_company(); ua=fake.address().replace("\n",", ")+", US"
    ein=fake.bothify("##-#######")
    cn=random_company(); ca=fake.address().replace("\n",", ")+f", {dc[0]}"
    ref=f"SLI-{random.randint(100000,999999)}"
    dt=fake.date_between(start_date="-2y",end_date="today")
    inco=random.choice(INCOTERMS)
    SCHED_B=[("8471.30.0100","Portable ADP Machines"),("8534.00.0000","Printed Circuit Boards"),
             ("6203.42.4011","Men's Trousers, Cotton"),("8708.30.5010","Disc Brake Systems"),
             ("3926.90.9990","Plastic Articles NEC"),("9018.31.0040","Hypodermic Syringes"),
             ("2008.19.9000","Prepared Nuts"),("8518.30.2000","Headphone Assemblies"),
             ("5407.42.0000","Woven Synthetic Fabric"),("7208.37.0030","Hot-Rolled Steel Coils"),
             ("8544.42.9000","Electric Conductors"),("9403.20.0018","Metal Office Furniture"),
             ("6110.20.2075","Cotton Knit Sweaters"),("8481.80.3090","Industrial Valves"),
             ("3004.90.9195","Pharmaceutical Preparations"),("8504.40.9550","Power Supplies"),
             ("8443.99.2550","Printer Parts"),("7326.90.8688","Steel Articles NEC"),]
    n_items=random.randint(30,40)  # guaranteed 2-page overflow
    chosen=random.choices(SCHED_B, k=n_items)
    items=[{"marks":f"MK-{random.randint(1,99)}","description":d,"sb":sb,
            "dom_for":random.choice(["D","F"]),"qty":random.randint(10,500),
            "unit":random.choice(["PCS","KGS","MTR","CTN"]),
            "wt":round(random.uniform(5,200),2),"val":round(random.uniform(500,50000),2)}
           for sb,d in chosen]
    sig=fake.name(); pos=random.choice(["Export Manager","Compliance Officer","Trade Director"])
    st={"title":S("t",fontName="Helvetica-Bold",fontSize=11,alignment=TA_CENTER,textColor=colors.white),
        "hdr":S("h",fontName="Helvetica-Bold",fontSize=7.5,textColor=colors.HexColor("#1a1a2e")),
        "lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
        "val":S("v",fontName="Helvetica-Bold",fontSize=8),
        "sm":S("sm",fontSize=7,leading=9),
        "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER,textColor=colors.white),
        "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,alignment=TA_RIGHT,leading=9),
        "cdc":S("cdc",fontSize=7,alignment=TA_CENTER,leading=9),}
    def Ps(t,s): return P(t,st[s])
    fname=f"sli_mp_{doc_id:04d}.pdf"
    W=186*mm
    doc=SimpleDocTemplate(str(out_dir/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]
    story.append(Table([[Ps("U.S. SHIPPER'S LETTER OF INSTRUCTIONS","title")]],[W]))
    story[-1].setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#1a1a2e")),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(Spacer(1,1*mm))
    dr=Table([[Ps("DATE","lbl"),Ps(dt.strftime("%d %b %Y"),"val"),
               Ps("REFERENCE NO.","lbl"),Ps(ref,"val"),
               Ps("INCOTERMS","lbl"),Ps(inco,"val"),
               Ps("COUNTRY OF DESTINATION","lbl"),Ps(dc[0],"val")]],
             [18*mm,28*mm,26*mm,30*mm,20*mm,18*mm,42*mm,4*mm])
    dr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),3),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,0),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(6,0),(6,0),colors.HexColor("#EEEEEE"))]))
    story.append(dr); story.append(Spacer(1,1*mm))
    pp=Table([[
        [Ps("USPPI (U.S. PRINCIPAL PARTY IN INTEREST)","hdr"),Ps(usppi,"val"),Ps(ua,"sm"),Ps(f"EIN: {ein}","sm")],
        [Ps("ULTIMATE CONSIGNEE","hdr"),Ps(cn,"val"),Ps(ca,"sm")],
    ]],[100*mm,86*mm])
    pp.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(pp); story.append(Spacer(1,1*mm))
    # Items (many rows → overflow)
    CW=[16*mm,10*mm,56*mm,10*mm,26*mm,18*mm,18*mm,22*mm]
    rows=[[Ps("Marks & Nos","ch"),Ps("D/F","ch"),Ps("Description of Commodities","ch"),
           Ps("Schedule B Number","ch"),Ps("Qty / Unit","ch"),
           Ps("Weight (KG)","ch"),Ps("Value (USD)","ch"),Ps("ECCN","ch")]]
    eccns=["EAR99","5E992","3A992","7A994","0A988","2B350"]
    for it in items:
        rows.append([Ps(it["marks"],"cdc"),Ps(it["dom_for"],"cdc"),Ps(it["description"],"cd"),
                     Ps(it["sb"],"cdc"),Ps(f"{it['qty']} {it['unit']}","cdr"),
                     Ps(f"{it['wt']:,.2f}","cdr"),Ps(f"{it['val']:,.2f}","cdr"),
                     Ps(random.choice(eccns),"cdc")])
    ni=len(items)
    stripe=[("BACKGROUND",(0,r),(-1,r),colors.HexColor("#FAFAFA")) for r in range(1,ni+1) if r%2==0]
    it_t=Table(rows,colWidths=CW,repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1a1a2e")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]+stripe))
    story.append(it_t); story.append(Spacer(1,2*mm))
    story.append(Ps(f"Signature: {sig}  |  Title: {pos}  |  Date: {dt.strftime('%d %b %Y')}","sm"))
    doc.build(story)
    ann={"document_id":fname.replace(".pdf",""),"document_class":"Shipper's Letter of Instruction",
         "class_index":4,"is_multipage":True,
         "fields":{"reference":ref,"usppi":usppi,"consignee":cn,
                   "destination":dc[0],"incoterm":inco,"n_items":ni,
                   "total_value_usd":round(sum(i["val"] for i in items),2)}}
    (ann_dir/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return fname


# ══════════════════════════════════════════════════════════════════════════
# DGD — 5-8 DG entries per page → 2 pages
# ══════════════════════════════════════════════════════════════════════════
def gen_dgd(doc_id, out_dir, ann_dir):
    sn=random_company(); sa=fake.address().replace("\n",", ")
    cn=random_company(); ca=fake.address().replace("\n",", ")
    awb=random_hawb_number(); emg=fake.phone_number()
    dep_name,dep_code=random.choice(AIRPORTS); dest_name,dest_code=random.choice(AIRPORTS)
    while dest_code==dep_code: dest_name,dest_code=random.choice(AIRPORTS)
    dt=fake.date_between(start_date="-1y",end_date="today")
    PACKING_INST=["PI 965 Section IA","PI 965 Section IB","PI 966 Section I","PI 967 Section I",
                   "PI 950","PI 910","PI 903","PI 870","PI 852","PI 959","PI 968"]
    # Force many DG entries → overflow
    n_entries=random.randint(40,55)  # force 2-page overflow
    entries=[]
    for _ in range(n_entries):
        un,name,cls,pg,hazard=random.choice(UN_NUMBERS)
        entries.append({"un":un,"name":name,"cls":cls,"pg":pg or "N/A",
                        "pkgs":random.randint(1,12),
                        "pkg_type":random.choice(["Fibreboard box","Plastic jerrican","Steel drum","Composite packaging"]),
                        "qty":round(random.uniform(0.1,30),2),
                        "unit":random.choice(["kg","L","G","mL"]),
                        "pi":random.choice(PACKING_INST),
                        "auth":f"2025-AUTH-{random.randint(1000,9999)}" if random.random()<0.3 else ""})
    st={"title":S("t",fontName="Helvetica-Bold",fontSize=11,alignment=TA_CENTER,textColor=colors.white),
        "warn":S("w",fontName="Helvetica-Bold",fontSize=8,alignment=TA_CENTER,textColor=colors.HexColor("#CC0000")),
        "lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
        "val":S("v",fontName="Helvetica-Bold",fontSize=8),
        "sm":S("sm",fontSize=7,leading=9),
        "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER,textColor=colors.white),
        "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,leading=9,alignment=TA_RIGHT),
        "cdc":S("cdc",fontSize=7,leading=9,alignment=TA_CENTER),}
    def Ps(t,s): return P(t,st[s])
    fname=f"dgd_mp_{doc_id:04d}.pdf"
    W=186*mm
    doc=SimpleDocTemplate(str(out_dir/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]
    story.append(Table([[Ps("SHIPPER'S DECLARATION FOR DANGEROUS GOODS","title")]],[W]))
    story[-1].setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#1a1a2e")),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(Table([[Ps("AIR TRANSPORT ONLY — IATA DANGEROUS GOODS REGULATIONS","warn")]],[W]))
    story[-1].setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#FFF3CD")),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(Spacer(1,1*mm))
    top=Table([[
        [Ps("SHIPPER","lbl"),Ps(sn,"val"),Ps(sa,"sm"),Ps(f"Emergency Tel: {emg}","sm")],
        [Ps("CONSIGNEE","lbl"),Ps(cn,"val"),Ps(ca,"sm")],
        [Ps("AWB NO.","lbl"),Ps(awb,"val"),Spacer(1,2*mm),
         Ps("DEPARTURE","lbl"),Ps(f"{dep_name} ({dep_code})","val"),Spacer(1,1*mm),
         Ps("DESTINATION","lbl"),Ps(f"{dest_name} ({dest_code})","val")],
    ]],[66*mm,66*mm,54*mm])
    top.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(top); story.append(Spacer(1,1*mm))
    CW=[10*mm,46*mm,10*mm,10*mm,30*mm,16*mm,18*mm,14*mm,20*mm,12*mm]
    rows=[[Ps("UN No.","ch"),Ps("Proper Shipping Name","ch"),Ps("Class","ch"),Ps("PG","ch"),
           Ps("Qty & Pkg Type","ch"),Ps("Net Qty","ch"),Ps("Pkg\nInstruction","ch"),
           Ps("Auth No.","ch"),Ps("Pkgs","ch"),Ps("Unit","ch")]]
    for e in entries:
        rows.append([Ps(e["un"],"cdc"),Ps(e["name"],"cd"),Ps(e["cls"],"cdc"),Ps(e["pg"],"cdc"),
                     Ps(f"{e['pkgs']} × {e['pkg_type']}","cd"),
                     Ps(f"{e['qty']}","cdr"),Ps(e["pi"],"cdc"),
                     Ps(e["auth"] or "-","cdc"),Ps(e["pkgs"],"cdr"),Ps(e["unit"],"cdc")])
    ni=len(entries)
    stripe=[("BACKGROUND",(0,r),(-1,r),colors.HexColor("#FFF8F8")) for r in range(1,ni+1) if r%2==0]
    dt_t=Table(rows,colWidths=CW,repeatRows=1)
    dt_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#CC0000")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ]+stripe))
    story.append(dt_t); story.append(Spacer(1,2*mm))
    story.append(Ps("I hereby declare that the contents of this consignment are fully and accurately described above by the proper shipping name.","sm"))
    story.append(Spacer(1,2*mm))
    story.append(Ps(f"Signed: {fake.name()}  |  Date: {dt.strftime('%d %b %Y')}  |  Place: {dep_name}","sm"))
    doc.build(story)
    ann={"document_id":fname.replace(".pdf",""),"document_class":"Dangerous Goods Declaration",
         "class_index":5,"is_multipage":True,
         "fields":{"shipper":sn,"consignee":cn,"awb":awb,"emergency_tel":emg,
                   "departure":f"{dep_name} ({dep_code})","destination":f"{dest_name} ({dest_code})",
                   "date":dt.strftime("%Y-%m-%d"),"n_dg_entries":ni}}
    (ann_dir/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return fname


# ══════════════════════════════════════════════════════════════════════════
# EEI / CBP Entry Summary — 18+ HTS lines → 2 pages
# ══════════════════════════════════════════════════════════════════════════
def gen_eei(doc_id, out_dir, ann_dir):
    entry_no=f"{random.randint(100,999)}-{fake.bothify('?######',letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"
    dt=fake.date_between(start_date="-2y",end_date="today")
    imp=random_company(); ia=fake.address().replace("\n",", ")+", US"
    ein=fake.bothify("##-#######")
    broker=random.choice(["DHL Global Forwarding","Kuehne + Nagel Customs","C.H. Robinson","Expeditors"])
    carrier=random.choice(["Maersk Line","CMA CGM","MSC","DHL Express","United Airlines Cargo"])
    bl=random_bl_number(); mode=random.choice(["Ocean","Air","Truck"])
    port=random.choice(["New York, NY (1001)","Los Angeles, CA (2704)","Miami, FL (5201)","Chicago, IL (3901)"])
    origin_country=random_country()
    DUTY_RATES=[0.0,0.0,2.5,3.7,5.0,7.5,10.0,15.0,20.0,25.0]
    # Force many HTS items → overflow
    n_items=random.randint(45,60)  # force 2-page overflow
    items=[]
    chosen=random.choices(COMMODITY_CATEGORIES, k=n_items)
    for cat in chosen:
        qty=random.randint(10,500); unit=cat["unit"]
        val=round(random.uniform(500,20000),2)
        dr=random.choice(DUTY_RATES)
        items.append({"hts":cat["hs_code"],"description":cat["description"],
                      "origin":origin_country[0][:14],"qty":qty,"unit":unit,
                      "value":val,"duty_rate":dr,"duty":round(val*dr/100,2)})
    tv=round(sum(i["value"] for i in items),2)
    td=round(sum(i["duty"]  for i in items),2)
    st={"title":S("t",fontName="Helvetica-Bold",fontSize=11,alignment=TA_CENTER,textColor=colors.white),
        "sub":S("s",fontSize=8,alignment=TA_CENTER,textColor=colors.HexColor("#333333")),
        "lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
        "val":S("v",fontName="Helvetica-Bold",fontSize=8),
        "sm":S("sm",fontSize=7,leading=9),
        "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER,textColor=colors.white),
        "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,leading=9,alignment=TA_RIGHT),
        "cdc":S("cdc",fontSize=7,leading=9,alignment=TA_CENTER),}
    def Ps(t,s): return P(t,st[s])
    fname=f"eei_mp_{doc_id:04d}.pdf"
    W=186*mm
    doc=SimpleDocTemplate(str(out_dir/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]
    story.append(Table([[Ps("U.S. CUSTOMS AND BORDER PROTECTION","sub")],[Ps("ENTRY SUMMARY — CBP Form 7501","title")]],[W]))
    story[-1].setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),colors.HexColor("#002868")),
        ("TEXTCOLOR",(0,0),(0,0),colors.HexColor("#AAAAAA")),
        ("BACKGROUND",(0,1),(0,1),colors.HexColor("#BF0A30")),("TEXTCOLOR",(0,1),(0,1),colors.white),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(Spacer(1,1*mm))
    eh=Table([[Ps("ENTRY NO.","lbl"),Ps(entry_no,"val"),Ps("ENTRY DATE","lbl"),Ps(dt.strftime("%m/%d/%Y"),"val"),
               Ps("PORT OF ENTRY","lbl"),Ps(port,"val"),Ps("MODE","lbl"),Ps(mode,"val")],
              [Ps("IMPORTER","lbl"),Ps(imp,"val"),Ps("EIN","lbl"),Ps(ein,"val"),
               Ps("CARRIER","lbl"),Ps(carrier,"val"),Ps("B/L OR AWB","lbl"),Ps(bl,"val")]],
             [22*mm,36*mm,22*mm,30*mm,20*mm,28*mm,14*mm,14*mm])
    eh.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),3),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,-1),colors.HexColor("#EEEEEE")),("BACKGROUND",(6,0),(6,-1),colors.HexColor("#EEEEEE"))]))
    story.append(eh); story.append(Spacer(1,1*mm))
    # Items (overflow)
    CW=[22*mm,52*mm,20*mm,12*mm,12*mm,20*mm,14*mm,20*mm,14*mm]
    rows=[[Ps("HTS No.","ch"),Ps("Description of Merchandise","ch"),Ps("Country\nOrigin","ch"),
           Ps("Qty","ch"),Ps("Unit","ch"),Ps("Entered\nValue (USD)","ch"),
           Ps("Duty\nRate","ch"),Ps("Duty\nAmount (USD)","ch"),Ps("Add'l\nDuty","ch")]]
    for it in items:
        rows.append([Ps(it["hts"],"cdc"),Ps(it["description"],"cd"),Ps(it["origin"],"cdc"),
                     Ps(it["qty"],"cdr"),Ps(it["unit"],"cdc"),Ps(f"{it['value']:,.2f}","cdr"),
                     Ps(f"{it['duty_rate']:.1f}%","cdc"),Ps(f"{it['duty']:,.2f}","cdr"),Ps("-","cdc")])
    rows.append([Ps("TOTALS","ch")]+[Ps("","cdc")]*3+[Ps("","cdc")]+
                [Ps(f"{tv:,.2f}","cdr"),Ps("","cdc"),Ps(f"{td:,.2f}","cdr"),Ps("","cdc")])
    ni=len(items)
    stripe=[("BACKGROUND",(0,r),(-1,r),colors.HexColor("#EEF2F7")) for r in range(1,ni+1) if r%2==0]
    it_t=Table(rows,colWidths=CW,repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#002868")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EEEEEE")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP"),
    ]+stripe))
    story.append(it_t); story.append(Spacer(1,2*mm))
    story.append(Ps(f"Broker: {broker}  |  Declared by: {fake.name()}  |  Date: {dt.strftime('%m/%d/%Y')}","sm"))
    doc.build(story)
    ann={"document_id":fname.replace(".pdf",""),"document_class":"Import/Export License",
         "class_index":11,"is_multipage":True,
         "fields":{"entry_number":entry_no,"importer":imp,"port":port,"carrier":carrier,
                   "mode":mode,"country_of_origin":origin_country[0],
                   "date":dt.strftime("%Y-%m-%d"),"n_items":ni,
                   "total_value_usd":tv,"total_duty_usd":td}}
    (ann_dir/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return fname


# ══════════════════════════════════════════════════════════════════════════
# VGM — 5+ containers per submission → 2 pages
# ══════════════════════════════════════════════════════════════════════════
def gen_vgm(doc_id, out_dir, ann_dir):
    shipper=random_company(); addr=fake.address().replace("\n",", ")
    bl=random_bl_number(); booking=f"BKG-{random.randint(100000,999999)}"
    pol=random.choice(PORTS_SEA); pod=random.choice(PORTS_SEA)
    while pod==pol: pod=random.choice(PORTS_SEA)
    dt=fake.date_between(start_date="-1y",end_date="today")
    TARES={"20'GP":2200,"40'GP":3900,"40'HC":4000,"45'HC":4800,"20'RF":2900}
    n_ctrs=random.randint(35,50)  # force 2-page overflow
    containers=[]
    for _ in range(n_ctrs):
        ctype=random.choice(list(TARES.keys())); tare=TARES[ctype]
        method=random.choice([1,2]); cargo=round(random.uniform(2000,22000),1)
        vgm=round(cargo+tare,1)
        containers.append({"no":random_container_number(),"seal":random_seal_number(),
                            "type":ctype,"method":method,"tare":tare,
                            "cargo_wt":cargo,"vgm":vgm,"unit":"KGS"})
    st={"title":S("t",fontName="Helvetica-Bold",fontSize=13,alignment=TA_CENTER,textColor=colors.white),
        "lbl":S("l",fontSize=7.5,textColor=colors.HexColor("#444444")),
        "val":S("v",fontName="Helvetica-Bold",fontSize=8.5),
        "sm":S("sm",fontSize=7.5,leading=10),
        "ch":S("ch",fontName="Helvetica-Bold",fontSize=7.5,alignment=TA_CENTER,textColor=colors.white),
        "cd":S("cd",fontSize=8,leading=10),
        "cdr":S("cdr",fontSize=8,leading=10,alignment=TA_RIGHT),
        "cdc":S("cdc",fontSize=8,leading=10,alignment=TA_CENTER),}
    def Ps(t,s): return P(t,st[s])
    fname=f"vgm_mp_{doc_id:04d}.pdf"
    W=186*mm
    doc=SimpleDocTemplate(str(out_dir/fname),pagesize=A4,
                          leftMargin=15*mm,rightMargin=15*mm,topMargin=12*mm,bottomMargin=12*mm)
    story=[]
    story.append(Table([[Ps("VERIFIED GROSS MASS (VGM) — MULTI-CONTAINER DECLARATION","title")]],[W-6*mm]))
    story[-1].setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#1a1a2e")),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(Spacer(1,2*mm))
    hr=Table([[Ps("SHIPPER:","lbl"),Ps(shipper,"val"),Ps("B/L NO.:","lbl"),Ps(bl,"val")],
              [Ps("ADDRESS:","lbl"),Ps(addr,"sm"),Ps("BOOKING:","lbl"),Ps(booking,"val")],
              [Ps("PORT OF LOADING:","lbl"),Ps(pol,"val"),Ps("PORT OF DISCHARGE:","lbl"),Ps(pod,"val")]],
             [28*mm,62*mm,28*mm,58*mm])
    hr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F0F0F0")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#F0F0F0"))]))
    story.append(hr); story.append(Spacer(1,2*mm))
    CW=[28*mm,20*mm,14*mm,14*mm,18*mm,22*mm,22*mm,24*mm,24*mm]
    rows=[[Ps("Container No.","ch"),Ps("Seal No.","ch"),Ps("Size/Type","ch"),Ps("Method","ch"),
           Ps("Tare Wt\n(KGS)","ch"),Ps("Cargo Wt\n(KGS)","ch"),Ps("VGM\n(KGS)","ch"),
           Ps("Unit","ch"),Ps("Verified Date","ch")]]
    for c in containers:
        rows.append([Ps(c["no"],"cdc"),Ps(c["seal"],"cdc"),Ps(c["type"],"cdc"),
                     Ps(f"Method {c['method']}","cdc"),Ps(f"{c['tare']:,}","cdr"),
                     Ps(f"{c['cargo_wt']:,.1f}","cdr"),Ps(f"{c['vgm']:,.1f}","cdr"),
                     Ps(c["unit"],"cdc"),Ps(dt.strftime("%d %b %Y"),"cdc")])
    rows.append([Ps("TOTAL","ch")]+[Ps("","cdc")]*3+[Ps("","cdr"),
                 Ps(f"{sum(c['cargo_wt'] for c in containers):,.1f}","cdr"),
                 Ps(f"{sum(c['vgm'] for c in containers):,.1f}","cdr"),
                 Ps("KGS","cdc"),Ps("","cdc")])
    nc=len(containers)
    stripe=[("BACKGROUND",(0,r),(-1,r),colors.HexColor("#FAFAFA")) for r in range(1,nc+1) if r%2==0]
    vt=Table(rows,colWidths=CW,repeatRows=1)
    vt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1a1a2e")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#FFF3CD")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),.5,BORDER),("INNERGRID",(0,0),(-1,-1),.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]+stripe))
    story.append(vt); story.append(Spacer(1,3*mm))
    sig=fake.name(); pos=random.choice(["Logistics Manager","Export Compliance Officer"])
    story.append(Ps(f"I certify that the VGM weights above are accurate per SOLAS Regulation VI/2.\nAuthorized by: {sig}  |  Title: {pos}  |  Date: {dt.strftime('%d %b %Y')}","sm"))
    doc.build(story)
    ann={"document_id":fname.replace(".pdf",""),"document_class":"Verified Gross Mass",
         "class_index":6,"is_multipage":True,
         "fields":{"shipper":shipper,"bl":bl,"pol":pol,"pod":pod,
                   "n_containers":nc,"date":dt.strftime("%Y-%m-%d"),
                   "total_vgm_kg":round(sum(c["vgm"] for c in containers),1)}}
    (ann_dir/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return fname


# ══════════════════════════════════════════════════════════════════════════
# Registry + main
# ══════════════════════════════════════════════════════════════════════════
GENERATORS = {
    "02": ("House Bill of Lading",            gen_hbl, "02_House_Bill_of_Lading"),
    "04": ("Shipper's Letter of Instruction", gen_sli, "04_Shippers_Letter_of_Instruction"),
    "05": ("Dangerous Goods Declaration",     gen_dgd, "05_Dangerous_Goods_Declaration"),
    "06": ("Verified Gross Mass",             gen_vgm, "06_Verified_Gross_Mass"),
    "11": ("Import/Export License",           gen_eei, "11_Import_Export_License"),
}

def generate(count_per_class=300):
    print(f"Generating {count_per_class} 2-page docs for 5 additional classes -> {MP_DIR}/")
    import fitz
    for cls_idx, (cls_name, gen_fn, folder) in GENERATORS.items():
        out_dir = MP_DIR / folder / "pdfs"
        ann_dir = MP_DIR / folder / "annotations"
        out_dir.mkdir(parents=True, exist_ok=True)
        ann_dir.mkdir(parents=True, exist_ok=True)
        for f in list(out_dir.glob("*.pdf")) + list(ann_dir.glob("*.json")): f.unlink()
        print(f"\n  [{cls_idx}] {cls_name} ({count_per_class} docs)...")
        for i in range(1, count_per_class + 1):
            fname = gen_fn(i, out_dir, ann_dir)
            if i <= 2 or i % 100 == 0:
                d = fitz.open(str(out_dir / fname))
                print(f"    [{i:04d}] {fname}  ({len(d)} pages)")
                d.close()
    print("\nAll done. Multi-page pools:")
    for d in sorted(MP_DIR.iterdir()):
        if d.is_dir():
            pdfs = list(d.rglob("*.pdf"))
            if pdfs:
                import fitz as fz; pages=[len(fz.open(str(p))) for p in pdfs[:3]]
                print(f"  {d.name}: {len(pdfs)} docs, sample pages={pages}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=300)
    generate(p.parse_args().count)
