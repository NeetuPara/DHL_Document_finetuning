"""IATA Dangerous Goods Declaration — column format (air freight)."""
import json, random
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import fake, random, random_company, random_country, random_hawb_number, AIRPORTS, UN_NUMBERS

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "05_Dangerous_Goods_Declaration"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"
BORDER=colors.HexColor("#555555"); LN=colors.HexColor("#BBBBBB"); PAGE_W=186*mm

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=8,leading=10,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=11,alignment=TA_CENTER),
    "sub":S("s",fontSize=7,alignment=TA_CENTER),"hdr":S("h",fontName="Helvetica-Bold",fontSize=7),
    "lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=8),"sm":S("sm",fontSize=7,leading=9),
    "ch":S("ch",fontName="Helvetica-Bold",fontSize=6.5,alignment=TA_CENTER),
    "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,leading=9,alignment=TA_RIGHT),
    "cdc":S("cdc",fontSize=7,leading=9,alignment=TA_CENTER),
    "warn":S("w",fontName="Helvetica-Bold",fontSize=7.5,alignment=TA_CENTER,textColor=colors.HexColor("#CC0000")),}
def P(t,s="cd"): return Paragraph(str(t),ST[s])

PACKING_INSTRUCTIONS=["PI 965","PI 966","PI 967","PI 968","PI 959","PI 950","PI 910","PI 903","PI 870","PI 852"]
SPECIAL_PROVISIONS=["A1","A2","A3","A51","A88","A99","A109","A154","A176","A211"]
AUTH_NUMBERS=["2024-AUT-"+str(random.randint(10000,99999)) for _ in range(20)]

def generate_one(doc_id):
    sc=random_country(); dc=random_country()
    shipper_name=random_company(); shipper_addr=fake.address().replace("\n",", ")+f", {sc[0]}"
    shipper_phone=fake.phone_number(); shipper_emergency=fake.phone_number()
    consignee_name=random_company(); consignee_addr=fake.address().replace("\n",", ")+f", {dc[0]}"
    awb=random_hawb_number()
    dep_airport,dep_code=random.choice(AIRPORTS)
    dest_airport,dest_code=random.choice(AIRPORTS)
    while dest_code==dep_code: dest_airport,dest_code=random.choice(AIRPORTS)
    flight_no=f"{random.choice(['DL','LH','EK','SQ','QF','BA'])}{random.randint(100,999)}"
    flight_date=fake.date_between(start_date="-1y",end_date="today")
    n_entries=random.randint(1,3)
    entries=[]
    for _ in range(n_entries):
        un_no,prop_name,dg_class,pg,hazard=random.choice(UN_NUMBERS)
        n_pkgs=random.randint(1,20); pkg_type=random.choice(["Fibreboard box","Steel drum","Plastic jerrican","Composite packaging","Combination packaging"])
        net_qty=round(random.uniform(0.1,50),2); qty_unit=random.choice(["kg","L","G"])
        pi=random.choice(PACKING_INSTRUCTIONS)
        auth=random.choice(AUTH_NUMBERS) if random.random()<0.3 else ""
        sp=random.choice(SPECIAL_PROVISIONS) if random.random()<0.4 else ""
        entries.append({"un_no":un_no,"proper_shipping_name":prop_name,"class":dg_class,
                        "packing_group":pg or "N/A","n_pkgs":n_pkgs,"pkg_type":pkg_type,
                        "net_qty":net_qty,"qty_unit":qty_unit,"packing_instruction":pi,
                        "auth_no":auth,"special_provision":sp,"hazard_label":hazard})
    signatory=fake.name(); sign_date=flight_date; sign_place=dep_airport.split(" International")[0]

    fname=f"dgd_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]

    # Title + warning
    tb=Table([[P("SHIPPER'S DECLARATION FOR DANGEROUS GOODS","title")],
              [P("AIR TRANSPORT ONLY — IATA DANGEROUS GOODS REGULATIONS","sub")],
              [P("WARNING: Failure to comply with applicable dangerous goods regulations may be in breach of applicable law, subject to legal penalties. This declaration must not be used as a shipping document.","sm")]],
             colWidths=[PAGE_W])
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(0,1),colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",(0,0),(0,1),colors.white),
        ("BACKGROUND",(0,2),(0,2),colors.HexColor("#FFF9E6")),
        ("BOX",(0,0),(-1,-1),0.8,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(tb); story.append(Spacer(1,2*mm))

    # Shipper / AWB / Flight
    top=Table([[
        [P("SHIPPER","lbl"),P(shipper_name,"val"),P(shipper_addr,"sm"),
         P(f"Tel: {shipper_phone}","sm"),P(f"Emergency Tel: {shipper_emergency}","sm")],
        [P("CONSIGNEE","lbl"),P(consignee_name,"val"),P(consignee_addr,"sm")],
        [P("AIR WAYBILL NO.","lbl"),P(awb,"val"),Spacer(1,2*mm),
         P("PAGE NO.","lbl"),P(f"1 of 1","val"),Spacer(1,2*mm),
         P("SHIPPER'S REFERENCE","lbl"),P(f"REF-{random.randint(10000,99999)}","val")],
    ]],colWidths=[72*mm,72*mm,42*mm])
    top.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(top); story.append(Spacer(1,1*mm))

    # Airport / Flight
    fl=Table([[P("AIRPORT OF DEPARTURE","lbl"),P(f"{dep_airport} ({dep_code})","val"),
               P("AIRPORT OF DESTINATION","lbl"),P(f"{dest_airport} ({dest_code})","val")],
              [P("FLIGHT NO. / DATE","lbl"),P(f"{flight_no} / {flight_date.strftime('%d %b %Y')}","val"),
               P("SHIPMENT TYPE","lbl"),P("[X] Non-Radioactive   [ ] Radioactive","sm")]],
             colWidths=[34*mm,58*mm,34*mm,60*mm])
    fl.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#EEEEEE"))]))
    story.append(fl); story.append(Spacer(1,1*mm))

    # Transport detail header
    tdhdr=Table([[P("TRANSPORT DETAILS","warn")]],colWidths=[PAGE_W])
    tdhdr.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#FFFBE6")),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(tdhdr)

    # DG entries table
    dg_rows=[[P("UN or\nID No.","ch"),P("Proper Shipping Name (and Description)","ch"),
              P("Class\nor\nDiv.","ch"),P("Packing\nGroup","ch"),P("Qty & Type\nof Packing","ch"),
              P("Packing\nInst.","ch"),P("Auth.\nNo.","ch"),P("No. of\nPkgs.","ch")]]
    for e in entries:
        dg_rows.append([P(e["un_no"],"cd"),P(f"{e['proper_shipping_name']}\n({e['hazard_label']})","cd"),
                        P(e["class"],"cdr" if True else "cd"),P(e["packing_group"],"cdr" if True else "cd"),
                        P(f"{e['net_qty']} {e['qty_unit']}\n{e['pkg_type']}","cd"),
                        P(e["packing_instruction"],"cd"),P(e["auth_no"] or "-","cd"),P(e["n_pkgs"],"cdr" if True else "cd")])
    for _ in range(max(0,4-len(entries))): dg_rows.append([P("")]*8)
    dgt=Table(dg_rows,colWidths=[16*mm,58*mm,14*mm,14*mm,34*mm,16*mm,20*mm,14*mm],repeatRows=1)
    dgt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(dgt); story.append(Spacer(1,2*mm))

    # Declaration
    decl_text=("I hereby declare that the contents of this consignment are fully and accurately described above by "
               "the proper shipping name, and are classified, packaged, marked and labelled/placarded, and are in all "
               "respects in proper condition for transport according to applicable international and national governmental regulations.")
    decl=Table([[P(decl_text,"sm")]],colWidths=[PAGE_W])
    decl.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(decl); story.append(Spacer(1,2*mm))

    # Signature
    sg=Table([[P("Name / Title (print): ___________________________","sm"),
               P(f"{signatory} — Dangerous Goods Certified","sm")],
              [P("Place and Date:","sm"),P(f"{sign_place},  {sign_date.strftime('%d %b %Y')}","val")],
              [P("Signature: (shipper) ___________________________","sm"),P("","sm")]],
             colWidths=[110*mm,76*mm])
    sg.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(sg)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Dangerous Goods Declaration","class_index":5,
         "fields":{"shipper_name":shipper_name,"shipper_address":shipper_addr,"emergency_tel":shipper_emergency,
                   "consignee_name":consignee_name,"consignee_address":consignee_addr,
                   "awb_number":awb,"flight_no":flight_no,"flight_date":flight_date.strftime("%Y-%m-%d"),
                   "airport_departure":f"{dep_airport} ({dep_code})",
                   "airport_destination":f"{dest_airport} ({dest_code})",
                   "signatory":signatory,"sign_date":sign_date.strftime("%Y-%m-%d"),"sign_place":sign_place,
                   "dangerous_goods_entries":entries}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} DGD documents...")
    for i in range(1,count+1):
        a=generate_one(i); f=a["fields"]
        print(f"  [{i:04d}] {f['awb_number']}  {len(f['dangerous_goods_entries'])} DG entry(ies)")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
