"""Customs Declaration CN23 — UPU standard postal customs declaration form."""
import json, random
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import fake, random, random_company, random_country, CURRENCIES

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "09_Customs_Declarations"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"
BORDER=colors.HexColor("#555555"); LN=colors.HexColor("#BBBBBB"); PAGE_W=186*mm

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=8,leading=10,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=12,alignment=TA_CENTER),
    "sub":S("s",fontSize=8,alignment=TA_CENTER),"lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=8.5),"sm":S("sm",fontSize=7,leading=9),
    "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER),
    "cd":S("cd",fontSize=7.5,leading=9),"cdr":S("cdr",fontSize=7.5,leading=9,alignment=TA_RIGHT),
    "cdc":S("cdc",fontSize=7.5,leading=9,alignment=TA_CENTER),
    "decl":S("dc",fontSize=7,leading=10),"bold":S("b",fontName="Helvetica-Bold",fontSize=8),}
def P(t,s="cd"): return Paragraph(str(t),ST[s])
def cb(x): return "[X]" if x else "[ ]"

ITEM_TYPES=[("Gift","Personal gift for family/friends"),("Commercial Sample","No commercial value"),
            ("Returned Goods","Returned as originally exported"),("Documents","No commercial value"),
            ("Other","Goods sold online"),("Commercial","Commercial goods")]
POSTAL_ITEMS=[("Book","Books and printed matter","4901.99.00"),
              ("Clothing","Textile garments","6211.42.00"),
              ("Cosmetics","Personal care products","3304.99.00"),
              ("Electronics","Electronic accessories","8517.62.00"),
              ("Jewellery","Fashion jewellery","7117.19.00"),
              ("Toys","Children's toys","9503.00.00"),
              ("Food","Processed food items","2106.90.90"),
              ("Stationery","Office stationery","4820.10.20"),
              ("Health Products","Vitamins and supplements","2106.90.92"),
              ("Sports Equipment","Sporting goods","9506.99.00")]

def generate_one(doc_id):
    sc=random_country(); dc=random_country()
    while dc[1]==sc[1]: dc=random_country()
    sender_name=fake.name(); sender_addr=fake.address().replace("\n",", ")+f", {sc[0]}"
    sender_phone=fake.phone_number(); sender_email=fake.email()
    sender_company=random.choice([random_company(),""] )
    addressee=fake.name(); addr_addr=fake.address().replace("\n",", ")+f", {dc[0]}"
    addr_phone=fake.phone_number()
    item_type,item_desc_type=random.choice(ITEM_TYPES)
    n_items=random.randint(1,5); currency=random.choice(["GBP","USD","EUR","AUD","CAD"])
    items=[]
    for _ in range(n_items):
        cat,desc,hs=random.choice(POSTAL_ITEMS)
        qty=random.randint(1,10); wt=round(random.uniform(0.05,2.0),3)
        val=round(random.uniform(5,200),2)
        items.append({"qty":qty,"description":desc,"weight_kg":wt,"value":val,
                      "hs_code":hs,"origin":sc[0]})
    total_wt=round(sum(i["weight_kg"] for i in items),3)
    total_val=round(sum(i["value"] for i in items),2)
    insured=random.random()<0.3; insured_val=round(random.uniform(50,500),2) if insured else 0
    postal_charges=round(random.uniform(5,80),2)
    issue_date=fake.date_between(start_date="-2y",end_date="today")
    ref=f"CN23-{random.randint(100000,999999)}"

    fname=f"cn23_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=20*mm,rightMargin=20*mm,topMargin=15*mm,bottomMargin=15*mm)
    story=[]
    W=170*mm

    # Title
    tb=Table([[P("CUSTOMS DECLARATION","title")],
              [P(f"CN 23 — Dispatch Note / Déclaration en douane","sub")]],
             colWidths=[W])
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),colors.HexColor("#003399")),
        ("TEXTCOLOR",(0,0),(0,0),colors.white),("BACKGROUND",(0,1),(0,1),colors.HexColor("#E6ECFF")),
        ("BOX",(0,0),(-1,-1),0.8,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(-1,-1),6)]))
    story.append(tb); story.append(Spacer(1,3*mm))

    # Sender / Addressee
    sa=Table([[
        [P("SENDER / EXPÉDITEUR","lbl"),P(sender_name,"val"),
         P(sender_company,"sm") if sender_company else Spacer(1,1*mm),
         P(sender_addr,"sm"),P(f"Tel: {sender_phone}","sm"),P(f"Email: {sender_email}","sm")],
        [P("ADDRESSEE / DESTINATAIRE","lbl"),P(addressee,"val"),
         P(addr_addr,"sm"),P(f"Tel: {addr_phone}","sm")],
    ]],colWidths=[W//2,W//2])
    sa.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(sa); story.append(Spacer(1,2*mm))

    # Category checkboxes
    cats=[("Gift",item_type=="Gift"),("Commercial Sample",item_type=="Commercial Sample"),
          ("Returned Goods",item_type=="Returned Goods"),("Documents",item_type=="Documents"),
          ("Other",item_type not in ["Gift","Commercial Sample","Returned Goods","Documents"])]
    cat_row=[[P(f"{cb(c)} {n}","sm") for n,c in cats]]
    ct=Table(cat_row,colWidths=[W//5]*5)
    ct.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4)]))
    story.append(P("CATEGORY OF ITEM:","lbl")); story.append(ct); story.append(Spacer(1,2*mm))

    # Items table
    rows=[[P("Qty","ch"),P("Detailed Description of Contents","ch"),P("Net Weight\n(kg)","ch"),
           P(f"Value\n({currency})","ch"),P("HS Tariff No.","ch"),P("Country\nof Origin","ch")]]
    for it in items:
        rows.append([P(it["qty"],"cdc"),P(it["description"],"cd"),P(f"{it['weight_kg']:.3f}","cdr"),
                     P(f"{it['value']:.2f}","cdr"),P(it["hs_code"],"cdc"),P(it["origin"],"cdc")])
    for _ in range(max(0,5-len(items))): rows.append([P("")]*6)
    rows.append([P("","ch"),P("TOTAL","ch"),P(f"{total_wt:.3f}","cdr"),
                 P(f"{total_val:.2f}","cdr"),P("","cdc"),P("","cdc")])
    it_t=Table(rows,colWidths=[12*mm,70*mm,22*mm,20*mm,22*mm,24*mm],repeatRows=1)
    it_t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#003399")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EEEEEE")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(it_t); story.append(Spacer(1,2*mm))

    # Charges / Insurance
    ch=Table([[P("POSTAL CHARGES / FEES:","lbl"),P(f"{currency} {postal_charges:.2f}","val"),
               P(f"INSURED AMOUNT: {cb(insured)}","lbl"),
               P(f"{currency} {insured_val:.2f}" if insured else "Not insured","sm")]],
             colWidths=[40*mm,35*mm,50*mm,45*mm])
    ch.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4)]))
    story.append(ch); story.append(Spacer(1,2*mm))

    # Declaration
    decl_text=("I, the undersigned, certify that the particulars given in this customs declaration are correct "
               "and that this item does not contain any dangerous article, or articles prohibited by legislation "
               "or postal or customs regulations.")
    story.append(P(decl_text,"decl")); story.append(Spacer(1,2*mm))
    sg=Table([[P(f"Sender's Signature: ___________________________","sm"),
               P(f"Date: {issue_date.strftime('%d %b %Y')}","val"),
               P(f"Reference: {ref}","sm")]],
             colWidths=[80*mm,44*mm,46*mm])
    sg.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(sg)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Customs Declaration CN23","class_index":9,
         "fields":{"sender_name":sender_name,"sender_address":sender_addr,
                   "sender_company":sender_company,"sender_country":sc[0],
                   "addressee_name":addressee,"addressee_address":addr_addr,"addressee_country":dc[0],
                   "item_category":item_type,"currency":currency,
                   "total_weight_kg":total_wt,"total_value":total_val,
                   "insured":insured,"insured_amount":insured_val,"postal_charges":postal_charges,
                   "issue_date":issue_date.strftime("%Y-%m-%d"),"reference":ref,"items":items}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} CN23 Customs Declaration documents...")
    for i in range(1,count+1):
        a=generate_one(i); f=a["fields"]
        print(f"  [{i:04d}] {f['reference']}  {f['item_category']}  {f['total_weight_kg']} KG  {f['currency']} {f['total_value']:.2f}")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
