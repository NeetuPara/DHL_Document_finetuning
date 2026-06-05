"""
Certificate of Origin — Format 1: General/Chamber of Commerce style (Mohawk Global layout).
Shipper/Exporter + Consignee header, routing fields, goods table, sworn certification.
"""
import json, random, argparse
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_bl_number, random_invoice_number, PORTS_SEA)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "03_Certificate_of_Origin"
PDF_DIR  = OUT_DIR / "pdfs" / "format1_general"
ANN_DIR  = OUT_DIR / "annotations" / "format1_general"

BORDER = colors.HexColor("#555555"); LN = colors.HexColor("#BBBBBB")
TITLE_BG = colors.HexColor("#CCCCCC"); HDR_BG = colors.HexColor("#AAAAAA")
PAGE_W = 186*mm

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=8,leading=10,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=16,alignment=TA_CENTER),
    "sub":S("s",fontSize=8,alignment=TA_CENTER,textColor=colors.HexColor("#333333")),
    "lbl":S("l",fontSize=7,fontName="Helvetica-Bold",textColor=colors.HexColor("#333333")),
    "val":S("v",fontSize=8),"sm":S("sm",fontSize=7,leading=9),
    "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER),
    "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,leading=9,alignment=TA_CENTER),
    "cert":S("cert",fontSize=7.5,leading=11),
    "sig_lbl":S("sl",fontSize=7.5,fontName="Helvetica-Bold")}

def P(t,s="cd"): return Paragraph(str(t),ST[s])
def lv(l,v): return [P(l,"lbl"),P(v,"val")]
def addr_blk(hdr,name,addr): return [P(hdr,"lbl"),P(name,"val"),P(addr,"sm")]

COMMODITY_DESCS = [
    "Electronic Components — Printed Circuit Boards and Integrated Circuits",
    "Textile Products — Cotton Fabric and Garments",
    "Machinery Parts — Steel Gears and Drive Shafts",
    "Agricultural Products — Processed Grains and Cereals",
    "Chemical Products — Industrial Solvents and Resins",
    "Consumer Electronics — Mobile Phone Accessories",
    "Pharmaceutical Raw Materials — Active Ingredients",
    "Automotive Components — Brake Systems and Suspension Parts",
    "Furniture — Wooden Office and Home Furniture",
    "Plastic Products — Injection-Moulded Consumer Goods",
]

def generate_one(doc_id):
    sc=random_country(); cc=random_country()
    while cc[1]==sc[1]: cc=random_country()
    sn=random_company(); sa=fake.address().replace("\n",", ")+f", {sc[0]}"
    cn=random_company(); ca=fake.address().replace("\n",", ")+f", {cc[0]}"
    fwd=random.choice(["DHL Global Forwarding","Kuehne + Nagel","DB Schenker","Panalpina","Expeditors International"])
    fwd_ref=f"FWD-{random.randint(10000,99999)}"
    doc_no=f"COO-{fake.date_this_decade().strftime('%Y%m')}-{random.randint(1000,9999)}"
    bl_awb=random_bl_number()
    pol=random.choice(PORTS_SEA); pod=random.choice(PORTS_SEA)
    while pod==pol: pod=random.choice(PORTS_SEA)
    vessel=f"{random.choice(['MV','SS','CMA','MSC'])} {fake.last_name().upper()}"
    issue_date=fake.date_between(start_date="-2y",end_date="today")
    n_items=random.randint(1,5)
    items=[]
    for _ in range(n_items):
        desc=random.choice(COMMODITY_DESCS)
        n_pkgs=random.randint(10,500)
        pkg_type=random.choice(["Cartons","Pallets","Cases","Drums","Bags"])
        gw=round(random.uniform(50,5000),2)
        cbm=round(random.uniform(0.5,20),3)
        items.append({"marks":f"{random.choice(['ABC','XYZ','GLB'])}/{random.randint(1,99)}",
                      "n_pkgs":n_pkgs,"pkg_type":pkg_type,"description":desc,
                      "gross_weight":gw,"cbm":cbm,"origin":sc[0]})
    cert_text=(f"The undersigned {sn}, does hereby declare that the above mentioned goods were "
               f"manufactured and/or produced in {sc[0]} and that the information stated herein is true and correct.")
    day_words=["first","second","third","fourth","fifth","sixth","seventh","eighth","ninth","tenth",
               "eleventh","twelfth","thirteenth","fourteenth","fifteenth"]
    day_word=random.choice(day_words)
    month_name=issue_date.strftime("%B")
    year=issue_date.year
    signatory=fake.name()
    chamber=f"Chamber of Commerce and Industry, {random.choice(['New York','London','Hamburg','Singapore','Sydney'])}"

    fname=f"coo_general_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=12*mm,bottomMargin=12*mm)
    story=[]

    # Title
    tb=Table([[P("CERTIFICATE OF ORIGIN","title")],[P("Issued by Chamber of Commerce","sub")]],
             colWidths=[PAGE_W])
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),TITLE_BG),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("BOX",(0,0),(-1,-1),0.8,BORDER)]))
    story.append(tb); story.append(Spacer(1,2*mm))

    # Header info: Shipper/Doc#/BL
    h1=Table([[
        addr_blk("SHIPPER / EXPORTER",sn,sa),
        lv("DOCUMENT NO.",doc_no)+[Spacer(1,2*mm)]+lv("B/L OR AWB NUMBER",bl_awb),
    ]],colWidths=[100*mm,86*mm])
    h1.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(h1); story.append(Spacer(1,1*mm))

    # Consignee / Forwarder
    h2=Table([[
        addr_blk("CONSIGNED TO",cn,ca),
        [P("FORWARDING AGENT - REFERENCES","lbl"),P(fwd,"val"),P(fwd_ref,"sm"),
         Spacer(1,3*mm),P("POINT OF ORIGIN / COUNTRY","lbl"),P(sc[0],"val")],
    ]],colWidths=[100*mm,86*mm])
    h2.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(h2); story.append(Spacer(1,1*mm))

    # Routing
    rou=Table([[P("EXPORTING CARRIER","lbl"),P(vessel,"val"),
                P("PORT OF LOADING / EXPORT","lbl"),P(pol,"val")],
               [P("PORT OF DISCHARGE","lbl"),P(pod,"val"),
                P("COUNTRY OF DESTINATION","lbl"),P(cc[0],"val")]],
              colWidths=[40*mm,52*mm,42*mm,52*mm])
    rou.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F0F0F0")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#F0F0F0"))]))
    story.append(rou); story.append(Spacer(1,1*mm))

    # Goods table (shaded header)
    tb2=Table([[P("PARTICULARS FURNISHED BY SHIPPER","ch")]],colWidths=[PAGE_W])
    tb2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),HDR_BG),("TEXTCOLOR",(0,0),(-1,-1),colors.white),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("BOX",(0,0),(-1,-1),0.5,BORDER)]))
    story.append(tb2)

    goods_rows=[[P("MARKS AND NUMBERS","ch"),P("NO. OF PKGS.","ch"),
                 P("DESCRIPTION OF COMMODITIES AND GOODS","ch"),P("GROSS WEIGHT (KG)","ch"),P("CBM","ch")]]
    for it in items:
        goods_rows.append([P(it["marks"],"cdr"),P(f"{it['n_pkgs']} {it['pkg_type']}","cdr"),
                           P(it["description"],"cd"),P(f"{it['gross_weight']:,.2f}","cdr"),P(f"{it['cbm']:.3f}","cdr")])
    for _ in range(max(0,6-len(items))): goods_rows.append([P("")]*5)
    # Totals
    tot_pkgs=sum(i["n_pkgs"] for i in items); tot_gw=round(sum(i["gross_weight"] for i in items),2)
    tot_cbm=round(sum(i["cbm"] for i in items),3)
    goods_rows.append([P("TOTAL","ch"),P(str(tot_pkgs),"cdr"),P("","cd"),P(f"{tot_gw:,.2f}","cdr"),P(f"{tot_cbm:.3f}","cdr")])
    gt=Table(goods_rows,colWidths=[28*mm,26*mm,82*mm,26*mm,24*mm],repeatRows=1)
    gt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#DDDDDD")),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EEEEEE")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(gt); story.append(Spacer(1,2*mm))

    # Certification
    cert_data=[[
        [P("DECLARATION BY SHIPPER / EXPORTER","lbl"),Spacer(1,2*mm),
         P(cert_text,"cert"),Spacer(1,3*mm),
         P(f"Dated at {issue_place if hasattr(locals(),'issue_place') else pol.split(',')[1].strip()} on the {day_word} day of {month_name} {year}.","cert"),
         Spacer(1,5*mm),P("SIGNATURE OF OWNER OR AGENT: ____________________________","cert"),
         Spacer(1,2*mm),P(f"Name: {signatory}","sm")],
        [P("CERTIFICATION BY CHAMBER OF COMMERCE","lbl"),Spacer(1,2*mm),
         P(f"The {chamber} has examined the manufacturer's invoice and the sworn statement of the shipper, "
           f"and certifies that the products named originated in {sc[0]}.","cert"),
         Spacer(1,10*mm),P("SECRETARY SIGNATURE: ____________________________","cert")],
    ]]
    cert_t=Table(cert_data,colWidths=[100*mm,86*mm])
    cert_t.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(cert_t)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Certificate of Origin",
         "format":"General / Chamber of Commerce","class_index":3,
         "fields":{"exporter_name":sn,"exporter_address":sa,"exporter_country":sc[0],
                   "consignee_name":cn,"consignee_address":ca,"consignee_country":cc[0],
                   "document_no":doc_no,"bl_awb":bl_awb,"forwarding_agent":fwd,
                   "port_of_loading":pol,"port_of_discharge":pod,"country_of_origin":sc[0],
                   "issue_date":issue_date.strftime("%Y-%m-%d"),"signatory":signatory,
                   "total_packages":tot_pkgs,"total_gross_weight":tot_gw,"total_cbm":tot_cbm,
                   "goods":items}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} COO (General) documents...")
    for i in range(1,count+1):
        a=generate_one(i)
        print(f"  [{i:04d}] {a['fields']['document_no']}  Origin: {a['fields']['country_of_origin']}")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
