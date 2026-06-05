"""Certificate of Origin — Format 2: Free Trade Agreement (FTA/USMCA style, numbered fields 1-10)."""
import json, random, argparse
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import fake, random, random_company, random_country

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "03_Certificate_of_Origin"
PDF_DIR  = OUT_DIR / "pdfs" / "format2_fta"
ANN_DIR  = OUT_DIR / "annotations" / "format2_fta"

BORDER=colors.HexColor("#555555"); LN=colors.HexColor("#BBBBBB")
PAGE_W=186*mm; HDR_BG=colors.HexColor("#CCCCCC")
FTA_AGREEMENTS=["USMCA / CUSMA","CPTPP","ASFTA","EU-Canada CETA","Australia-UK FTA","RCEP","ASEAN FTA"]
ORIGIN_CRITERIA={"A":"Wholly obtained or produced","B":"Regional value content ≥ 60% (Transaction Value) or ≥ 50% (Net Cost)",
                 "C":"Change in tariff classification","D":"Produced in the territory of one or more parties"}

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=8,leading=10,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=13,alignment=TA_CENTER),
    "sub":S("s",fontSize=8,alignment=TA_CENTER,textColor=colors.HexColor("#444444")),
    "fld":S("f",fontName="Helvetica-Bold",fontSize=7.5,textColor=colors.HexColor("#1a1a2e")),
    "lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=8),
    "sm":S("sm",fontSize=7,leading=9),"ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER),
    "cd":S("cd",fontSize=7,leading=9),"cdc":S("cdc",fontSize=7,leading=9,alignment=TA_CENTER),
    "cert":S("cert",fontSize=7.5,leading=11),}

def P(t,s="cd"): return Paragraph(str(t),ST[s])

HS_CODES=[("8534.00.00","Printed circuit boards"),("8471.30.00","Portable computers"),
          ("6203.42.40","Men's trousers of cotton"),("8708.30.00","Brakes and parts"),
          ("9018.31.00","Medical syringes"),("3926.90.00","Plastic articles"),
          ("7208.37.00","Flat-rolled steel"),("2008.19.00","Prepared nuts"),
          ("5407.42.00","Woven polyester fabric"),("9401.30.00","Wooden chairs"),
          ("8518.30.00","Earphones"),("8483.40.00","Gear mechanisms"),]

def generate_one(doc_id):
    exporter_c=random_country(); producer_c=random_country(); importer_c=random_country()
    en=random_company(); ea=fake.address().replace("\n",", ")+f", {exporter_c[0]}"
    pn=random_company(); pa=fake.address().replace("\n",", ")+f", {producer_c[0]}"
    iname=random_company(); ia=fake.address().replace("\n",", ")+f", {importer_c[0]}"
    fta=random.choice(FTA_AGREEMENTS)
    blanket=random.random()<0.4
    dt=fake.date_between(start_date="-2y",end_date="today")
    from datetime import timedelta
    bf_start = dt - timedelta(days=365)
    blanket_from = fake.date_between(start_date=bf_start, end_date=dt)
    bt_end = dt + timedelta(days=365)
    blanket_to = fake.date_between(start_date=dt, end_date=bt_end)
    certifier_type=random.choice(["Exporter","Producer","Importer"])
    signatory=fake.name(); title=random.choice(["Export Compliance Manager","Trade Director","Operations Manager"])
    company=en if certifier_type=="Exporter" else (pn if certifier_type=="Producer" else iname)
    phone=fake.phone_number()

    n_items=random.randint(1,6)
    items=[]
    chosen_hs=random.sample(HS_CODES,min(n_items,len(HS_CODES)))
    for hs_code,hs_desc in chosen_hs:
        crit=random.choice(list(ORIGIN_CRITERIA.keys()))
        qty=random.randint(50,5000)
        unit=random.choice(["KGS","PCS","MTR","CTN","LTR"])
        items.append({"hs_code":hs_code,"description":hs_desc,"origin_criterion":crit,
                      "producer":random.choice(["Various","Same as Exporter",pn]),
                      "quantity":qty,"unit":unit,"origin":exporter_c[0]})

    fname=f"coo_fta_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]

    # Header
    hdr=Table([[P(fta.upper()+" CERTIFICATE OF ORIGIN","title")],
               [P("For goods traded under the Free Trade Agreement","sub")],
               [P("Please Print or Type — Attach Supporting Documentation as Required","sub")]],
              colWidths=[PAGE_W])
    hdr.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),HDR_BG),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),3),("BOX",(0,0),(-1,-1),0.8,BORDER)]))
    story.append(hdr); story.append(Spacer(1,2*mm))

    # Certifier type + blanket
    cert_row=Table([[
        [P("CERTIFIER (check one):","fld"),
         P(f"[{'X' if certifier_type=='Exporter' else ' '}] Exporter     "
           f"[{'X' if certifier_type=='Producer' else ' '}] Producer     "
           f"[{'X' if certifier_type=='Importer' else ' '}] Importer","sm")],
        [P("BLANKET PERIOD:","fld"),
         P(f"[{'X' if blanket else ' '}] Blanket Certificate","sm"),
         P(f"From: {blanket_from.strftime('%d-%m-%Y') if blanket else 'N/A'}  "
           f"To: {blanket_to.strftime('%d-%m-%Y') if blanket else 'N/A'}","sm")],
    ]],colWidths=[100*mm,86*mm])
    cert_row.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),4),
        ("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(cert_row); story.append(Spacer(1,1*mm))

    # Fields 1-4
    f14=Table([[
        [P("1  EXPORTER'S NAME AND ADDRESS","fld"),P(en,"val"),P(ea,"sm"),Spacer(1,1*mm),P(f"Tax ID / EIN: {fake.bothify('##-#######')}","sm")],
        [P("2  PRODUCER'S NAME AND ADDRESS","fld"),P(pn,"val"),P(pa,"sm"),Spacer(1,1*mm),P(f"Tax ID: {fake.bothify('##-#######')}","sm")],
        [P("3  IMPORTER'S NAME AND ADDRESS","fld"),P(iname,"val"),P(ia,"sm")],
    ]],colWidths=[62*mm,62*mm,62*mm])
    f14.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(f14); story.append(Spacer(1,1*mm))

    # Fields 5-9 goods table
    story.append(P("DESCRIPTION OF GOODS — Fields 5 through 9","fld"))
    story.append(Spacer(1,1*mm))
    cols=[[P("5\nDescription of Goods","ch"),P("6\nHS Tariff Classification","ch"),
           P("7\nPreference Criterion","ch"),P("8\nProducer","ch"),P("9\nQuantity & Unit","ch")]]
    for it in items:
        cols.append([P(it["description"],"cd"),P(it["hs_code"],"cdc"),
                     P(f"{it['origin_criterion']}\n({ORIGIN_CRITERIA[it['origin_criterion']][:30]}...)","cd"),
                     P(it["producer"],"cd"),P(f"{it['quantity']} {it['unit']}","cdc")])
    gt=Table(cols,colWidths=[50*mm,30*mm,38*mm,36*mm,32*mm],repeatRows=1)
    gt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#DDDDDD")),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(gt); story.append(Spacer(1,2*mm))

    # Field 10 certification
    cert_text=(f"10  I certify that:\n"
               f"• The information on this document is true and accurate and I assume the responsibility for "
               f"proving such representations. I understand that I am liable for any false statements or "
               f"material omissions made on or in connection with this document;\n"
               f"• I agree to maintain and present upon request, documentation necessary to support this "
               f"Certificate, and to inform, in writing, all persons to whom the Certificate was given of "
               f"any changes that could affect the accuracy or validity of this Certificate;\n"
               f"• This Certificate consists of 1 page.")
    f10=Table([[P(cert_text,"cert")]],colWidths=[PAGE_W])
    f10.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("LEFTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(f10); story.append(Spacer(1,2*mm))

    # Signature block
    sg=Table([[P("Authorized Signature: ___________________________","sm"),P(f"Company: {company}","sm")],
              [P(f"Name: {signatory}","sm"),P(f"Title: {title}","sm")],
              [P(f"Date: {dt.strftime('%d-%m-%Y')}","sm"),P(f"Telephone: {phone}","sm")]],
             colWidths=[100*mm,86*mm])
    sg.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(sg)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Certificate of Origin",
         "format":"FTA / Trade Agreement","class_index":3,
         "fields":{"fta_agreement":fta,"certifier_type":certifier_type,"blanket_period":blanket,
                   "blanket_from":blanket_from.strftime("%Y-%m-%d") if blanket else None,
                   "blanket_to":blanket_to.strftime("%Y-%m-%d") if blanket else None,
                   "exporter_name":en,"exporter_address":ea,"exporter_country":exporter_c[0],
                   "producer_name":pn,"producer_country":producer_c[0],
                   "importer_name":iname,"importer_country":importer_c[0],
                   "issue_date":dt.strftime("%Y-%m-%d"),"signatory":signatory,"title":title,
                   "goods":items}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} COO (FTA) documents...")
    for i in range(1,count+1):
        a=generate_one(i); f=a["fields"]
        print(f"  [{i:04d}] {f['fta_agreement']}  {f['exporter_country']} -> {f['importer_country']}")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
