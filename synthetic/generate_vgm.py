"""Verified Gross Mass (VGM) Declaration — SOLAS compliant."""
import json, random
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import fake, random, random_company, random_country, random_container_number, random_seal_number, random_bl_number, PORTS_SEA

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "06_Verified_Gross_Mass"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"
BORDER=colors.HexColor("#555555"); LN=colors.HexColor("#BBBBBB"); PAGE_W=186*mm
CONTAINER_SIZES=["20'GP","40'GP","40'HC","20'RF","45'HC","20'OT","40'OT"]
TARE_WEIGHTS={"20'GP":2200,"40'GP":3900,"40'HC":4000,"20'RF":2900,"45'HC":4800,"20'OT":2100,"40'OT":3800}

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=8,leading=10,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=14,alignment=TA_CENTER),
    "sub":S("s",fontSize=8,alignment=TA_CENTER,textColor=colors.HexColor("#555555")),
    "lbl":S("l",fontSize=8,textColor=colors.HexColor("#444444")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=10),"sm":S("sm",fontSize=7.5,leading=10),
    "big":S("big",fontName="Helvetica-Bold",fontSize=13),
    "cert":S("cert",fontSize=8,leading=11),}

def P(t,s="sm"): return Paragraph(str(t),ST[s])

def generate_one(doc_id):
    sc=random_country()
    shipper=random_company(); addr=fake.address().replace("\n",", ")+f", {sc[0]}"
    contact=fake.name(); phone=fake.phone_number()
    dhl_ref=f"DHL-{random.randint(1000000,9999999)}"
    booking=f"BKG-{random.randint(100000,999999)}"
    bl=random_bl_number()
    pol=random.choice(PORTS_SEA); pod=random.choice(PORTS_SEA)
    while pod==pol: pod=random.choice(PORTS_SEA)
    ctype=random.choice(CONTAINER_SIZES)
    container_no=random_container_number(); seal_no=random_seal_number()
    tare=TARE_WEIGHTS[ctype]
    method=random.choice([1,2])
    if method==1:
        cargo_wt=round(random.uniform(2000,24000),1)
        vgm=round(cargo_wt+tare,1)
        pkg_wt=None
    else:
        n_pkgs=random.randint(2,50)
        pkg_wt=round(random.uniform(100,12000),1)
        other_wt=round(random.uniform(10,200),1)
        vgm=round(pkg_wt+other_wt+tare,1)
        cargo_wt=round(pkg_wt+other_wt,1)
    verify_date=fake.date_between(start_date="-1y",end_date="today")
    cert_no=f"VGM-CERT-{random.randint(100000,999999)}"
    signatory=fake.name(); position=random.choice(["Logistics Manager","Operations Director","Export Manager","Compliance Officer"])
    unit=random.choice(["KGS","KGS","LBS"])

    fname=f"vgm_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=20*mm,rightMargin=20*mm,topMargin=15*mm,bottomMargin=15*mm)
    story=[]

    # Title
    tb=Table([[P("VERIFIED GROSS MASS (VGM) DECLARATION","title")],
              [P("In compliance with SOLAS Regulation VI/2 — Mandatory weighing of packed containers","sub")]],
             colWidths=[166*mm])
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",(0,0),(0,0),colors.white),
        ("BACKGROUND",(0,1),(0,1),colors.HexColor("#EEEEEE")),
        ("BOX",(0,0),(-1,-1),0.8,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(-1,-1),6)]))
    story.append(tb); story.append(Spacer(1,5*mm))

    # Company / Reference
    cr=Table([[P("SHIPPER / COMPANY:","lbl"),P(shipper,"val"),P("DHL REFERENCE:","lbl"),P(dhl_ref,"val")],
              [P("ADDRESS:","lbl"),P(addr,"sm"),P("BOOKING NO.:","lbl"),P(booking,"sm")],
              [P("CONTACT PERSON:","lbl"),P(contact,"sm"),P("B/L NUMBER:","lbl"),P(bl,"sm")],
              [P("TELEPHONE:","lbl"),P(phone,"sm"),P("CERTIFICATION NO.:","lbl"),P(cert_no,"sm")]],
             colWidths=[30*mm,53*mm,34*mm,49*mm])
    cr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F0F0F0")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#F0F0F0"))]))
    story.append(cr); story.append(Spacer(1,4*mm))

    # Container details
    cd=Table([[P("CONTAINER NUMBER:","lbl"),P(container_no,"big"),P("CONTAINER SIZE/TYPE:","lbl"),P(ctype,"big")],
              [P("SEAL NUMBER:","lbl"),P(seal_no,"val"),P("PORT OF LOADING:","lbl"),P(pol,"val")],
              [P("PORT OF DISCHARGE:","lbl"),P(pod,"val"),P("UNIT OF MEASURE:","lbl"),P(unit,"val")]],
             colWidths=[38*mm,45*mm,38*mm,45*mm])
    cd.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F0F0F0")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#F0F0F0"))]))
    story.append(cd); story.append(Spacer(1,4*mm))

    # Method + VGM
    method_text1=("METHOD 1: The packed container was weighed using calibrated and certified equipment. "
                  "Total mass = gross weight of packed container including all packing material, pallets etc.")
    method_text2=("METHOD 2: All cargo items, packing materials, pallets etc. were individually weighed and "
                  "the mass of each was added to the tare mass of the container.")
    mv=Table([[P(f"VERIFICATION METHOD:  [{'X' if method==1 else ' '}] Method 1     [{'X' if method==2 else ' '}] Method 2","lbl"),P("","sm")]],
             colWidths=[120*mm,46*mm])
    story.append(mv)
    story.append(Spacer(1,1*mm))
    story.append(P(method_text1 if method==1 else method_text2,"sm"))
    story.append(Spacer(1,4*mm))

    # Weight breakdown
    wr=Table([[P("TARE WEIGHT OF CONTAINER:","lbl"),P(f"{tare:,.1f}  {unit}","big")],
              [P("CARGO GROSS WEIGHT (incl. packing):","lbl"),P(f"{cargo_wt:,.1f}  {unit}","big")],
              [P("VERIFIED GROSS MASS (VGM):","lbl"),P(f"{vgm:,.1f}  {unit}","big")]],
             colWidths=[80*mm,86*mm])
    wr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(-1,-1),5),
        ("BACKGROUND",(0,2),(0,2),colors.HexColor("#FFF3CD")),("BACKGROUND",(1,2),(1,2),colors.HexColor("#FFF3CD")),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F5F5F5"))]))
    story.append(wr); story.append(Spacer(1,5*mm))

    # Certification
    cert_text=(f"I, the undersigned, hereby certify that the Verified Gross Mass (VGM) of the above container "
               f"as stated is accurate, and has been determined using certified and calibrated equipment / Method {method}. "
               f"This declaration is provided in accordance with the requirements of SOLAS Chapter VI, Regulation 2.")
    story.append(P(cert_text,"cert")); story.append(Spacer(1,4*mm))

    sg=Table([[P("Authorized Signature: ___________________________","sm"),P(f"Date of Verification: {verify_date.strftime('%d %b %Y')}","val")],
              [P(f"Name: {signatory}","sm"),P(f"Position: {position}","sm")],
              [P(f"Company: {shipper}","sm"),P("Company Stamp:","sm")]],
             colWidths=[100*mm,66*mm])
    sg.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(sg)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Verified Gross Mass","class_index":6,
         "fields":{"shipper_name":shipper,"shipper_address":addr,"contact":contact,"phone":phone,
                   "dhl_reference":dhl_ref,"booking_no":booking,"bl_number":bl,"certification_no":cert_no,
                   "container_no":container_no,"container_type":ctype,"seal_no":seal_no,
                   "port_of_loading":pol,"port_of_discharge":pod,
                   "verification_method":method,"tare_weight":tare,"cargo_weight":cargo_wt,
                   "vgm_weight":vgm,"weight_unit":unit,"verification_date":verify_date.strftime("%Y-%m-%d"),
                   "signatory":signatory,"position":position}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} VGM documents...")
    for i in range(1,count+1):
        a=generate_one(i); f=a["fields"]
        print(f"  [{i:04d}] {f['container_no']}  VGM={f['vgm_weight']:,.1f} {f['weight_unit']}  Method {f['verification_method']}")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
