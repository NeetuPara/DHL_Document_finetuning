"""Import Entry Summary — CBP Form 7501 style (US Customs Entry Summary)."""
import json, random
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import fake, random, random_company, random_country, COMMODITY_CATEGORIES

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "11_Import_Export_License"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"
BORDER=colors.HexColor("#555555"); LN=colors.HexColor("#BBBBBB"); PAGE_W=186*mm

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=7.5,leading=9.5,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=11,alignment=TA_CENTER),
    "sub":S("s",fontSize=8,alignment=TA_CENTER),"fno":S("fn",fontName="Helvetica-Bold",fontSize=7),
    "lbl":S("l",fontSize=6.5,textColor=colors.HexColor("#555555")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=8),"sm":S("sm",fontSize=7,leading=9),
    "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER),
    "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,leading=9,alignment=TA_RIGHT),
    "cdc":S("cdc",fontSize=7,leading=9,alignment=TA_CENTER),}
def P(t,s="cd"): return Paragraph(str(t),ST[s])

ENTRY_TYPES=[("01","Consumption — Free"),("03","Consumption — Antidumping/Countervailing"),
             ("06","Consumption — Foreign Trade Zone"),("11","Informal — Free"),
             ("21","Warehouse"),("31","Warehouse Withdrawal — Consumption")]
PORTS_OF_ENTRY=["New York, NY (1001)","Los Angeles, CA (2704)","Chicago, IL (3901)","Miami, FL (5201)",
                "Houston, TX (5301)","Seattle, WA (3001)","Atlanta, GA (1703)","Boston, MA (0401)",
                "Detroit, MI (3801)","San Francisco, CA (2801)"]
COUNTRY_CODES=[("US","United States"),("DE","Germany"),("CN","China"),("JP","Japan"),
               ("GB","United Kingdom"),("KR","South Korea"),("IN","India"),("MX","Mexico"),
               ("CA","Canada"),("TW","Taiwan"),("VN","Vietnam"),("TH","Thailand")]
DUTY_RATES=["Free","2.5%","3.7%","5.0%","7.5%","10.0%","15.0%","20.0%","25.0%"]

def generate_one(doc_id):
    entry_type_code,entry_type_desc=random.choice(ENTRY_TYPES)
    entry_no=f"{random.randint(100,999)}-{fake.bothify('?######',letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"
    entry_date=fake.date_between(start_date="-2y",end_date="today")
    port_of_entry=random.choice(PORTS_OF_ENTRY)
    import_date=fake.date_between(start_date=entry_date,end_date="today")
    transport_mode=random.choice(["Air","Ocean","Truck","Rail"])
    carrier=random.choice(["Delta Air Lines","Maersk Line","UPS","FedEx","American Airlines","Lufthansa Cargo"])
    bl_awb=f"{random.randint(100,999)}-{random.randint(10000000,99999999)}"
    voyage=f"V{random.randint(100,999)}" if transport_mode=="Ocean" else f"Flt {random.randint(100,999)}"
    importer_name=random_company(); importer_addr=fake.address().replace("\n",", ")+", US"
    importer_ein=fake.bothify("##-#######"); importer_id=f"IMP-{random.randint(1000000,9999999)}"
    consignee_same=random.random()<0.6
    consignee_name=importer_name if consignee_same else random_company()
    broker_name=random.choice(["DHL Global Forwarding","Kuehne + Nagel Customs","CH Robinson","C.H. Powell Co."])
    broker_id=fake.bothify("##-######")
    origin_code,origin_country=random.choice(COUNTRY_CODES)
    n_items=random.randint(1,6)
    items=[]
    chosen=random.sample(COMMODITY_CATEGORIES,min(n_items,len(COMMODITY_CATEGORIES)))
    for cat in chosen:
        qty=random.randint(10,500); unit=cat["unit"]
        val=round(random.uniform(500,50000),2); wt=round(random.uniform(50,2000),2)
        duty_rate=random.choice(DUTY_RATES)
        duty_amt=round(val*float(duty_rate.replace("%","").replace("Free","0"))/100,2) if duty_rate!="Free" else 0
        items.append({"hts_no":cat["hs_code"],"description":cat["description"],
                      "country_of_origin":origin_country,"qty":qty,"unit":unit,
                      "entered_value":val,"gross_weight":wt,"duty_rate":duty_rate,"duty_amount":duty_amt})
    total_val=round(sum(i["entered_value"] for i in items),2)
    total_duty=round(sum(i["duty_amount"] for i in items),2)
    total_wt=round(sum(i["gross_weight"] for i in items),2)
    bond_no=f"BD-{random.randint(1000000,9999999)}"

    fname=f"entry_summary_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]

    # Title
    tb=Table([[P("U.S. CUSTOMS AND BORDER PROTECTION","sub")],
              [P("ENTRY SUMMARY — CBP Form 7501","title")]],
             colWidths=[PAGE_W])
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),colors.HexColor("#002868")),
        ("TEXTCOLOR",(0,0),(0,0),colors.white),
        ("BACKGROUND",(0,1),(0,1),colors.HexColor("#BF0A30")),
        ("TEXTCOLOR",(0,1),(0,1),colors.white),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(tb); story.append(Spacer(1,1*mm))

    # Entry header
    eh=Table([[P("1. ENTRY NO.","lbl"),P(entry_no,"val"),P("2. ENTRY TYPE","lbl"),P(f"{entry_type_code} — {entry_type_desc}","sm"),
               P("3. SUMMARY DATE","lbl"),P(entry_date.strftime("%m/%d/%Y"),"val")],
              [P("4. PORT OF ENTRY","lbl"),P(port_of_entry,"sm"),P("5. ENTRY DATE","lbl"),P(import_date.strftime("%m/%d/%Y"),"val"),
               P("6. BOND NO.","lbl"),P(bond_no,"sm")]],
             colWidths=[22*mm,36*mm,26*mm,46*mm,28*mm,28*mm])
    eh.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),3),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,-1),colors.HexColor("#EEEEEE"))]))
    story.append(eh); story.append(Spacer(1,1*mm))

    # Transport
    tr=Table([[P("7. MODE OF TRANSPORT","lbl"),P(transport_mode,"val"),P("8. CARRIER","lbl"),P(carrier,"val"),
               P("9. B/L OR AWB NO.","lbl"),P(bl_awb,"val")],
              [P("10. VOYAGE/FLIGHT/TRIP NO.","lbl"),P(voyage,"val"),
               P("11. COUNTRY OF ORIGIN","lbl"),P(f"{origin_country} ({origin_code})","val"),
               P("12. GROSS WEIGHT (KG)","lbl"),P(f"{total_wt:,.2f}","val")]],
             colWidths=[38*mm,28*mm,18*mm,46*mm,30*mm,26*mm])
    tr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),3),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,-1),colors.HexColor("#EEEEEE"))]))
    story.append(tr); story.append(Spacer(1,1*mm))

    # Importer / Consignee / Broker
    ic=Table([[
        [P("13. IMPORTER OF RECORD","lbl"),P(importer_name,"val"),P(importer_addr,"sm"),P(f"EIN: {importer_ein}","sm"),P(f"Importer ID: {importer_id}","sm")],
        [P("14. CONSIGNEE","lbl"),P(consignee_name,"val"),P("(same as importer)" if consignee_same else "","sm")],
        [P("15. CUSTOMS BROKER","lbl"),P(broker_name,"val"),P(f"License: {broker_id}","sm"),P(f"Contact: {fake.name()}","sm"),P(f"Tel: {fake.phone_number()}","sm")],
    ]],colWidths=[66*mm,66*mm,54*mm])
    ic.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(ic); story.append(Spacer(1,1*mm))

    # Line items
    rows=[[P("16. HTS No.","ch"),P("17. Description of Merchandise","ch"),P("18. Country\nof Origin","ch"),
           P("19. Qty","ch"),P("20. Unit","ch"),P("21. Entered\nValue (USD)","ch"),
           P("22. Duty\nRate","ch"),P("23. Duty\nAmount (USD)","ch")]]
    for it in items:
        rows.append([P(it["hts_no"],"cdc"),P(it["description"],"cd"),P(it["country_of_origin"],"cdc"),
                     P(it["qty"],"cdc"),P(it["unit"],"cdc"),P(f"{it['entered_value']:,.2f}","cdr"),
                     P(it["duty_rate"],"cdc"),P(f"{it['duty_amount']:,.2f}","cdr")])
    rows.append([P("TOTALS","ch"),P("","cd"),P("","cdc"),P("","cdc"),P("","cdc"),
                 P(f"{total_val:,.2f}","cdr"),P("","cdc"),P(f"{total_duty:,.2f}","cdr")])
    it_t=Table(rows,colWidths=[22*mm,60*mm,24*mm,12*mm,10*mm,22*mm,14*mm,22*mm],repeatRows=1)
    it_t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#002868")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EEEEEE")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(it_t); story.append(Spacer(1,2*mm))

    # Certification
    cert=Table([[P(f"I declare that the information shown above is accurate and complete to the best of my knowledge.\n"
                   f"Broker/Importer Signature: ___________________________     Date: {entry_date.strftime('%m/%d/%Y')}","sm")]],
               colWidths=[PAGE_W])
    cert.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(cert)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Import Entry Summary (CBP 7501)","class_index":11,
         "fields":{"entry_number":entry_no,"entry_type":entry_type_desc,"entry_date":entry_date.strftime("%Y-%m-%d"),
                   "port_of_entry":port_of_entry,"import_date":import_date.strftime("%Y-%m-%d"),
                   "transport_mode":transport_mode,"carrier":carrier,"bl_awb":bl_awb,
                   "country_of_origin":origin_country,"gross_weight_kg":total_wt,
                   "importer_name":importer_name,"importer_ein":importer_ein,
                   "consignee_name":consignee_name,"customs_broker":broker_name,
                   "total_entered_value_usd":total_val,"total_duty_usd":total_duty,
                   "line_items":items}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} Entry Summary documents...")
    for i in range(1,count+1):
        a=generate_one(i); f=a["fields"]
        print(f"  [{i:04d}] {f['entry_number']}  USD {f['total_entered_value_usd']:,.2f}  Duty: USD {f['total_duty_usd']:,.2f}")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
