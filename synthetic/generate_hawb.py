"""House Air Waybill (HAWB) — IATA neutral AWB format."""
import json, random
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_hawb_number, random_mawb_number, AIRPORTS, CURRENCIES, COMMODITY_CATEGORIES)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "07_House_Airway_Bill"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"
BORDER=colors.HexColor("#555555"); LN=colors.HexColor("#BBBBBB"); PAGE_W=186*mm

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=8,leading=10,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=13,alignment=TA_CENTER),
    "awb_no":S("a",fontName="Helvetica-Bold",fontSize=11,alignment=TA_CENTER),
    "lbl":S("l",fontSize=6.5,textColor=colors.HexColor("#555555")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=8),
    "sm":S("sm",fontSize=7,leading=9),"ch":S("ch",fontName="Helvetica-Bold",fontSize=6.5,alignment=TA_CENTER),
    "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,leading=9,alignment=TA_RIGHT),
    "cdc":S("cdc",fontSize=7,leading=9,alignment=TA_CENTER),}
def P(t,s="cd"): return Paragraph(str(t),ST[s])

RATE_CLASSES={"Q":"Quantity Rate","B":"Basic ULD Rate","M":"Unit Load Device","C":"Specific Commodity","K":"Class Rate","Y":"Normal Rate"}
CHARGE_CODES={"PP":"Prepaid","CC":"Collect","XX":"Unknown"}

def generate_one(doc_id):
    sc=random_country(); dc=random_country()
    while dc[1]==sc[1]: dc=random_country()
    shipper=random_company(); sh_addr=fake.address().replace("\n",", ")+f", {sc[0]}"
    sh_phone=fake.phone_number(); sh_acct=f"{random.randint(10000000,99999999)}"
    consignee=random_company(); cn_addr=fake.address().replace("\n",", ")+f", {dc[0]}"
    cn_phone=fake.phone_number()
    agent="DHL Global Forwarding"; agent_iata=f"{random.randint(10,99)}-{random.randint(100000,999999)}"
    hawb=random_hawb_number(); mawb=random_mawb_number()
    dep_airport,dep_code=random.choice(AIRPORTS)
    dest_airport,dest_code=random.choice(AIRPORTS)
    while dest_code==dep_code: dest_airport,dest_code=random.choice(AIRPORTS)
    via1_name,via1_code=random.choice(AIRPORTS) if random.random()<0.5 else ("","")
    currency=random.choice(CURRENCIES)
    charge_code=random.choice(["PP","CC"])
    declared_carriage="NVD"  # No Value Declared (most common)
    declared_customs=round(random.uniform(100,50000),2) if random.random()<0.7 else 0
    issue_date=fake.date_between(start_date="-2y",end_date="today")
    n_pkgs=random.randint(1,50)
    gross_wt=round(random.uniform(5,2000),2)
    chargeable_wt=max(gross_wt,round(random.uniform(gross_wt*0.8,gross_wt*1.5),2))
    rate_class=random.choice(list(RATE_CLASSES.keys()))
    commodity_no=f"{random.randint(1000,9999)}.{random.randint(10,99)}"
    rate=round(random.uniform(1.5,15.0),2)
    total_charge=round(chargeable_wt*rate,2)
    nature_of_goods=random.choice([c["description"] for c in COMMODITY_CATEGORIES])
    dimensions=f"{random.randint(30,120)}x{random.randint(30,80)}x{random.randint(20,60)} cm"
    handling=random.choice(["","","Keep Upright","Keep Dry","Keep Cool 2-8°C","Handle with Care","Fragile"])
    signatory=fake.name()

    fname=f"hawb_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]

    # Title + AWB No.
    tb=Table([[P("HOUSE AIR WAYBILL","title")],
              [P("Issued by DHL Global Forwarding (NVOCC / Freight Forwarder)","sm")]],
             colWidths=[PAGE_W])
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",(0,0),(0,0),colors.white),
        ("BACKGROUND",(0,1),(0,1),colors.HexColor("#EEEEEE")),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(tb); story.append(Spacer(1,1*mm))

    # HAWB + MAWB numbers
    nb=Table([[P("HOUSE AIR WAYBILL NO.","lbl"),P(hawb,"awb_no"),P("MASTER AWB NO.","lbl"),P(mawb,"val")]],
             colWidths=[42*mm,52*mm,30*mm,62*mm])
    nb.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,0),colors.HexColor("#EEEEEE"))]))
    story.append(nb); story.append(Spacer(1,1*mm))

    # Shipper / Consignee / Agent
    sca=Table([[
        [P("SHIPPER'S NAME AND ADDRESS","lbl"),P(shipper,"val"),P(sh_addr,"sm"),
         P(f"Tel: {sh_phone}","sm"),P(f"Account No: {sh_acct}","sm")],
        [P("CONSIGNEE'S NAME AND ADDRESS","lbl"),P(consignee,"val"),P(cn_addr,"sm"),P(f"Tel: {cn_phone}","sm")],
        [P("ISSUING CARRIER'S AGENT NAME AND CITY","lbl"),P(agent,"val"),P(f"IATA Code: {agent_iata}","sm"),
         Spacer(1,2*mm),P("ACCOUNT NO.","lbl"),P(f"{random.randint(100000,999999)}","sm")],
    ]],colWidths=[66*mm,66*mm,54*mm])
    sca.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(sca); story.append(Spacer(1,1*mm))

    # Routing
    via_str=f"{via1_code} / " if via1_code else ""
    rt=Table([[P("AIRPORT OF DEPARTURE","lbl"),P(f"{dep_airport} ({dep_code})","val"),
               P("TO (FIRST CARRIER)","lbl"),P(f"{via_str}{dest_code}","val"),
               P("BY (CARRIER CODE)","lbl"),P(random.choice(["DL","LH","EK","SQ","QF","BA","AF"]),"val")],
              [P("REQUESTED ROUTING","lbl"),P(f"{dep_code} → {dest_code}","val"),
               P("AIRPORT OF DESTINATION","lbl"),P(f"{dest_airport} ({dest_code})","val"),
               P("FLIGHT DATE","lbl"),P(issue_date.strftime("%d %b %Y"),"val")]],
             colWidths=[36*mm,54*mm,28*mm,36*mm,20*mm,12*mm])
    rt.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,-1),colors.HexColor("#EEEEEE"))]))
    story.append(rt); story.append(Spacer(1,1*mm))

    # Value / Currency
    vc=Table([[P("CURRENCY","lbl"),P(currency,"val"),P("CHGS CODE","lbl"),P(charge_code,"val"),
               P("DECLARED VALUE FOR CARRIAGE","lbl"),P(declared_carriage,"val"),
               P(f"DECLARED VALUE FOR CUSTOMS ({currency})","lbl"),P(f"{declared_customs:,.2f}" if declared_customs else "NCV","val")]],
             colWidths=[20*mm,16*mm,18*mm,12*mm,40*mm,20*mm,44*mm,16*mm])
    vc.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),3),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,0),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(6,0),(6,0),colors.HexColor("#EEEEEE"))]))
    story.append(vc); story.append(Spacer(1,1*mm))

    # Rate table
    rh=[P("NO. OF\nPIECES","ch"),P("GROSS\nWEIGHT","ch"),P("KG/LB","ch"),P("RATE\nCLASS","ch"),
        P("COMMODITY\nITEM NO.","ch"),P("CHARGEABLE\nWEIGHT","ch"),P("RATE/\nCHARGE","ch"),
        P(f"TOTAL\n({currency})","ch"),P("NATURE AND QUANTITY OF GOODS\n(INCL. DIMENSIONS / VOLUME)","ch")]
    rd=[P(n_pkgs,"cdc"),P(f"{gross_wt:,.2f}","cdr"),P("KG","cdc"),P(rate_class,"cdc"),
        P(commodity_no,"cdc"),P(f"{chargeable_wt:,.2f}","cdr"),P(f"{rate:.2f}","cdr"),
        P(f"{total_charge:,.2f}","cdr"),P(f"{nature_of_goods}\nDimensions: {dimensions}","cd")]
    rt2=Table([rh,rd],colWidths=[16*mm,18*mm,10*mm,12*mm,16*mm,18*mm,14*mm,14*mm,68*mm])
    rt2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(rt2); story.append(Spacer(1,1*mm))

    if handling:
        story.append(P(f"Handling Information: {handling}","sm"))
        story.append(Spacer(1,1*mm))

    # Charges
    ch_rows=[[P("WEIGHT CHARGE","lbl"),P(f"{currency} {total_charge:,.2f}","val"),
              P("TOTAL OTHER CHARGES","lbl"),P(f"{currency} 0.00","val"),
              P("TOTAL CHARGES","lbl"),P(f"{currency} {total_charge:,.2f}","val"),
              P("[ ] PREPAID  [ ] COLLECT","sm")]]
    ct=Table(ch_rows,colWidths=[32*mm,28*mm,36*mm,22*mm,28*mm,26*mm,14*mm])
    ct.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),3),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,0),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,0),colors.HexColor("#EEEEEE"))]))
    story.append(ct); story.append(Spacer(1,2*mm))

    # Signature
    sg=Table([[P("Executed on (date):","lbl"),P(issue_date.strftime("%d %b %Y"),"val"),
               P("At (place):","lbl"),P(dep_airport.split("International")[0].strip(),"val")],
              [P(f"Signature of Shipper or Agent: {signatory}","sm"),
               P(f"For Carrier: {agent}","sm"),P("","sm"),P("","sm")]],
             colWidths=[30*mm,66*mm,20*mm,70*mm])
    sg.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),4),
        ("SPAN",(0,1),(1,1)),("SPAN",(2,1),(3,1))]))
    story.append(sg)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"House Airway Bill","class_index":7,
         "fields":{"hawb_number":hawb,"mawb_number":mawb,"shipper_name":shipper,"shipper_address":sh_addr,
                   "consignee_name":consignee,"consignee_address":cn_addr,"issuing_agent":agent,
                   "airport_departure":f"{dep_airport} ({dep_code})",
                   "airport_destination":f"{dest_airport} ({dest_code})",
                   "currency":currency,"charge_code":charge_code,
                   "declared_value_customs":declared_customs,
                   "no_of_pieces":n_pkgs,"gross_weight_kg":gross_wt,"chargeable_weight":chargeable_wt,
                   "rate":rate,"total_charge":total_charge,"nature_of_goods":nature_of_goods,
                   "handling_info":handling,"issue_date":issue_date.strftime("%Y-%m-%d"),"signatory":signatory}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} HAWB documents...")
    for i in range(1,count+1):
        a=generate_one(i); f=a["fields"]
        print(f"  [{i:04d}] {f['hawb_number']}  {f['gross_weight_kg']} KG  {f['currency']} {f['total_charge']:,.2f}")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
