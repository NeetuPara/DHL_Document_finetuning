"""U.S. Shipper's Letter of Instructions — matches DHL Global Forwarding SLI layout."""
import json, random
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country, INCOTERMS, CURRENCIES)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "04_Shippers_Letter_of_Instruction"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"
BORDER=colors.HexColor("#555555"); LN=colors.HexColor("#BBBBBB"); PAGE_W=186*mm

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=8,leading=10,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=12,alignment=TA_CENTER),
    "sub":S("sb",fontSize=7.5,alignment=TA_CENTER),
    "hdr":S("h",fontName="Helvetica-Bold",fontSize=7,textColor=colors.HexColor("#1a1a2e"),leading=9),
    "lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=8),
    "sm":S("sm",fontSize=7,leading=9),"note":S("nt",fontSize=6.5,leading=9,textColor=colors.HexColor("#444444")),
    "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER),
    "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,alignment=TA_RIGHT,leading=9),}
def P(t,s="cd"): return Paragraph(str(t),ST[s])
def lv(l,v): return [P(l,"lbl"),P(v,"val")]
def cb(checked): return "[X]" if checked else "[ ]"

SCHEDULE_B=[("8471.30.0100","Portable computers"),("8534.00.0000","Printed circuit boards"),
            ("6203.42.4011","Men's trousers"),("8708.30.5010","Disc brakes"),
            ("3926.90.9990","Other plastic articles"),("9018.31.0040","Medical syringes"),
            ("2008.19.9000","Prepared nuts/seeds"),("8518.30.2000","Headphones"),
            ("5407.42.0000","Woven synthetic fabric"),("7208.37.0030","Hot-rolled steel")]
ECCN=["EAR99","5E992","5A992","7A994","3A992","0A988","2B350","1C010","9A515","ITAR"]
SERVICES=["Air","Ocean","Ground"]

def generate_one(doc_id):
    sc=random_country(); dc=random_country()
    while dc[1]==sc[1]: dc=random_country()
    usppi_name=random_company(); usppi_addr=fake.address().replace("\n",", ")+f", US"
    usppi_ein=fake.bothify("##-#######"); usppi_phone=fake.phone_number()
    consignee_name=random_company(); consignee_addr=fake.address().replace("\n",", ")+f", {dc[0]}"
    consignee_phone=fake.phone_number()
    notify_name=random_company(); notify_phone=fake.phone_number()
    svc=random.choice(SERVICES); consolidated=random.random()<0.5
    inco=random.choice(INCOTERMS); named_port=random.choice(["New York","Los Angeles","Chicago","Miami","Houston"])
    dgds=random.random()<0.15; perishable=random.random()<0.1; routed=random.random()<0.2
    insurance=random.random()<0.3; ins_value=round(random.uniform(1000,50000),2) if insurance else 0
    ref=f"SLI-{fake.date_this_decade().strftime('%Y%m')}-{random.randint(1000,9999)}"
    issue_date=fake.date_between(start_date="-2y",end_date="today")
    n_items=random.randint(1,5)
    items=[]
    for _ in range(n_items):
        sb_code,sb_desc=random.choice(SCHEDULE_B)
        qty=random.randint(10,1000); unit=random.choice(["PCS","KGS","LBS","CTN"])
        wt=round(random.uniform(5,500),2); val=round(random.uniform(100,50000),2)
        dom_for=random.choice(["D","F"])
        items.append({"marks":f"Mark {random.randint(1,99)}","description":sb_desc,"schedule_b":sb_code,
                      "dom_for":dom_for,"qty":qty,"unit":unit,"weight_kg":wt,"value_usd":val})
    license_type=random.choice(["NLR","Exception","License"])
    license_no=f"D{random.randint(100000,999999)}" if license_type=="License" else ""
    eccn_val=random.choice(ECCN); origin_state=fake.state_abbr()
    dest_country=dc[0]; payment=random.choice(["Open Account","Letter of Credit","Sight Draft"])
    signatory=fake.name(); sig_title=random.choice(["Export Manager","Compliance Officer","Trade Director"])
    sig_date=issue_date

    fname=f"sli_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]

    # Title
    tb=Table([[P("U.S. SHIPPER'S LETTER OF INSTRUCTIONS","title")],
              [P("DHL Global Forwarding — Licensed Customs Broker and Freight Forwarder","sub")]],
             colWidths=[PAGE_W])
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",(0,0),(0,0),colors.white),("FONTNAME",(0,0),(0,0),"Helvetica-Bold"),
        ("BACKGROUND",(0,1),(0,1),colors.HexColor("#EEEEEE")),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("BOX",(0,0),(-1,-1),0.5,BORDER)]))
    story.append(tb); story.append(Spacer(1,1*mm))

    # Date / Ref
    dr=Table([[P("DATE","lbl"),P(issue_date.strftime("%d %b %Y"),"val"),
               P("SHIPPER'S REFERENCE NUMBER","lbl"),P(ref,"val"),
               P("DHL WAYBILL NO.","lbl"),P("(To be assigned by DHL)","sm")]],
             colWidths=[16*mm,32*mm,48*mm,36*mm,32*mm,22*mm])
    dr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),3),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,0),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,0),colors.HexColor("#EEEEEE"))]))
    story.append(dr); story.append(Spacer(1,1*mm))

    # Parties
    parties=Table([[
        [P("1a. U.S. PRINCIPAL PARTY IN INTEREST (USPPI)","hdr"),
         P(f"Complete Name: {usppi_name}","sm"),P(f"Address: {usppi_addr}","sm"),
         P(f"Phone: {usppi_phone}","sm"),P(f"EIN: {usppi_ein}","sm")],
        [P("Service Requested:","hdr"),
         P(f"{cb(svc=='Air')} Air   {cb(svc=='Ocean')} Ocean   {cb(svc=='Ground')} Ground","sm"),
         P(f"{cb(consolidated)} Consolidated   {cb(not consolidated)} Direct","sm"),
         Spacer(1,3*mm),P("PARTIES TO TRANSACTION:","hdr"),
         P(f"[ ] Related   [X] Non-Related","sm")],
    ]],colWidths=[110*mm,76*mm])
    parties.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(parties); story.append(Spacer(1,1*mm))

    # Consignee
    cons=Table([[
        [P("2a. ULTIMATE CONSIGNEE","hdr"),P(consignee_name,"val"),P(consignee_addr,"sm"),P(f"Tel: {consignee_phone}","sm")],
        [P("3a. NOTIFY PARTY / INTERMEDIATE CONSIGNEE","hdr"),P(notify_name,"val"),P(f"Tel: {notify_phone}","sm"),
         Spacer(1,3*mm),
         P("CHARGES:","hdr"),
         P("Freight: [ ] Prepaid  [X] Collect","sm"),P("Handling: [X] Prepaid  [ ] Collect","sm")],
    ]],colWidths=[110*mm,76*mm])
    cons.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(cons); story.append(Spacer(1,1*mm))

    # Conditions + Incoterms
    cond=Table([[
        [P("SHIPMENT CONDITIONS","hdr"),
         P(f"4. Dangerous Goods:  {cb(dgds)} No  {cb(not dgds)} Yes","sm"),
         P(f"5. Perishable:  {cb(perishable)} No  {cb(not perishable)} Yes","sm"),
         P(f"7. Routed Export:  {cb(routed)} No  {cb(not routed)} Yes","sm"),
         P(f"8. Insurance:  {cb(insurance)} No  {cb(not insurance)} Yes"+(f"  USD {ins_value:,.2f}" if insurance else ""),"sm")],
        [P("10. INCOTERMS","hdr"),P(f"[X] {inco}","val"),P(f"Named Port/Place: {named_port}","sm"),
         Spacer(1,3*mm),P("11. EMERGENCY CONTACT IF UNABLE TO DELIVER","hdr"),
         P(f"Name: {fake.name()}","sm"),P(f"Phone: {fake.phone_number()}","sm")],
    ]],colWidths=[110*mm,76*mm])
    cond.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(cond); story.append(Spacer(1,1*mm))

    # Items table
    cols=[[P("(12)\nMarks & Nos","ch"),P("(13)\nDescription of Commodities","ch"),
           P("(14)\nD/F","ch"),P("(15)\nSchedule B Number","ch"),
           P("(16)\nQty / Unit","ch"),P("(17)\nWeight (KG)","ch"),P("(18)\nValue (USD)","ch")]]
    for it in items:
        cols.append([P(it["marks"],"cd"),P(it["description"],"cd"),P(it["dom_for"],"cdr"),
                     P(it["schedule_b"],"cdr"),P(f"{it['qty']} {it['unit']}","cdr"),
                     P(f"{it['weight_kg']:,.2f}","cdr"),P(f"{it['value_usd']:,.2f}","cdr")])
    for _ in range(max(0,5-len(items))): cols.append([P("")]*7)
    it_t=Table(cols,colWidths=[18*mm,60*mm,10*mm,28*mm,22*mm,22*mm,26*mm],repeatRows=1)
    it_t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(it_t); story.append(Spacer(1,1*mm))

    # Export control / destination
    ec=Table([[P(f"19. US EXPORT CONTROL: {cb(license_type=='NLR')} NLR  {cb(license_type=='Exception')} Exception  {cb(license_type=='License')} License  {license_no}","sm"),
               P(f"20. STATE OF ORIGIN: {origin_state}","sm"),P(f"21. COUNTRY OF DESTINATION: {dest_country}","sm")],
              [P(f"22. ECCN: {eccn_val}","sm"),P(f"23. PAYMENT TERMS: {payment}","sm"),P("","sm")]],
             colWidths=[80*mm,54*mm,52*mm])
    ec.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4)]))
    story.append(ec); story.append(Spacer(1,2*mm))

    # Signature
    sg=Table([[P(f"Signature: __________________________","sm"),P(f"Title: {sig_title}","sm"),P(f"Date: {sig_date.strftime('%d %b %Y')}","sm")],
              [P(f"Name: {signatory}","sm"),P(f"Company: {usppi_name}","sm"),P("","sm")]],
             colWidths=[70*mm,70*mm,46*mm])
    sg.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(sg)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Shipper's Letter of Instruction","class_index":4,
         "fields":{"reference":ref,"issue_date":issue_date.strftime("%Y-%m-%d"),
                   "usppi_name":usppi_name,"usppi_address":usppi_addr,"usppi_ein":usppi_ein,
                   "consignee_name":consignee_name,"consignee_address":consignee_addr,
                   "service":svc,"incoterm":inco,"named_port":named_port,
                   "dangerous_goods":dgds,"insurance":insurance,"insurance_value":ins_value,
                   "license_type":license_type,"license_no":license_no,"eccn":eccn_val,
                   "destination_country":dest_country,"payment_terms":payment,
                   "signatory":signatory,"title":sig_title,
                   "line_items":items}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} SLI documents...")
    for i in range(1,count+1):
        a=generate_one(i); f=a["fields"]
        print(f"  [{i:04d}] {f['reference']}  {f['service']}  -> {f['destination_country']}")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
