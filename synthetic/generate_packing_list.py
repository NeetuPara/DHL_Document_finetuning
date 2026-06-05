"""Packing List — matches DHL Global Forwarding UK template layout."""
import json, random
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country, random_invoice_number,
    random_bl_number, PACKAGE_TYPES, INCOTERMS, CURRENCIES, COMMODITY_CATEGORIES)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "08_Packing_List"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"
BORDER=colors.HexColor("#555555"); LN=colors.HexColor("#BBBBBB"); PAGE_W=186*mm

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=8,leading=10,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=14,alignment=TA_CENTER),
    "lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=8),"sm":S("sm",fontSize=7,leading=9),
    "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER),
    "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,leading=9,alignment=TA_RIGHT),
    "cdc":S("cdc",fontSize=7,leading=9,alignment=TA_CENTER),}
def P(t,s="cd"): return Paragraph(str(t),ST[s])

def generate_one(doc_id):
    sc=random_country(); dc=random_country()
    while dc[1]==sc[1]: dc=random_country()
    shipper=random_company(); sh_addr=fake.address().replace("\n",", ")+f", {sc[0]}"
    consignee=random_company(); cn_addr=fake.address().replace("\n",", ")+f", {dc[0]}"
    inv_no=random_invoice_number(); ref=f"PL-{random.randint(100000,999999)}"
    bl_awb=random.choice([random_bl_number(),f"{random.randint(100,999)}-{random.randint(10000000,99999999)}"])
    issue_date=fake.date_between(start_date="-2y",end_date="today")
    mode=random.choice(["Air Freight","Sea Freight","Road Freight","Express Courier"])
    carrier=random.choice(["DHL Global Forwarding","Maersk Line","CMA CGM","MSC","Hapag-Lloyd","Emirates SkyCargo"])
    inco=random.choice(INCOTERMS); currency=random.choice(CURRENCIES)
    n_items=random.randint(3,10)
    chosen=random.sample(COMMODITY_CATEGORIES,min(n_items,len(COMMODITY_CATEGORIES)))
    items=[]
    pkg_no=1
    for cat in chosen:
        n_pkgs=random.randint(1,20); pkg_type=random.choice(PACKAGE_TYPES)
        qty_per=random.randint(1,100); net_per=round(random.uniform(0.5,20),2)
        net_total=round(n_pkgs*net_per,2); grs_total=round(net_total*random.uniform(1.05,1.2),2)
        l=round(random.uniform(20,120)); w=round(random.uniform(15,80)); h=round(random.uniform(10,60))
        cbm=round(n_pkgs*(l/100)*(w/100)*(h/100),3)
        items.append({"pkg_no":f"{pkg_no}-{pkg_no+n_pkgs-1}","n_pkgs":n_pkgs,"pkg_type":pkg_type,
                      "description":cat["description"],"hs_code":cat["hs_code"],
                      "net_weight":net_total,"gross_weight":grs_total,
                      "dims":f"{l}x{w}x{h}cm","cbm":cbm,"origin":sc[0]})
        pkg_no+=n_pkgs
    total_pkgs=sum(i["n_pkgs"] for i in items)
    total_net=round(sum(i["net_weight"] for i in items),2)
    total_grs=round(sum(i["gross_weight"] for i in items),2)
    total_cbm=round(sum(i["cbm"] for i in items),3)
    signatory=fake.name(); position=random.choice(["Logistics Manager","Export Coordinator","Warehouse Supervisor"])

    fname=f"packing_list_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=12*mm,bottomMargin=12*mm)
    story=[]

    # Title
    tb=Table([[P("PACKING LIST","title")]],colWidths=[PAGE_W])
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#EEEEEE")),
        ("BOX",(0,0),(-1,-1),0.8,BORDER),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story.append(tb); story.append(Spacer(1,2*mm))

    # Header: shipper / consignee / shipment details
    hdr=Table([[
        [P("SHIPPER / EXPORTER","lbl"),P(shipper,"val"),P(sh_addr,"sm")],
        [P("CONSIGNEE","lbl"),P(consignee,"val"),P(cn_addr,"sm")],
        [P("INVOICE NUMBER","lbl"),P(inv_no,"val"),Spacer(1,1*mm),
         P("PACKING LIST REF","lbl"),P(ref,"val"),Spacer(1,1*mm),
         P("DATE","lbl"),P(issue_date.strftime("%d %b %Y"),"val"),Spacer(1,1*mm),
         P("B/L OR AWB NUMBER","lbl"),P(bl_awb,"val")],
    ]],colWidths=[66*mm,66*mm,54*mm])
    hdr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(hdr); story.append(Spacer(1,1*mm))

    # Mode / carrier / terms
    mc=Table([[P("MODE OF TRANSPORT","lbl"),P(mode,"val"),P("CARRIER","lbl"),P(carrier,"val"),
               P("INCOTERMS","lbl"),P(inco,"val"),P("CURRENCY","lbl"),P(currency,"val")]],
             colWidths=[36*mm,36*mm,18*mm,34*mm,22*mm,18*mm,18*mm,24*mm])
    mc.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,0),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(6,0),(6,0),colors.HexColor("#EEEEEE"))]))
    story.append(mc); story.append(Spacer(1,1*mm))

    # Items table
    CW=[18*mm,10*mm,18*mm,48*mm,20*mm,18*mm,18*mm,18*mm,18*mm]
    rows=[[P("Package\nMark & No.","ch"),P("No.\nPkgs","ch"),P("Package\nType","ch"),
           P("Description of Goods","ch"),P("HS Code","ch"),
           P("Net Wt\n(KG)","ch"),P("Gross Wt\n(KG)","ch"),P("Dimensions","ch"),P("Volume\n(CBM)","ch")]]
    for it in items:
        rows.append([P(it["pkg_no"],"cdc"),P(it["n_pkgs"],"cdc"),P(it["pkg_type"],"cdc"),
                     P(it["description"],"cd"),P(it["hs_code"],"cdc"),
                     P(f"{it['net_weight']:,.2f}","cdr"),P(f"{it['gross_weight']:,.2f}","cdr"),
                     P(it["dims"],"cdc"),P(f"{it['cbm']:.3f}","cdr")])
    # Totals row
    rows.append([P("TOTAL","ch"),P(str(total_pkgs),"cdc"),P("","cdc"),P("","cd"),P("","cdc"),
                 P(f"{total_net:,.2f}","cdr"),P(f"{total_grs:,.2f}","cdr"),P("","cdc"),P(f"{total_cbm:.3f}","cdr")])
    it_t=Table(rows,colWidths=CW,repeatRows=1)
    ts=TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EEEEEE")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE")])
    for r in range(1,len(items)+1):
        if r%2==0: ts.add("BACKGROUND",(0,r),(-1,r),colors.HexColor("#FAFAFA"))
    it_t.setStyle(ts)
    story.append(it_t); story.append(Spacer(1,3*mm))

    # Signature
    sg=Table([[P(f"Prepared by: {signatory}","sm"),P(f"Position: {position}","sm"),P(f"Date: {issue_date.strftime('%d %b %Y')}","sm")],
              [P("Signature: ___________________________","sm"),P(f"Company: {shipper}","sm"),P("Company Stamp:","sm")]],
             colWidths=[66*mm,66*mm,54*mm])
    sg.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(sg)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Packing List","class_index":8,
         "fields":{"shipper_name":shipper,"shipper_address":sh_addr,
                   "consignee_name":consignee,"consignee_address":cn_addr,
                   "invoice_number":inv_no,"reference":ref,"bl_awb":bl_awb,
                   "issue_date":issue_date.strftime("%Y-%m-%d"),"mode_of_transport":mode,
                   "carrier":carrier,"incoterms":inco,"currency":currency,
                   "total_packages":total_pkgs,"total_net_weight_kg":total_net,
                   "total_gross_weight_kg":total_grs,"total_cbm":total_cbm,
                   "signatory":signatory,"position":position,"items":items}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} Packing List documents...")
    for i in range(1,count+1):
        a=generate_one(i); f=a["fields"]
        print(f"  [{i:04d}] {f['invoice_number']}  {f['total_packages']} pkgs  {f['total_gross_weight_kg']} KG")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
