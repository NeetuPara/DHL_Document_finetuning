"""House Bill of Lading generator — standard international ocean HBL format."""
import json, random, argparse
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_bl_number, random_container_number, random_seal_number,
    VESSEL_NAMES, PORTS_SEA, PACKAGE_TYPES, INCOTERMS, CURRENCIES)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "02_House_Bill_of_Lading"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"

BORDER = colors.HexColor("#555555"); LN = colors.HexColor("#BBBBBB")
TITLE_BG = colors.HexColor("#1A1A2E"); HDR_BG = colors.HexColor("#EEEEEE")
PAGE_W = 186*mm

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=8,leading=10,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=13,alignment=TA_CENTER,textColor=colors.white),
    "sub":S("s",fontSize=7,alignment=TA_CENTER,textColor=colors.white),
    "lbl":S("l",fontSize=7,textColor=colors.HexColor("#555555")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=8),
    "sm":S("sm",fontSize=7,leading=9),
    "ch":S("ch",fontName="Helvetica-Bold",fontSize=7,alignment=TA_CENTER),
    "cd":S("cd",fontSize=7,leading=9),"cdr":S("cdr",fontSize=7,leading=9,alignment=TA_RIGHT),
    "cdc":S("cdc",fontSize=7,leading=9,alignment=TA_CENTER),
    "foot":S("ft",fontSize=6.5,textColor=colors.HexColor("#444444")),}

def P(t,s="cd"): return Paragraph(str(t),ST[s])
def lv(l,v): return [P(l,"lbl"),P(v,"val")]
def cell(*lines): return [P(l[0],l[1]) if isinstance(l,tuple) else P(l) for l in lines]

def generate_one(doc_id):
    sc=random_country(); cc=random_country(); nc=random_country()
    sn=random_company(); sa=fake.address().replace("\n",", ")+f", {sc[0]}"
    cn=random_company(); ca=fake.address().replace("\n",", ")+f", {cc[0]}"
    nn=random_company(); na=fake.address().replace("\n",", ")+f", {nc[0]}"
    bl=random_bl_number()
    pol=random.choice(PORTS_SEA); pod=random.choice(PORTS_SEA)
    while pod==pol: pod=random.choice(PORTS_SEA)
    pod_place=pod; por=random.choice(PORTS_SEA[:8])
    vessel=random.choice(VESSEL_NAMES); voyage=f"{random.randint(100,999)}{''.join(random.choices('NESW',k=1))}"
    issue_date=fake.date_between(start_date="-2y",end_date="today")
    issue_place=random.choice(["Singapore","Rotterdam","Hamburg","Hong Kong","Shanghai","Los Angeles"])
    freight=random.choice(["PREPAID","COLLECT","PAYABLE AT DESTINATION"])
    orig_bl=random.choice([1,2,3]); n_orig=f"{orig_bl} (ONE/TWO/THREE)"[:(orig_bl*3+orig_bl-1)]
    n_ctns=random.randint(1,20)
    containers=[{"container_no":random_container_number(),"seal_no":random_seal_number(),
                 "type":random.choice(["20'GP","40'GP","40'HC","20'RF","45'HC"])}
                for _ in range(random.randint(1,3))]
    marks=f"{random.choice(['ABC','XYZ','GLB'])}/{random.randint(1,99)}"
    n_pkgs=random.randint(5,500)
    pkg_type=random.choice(PACKAGE_TYPES)
    desc_list=[random.choice(["Electronic Components","Machinery Parts","Textile Goods",
               "Chemical Products","Consumer Electronics","Automotive Parts",
               "Pharmaceutical Products","Food Products","Steel Products","Plastic Goods"])]
    description=", ".join(desc_list)
    gross_wt=round(random.uniform(100,25000),2)
    net_wt=round(gross_wt*random.uniform(0.80,0.95),2)
    cbm=round(random.uniform(1,80),3)
    hs=f"{random.randint(1000,9999)}.{random.randint(10,99)}.{random.randint(10,99)}"

    fname=f"house_bol_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]

    # Title banner
    tb=Table([[P("HOUSE BILL OF LADING","title")],[P("NON-NEGOTIABLE UNLESS CONSIGNED TO ORDER","sub")]],
             colWidths=[PAGE_W])
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),TITLE_BG),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("BOX",(0,0),(-1,-1),0.5,BORDER)]))
    story.append(tb); story.append(Spacer(1,1*mm))

    # BL number row
    blr=Table([[P("B/L NUMBER","lbl"),P(bl,"val"),P("DATE OF ISSUE","lbl"),P(issue_date.strftime("%d %b %Y"),"val"),
               P("PLACE OF ISSUE","lbl"),P(issue_place,"val")]],
              colWidths=[28*mm,50*mm,28*mm,32*mm,24*mm,24*mm])
    blr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,0),HDR_BG),("BACKGROUND",(2,0),(2,0),HDR_BG),("BACKGROUND",(4,0),(4,0),HDR_BG)]))
    story.append(blr); story.append(Spacer(1,1*mm))

    # Shipper / Consignee / Notify
    party=Table([[[P("SHIPPER / EXPORTER","lbl"),P(sn,"val"),P(sa,"sm"),Spacer(1,1*mm)],
                  [P("CONSIGNEE","lbl"),P(cn,"val"),P(ca,"sm")],
                  [P("NOTIFY PARTY","lbl"),P(nn,"val"),P(na,"sm")]]],
                colWidths=[PAGE_W])
    scn=Table([[
        cell(("SHIPPER / EXPORTER","lbl"),sn,sa),
        cell(("CONSIGNEE","lbl"),cn,ca),
        cell(("NOTIFY PARTY","lbl"),nn,na),
    ]],colWidths=[62*mm,62*mm,62*mm])
    scn.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),4),
        ("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(scn); story.append(Spacer(1,1*mm))

    # Routing
    rt=Table([[P("PRE-CARRIAGE BY","lbl"),P("","val"),P("PLACE OF RECEIPT","lbl"),P(por,"val")],
              [P("VESSEL / VOYAGE NO.","lbl"),P(f"{vessel} / {voyage}","val"),
               P("PORT OF LOADING","lbl"),P(pol,"val")],
              [P("PORT OF DISCHARGE","lbl"),P(pod,"val"),
               P("PLACE OF DELIVERY","lbl"),P(pod_place,"val")]],
             colWidths=[36*mm,55*mm,36*mm,59*mm])
    rt.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,-1),HDR_BG),("BACKGROUND",(2,0),(2,-1),HDR_BG)]))
    story.append(rt); story.append(Spacer(1,1*mm))

    # Container block
    cont_rows=[[P("CONTAINER NO.","ch"),P("SEAL NO.","ch"),P("SIZE/TYPE","ch"),
                P("NO. OF PACKAGES","ch"),P("DESCRIPTION OF GOODS","ch"),
                P("GROSS WEIGHT (KG)","ch"),P("MEASUREMENT (CBM)","ch")]]
    for ct in containers:
        cont_rows.append([P(ct["container_no"],"cdc"),P(ct["seal_no"],"cdc"),P(ct["type"],"cdc"),
                          P(n_pkgs,"cdr"),P(description,"cd"),P(f"{gross_wt:,.2f}","cdr"),P(f"{cbm:.3f}","cdr")])
    # Marks row
    cont_rows.append([P(marks,"cd"),P("","cd"),P("","cd"),P("","cd"),
                      P(f"H.S. Code: {hs}","cd"),P("","cd"),P("","cd")])
    ct_t=Table(cont_rows,colWidths=[30*mm,22*mm,18*mm,22*mm,46*mm,24*mm,24*mm],repeatRows=1)
    ct_t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(ct_t); story.append(Spacer(1,1*mm))

    # Freight / Terms
    fr=Table([[P("FREIGHT TERMS","lbl"),P(freight,"val"),
               P("NO. OF ORIGINALS","lbl"),P(f"{orig_bl} ORIGINAL(S)","val"),
               P("INCOTERMS","lbl"),P(random.choice(INCOTERMS),"val")]],
             colWidths=[28*mm,42*mm,32*mm,30*mm,22*mm,32*mm])
    fr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,0),HDR_BG),("BACKGROUND",(2,0),(2,0),HDR_BG),("BACKGROUND",(4,0),(4,0),HDR_BG)]))
    story.append(fr); story.append(Spacer(1,2*mm))

    # Signature
    sg=Table([[P("Issued by DHL Global Forwarding on behalf of the carrier.","sm"),
               P(f"Signed: ________________________","sm")],
              [P(f"Place and Date: {issue_place}, {issue_date.strftime('%d %b %Y')}","sm"),
               P("As agent for the carrier","sm")]],
             colWidths=[110*mm,76*mm])
    sg.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(sg)
    story.append(Spacer(1,2*mm))
    story.append(P("RECEIVED by the carrier the goods as specified above in apparent good order and condition unless otherwise stated, to be transported to such place as agreed, authorised or permitted herein.","foot"))
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"House Bill of Lading","class_index":2,
         "fields":{"bl_number":bl,"shipper_name":sn,"shipper_address":sa,
                   "consignee_name":cn,"consignee_address":ca,
                   "notify_party":nn,"notify_party_address":na,
                   "vessel":vessel,"voyage":voyage,"port_of_loading":pol,"port_of_discharge":pod,
                   "place_of_receipt":por,"place_of_delivery":pod_place,
                   "issue_date":issue_date.strftime("%Y-%m-%d"),"issue_place":issue_place,
                   "freight_terms":freight,"originals":orig_bl,
                   "containers":[c["container_no"] for c in containers],
                   "description":description,"hs_code":hs,
                   "no_of_packages":n_pkgs,"package_type":pkg_type,
                   "gross_weight_kg":gross_wt,"net_weight_kg":net_wt,"cbm":cbm,
                   "marks":marks}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} House Bill of Lading documents...")
    for i in range(1,count+1):
        a=generate_one(i)
        print(f"  [{i:04d}] {a['fields']['bl_number']}  {a['fields']['vessel']}")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
