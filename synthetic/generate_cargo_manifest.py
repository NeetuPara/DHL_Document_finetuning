"""Cargo Manifest — combined air/ocean manifest format (CBP/CBSA style)."""
import json, random
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_bl_number, random_hawb_number, VESSEL_NAMES, PORTS_SEA, AIRPORTS)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "10_Cargo_Manifest"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"
BORDER=colors.HexColor("#555555"); LN=colors.HexColor("#BBBBBB")
PAGE_W=277*mm  # landscape A4

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=7,leading=9,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=11,alignment=TA_CENTER),
    "lbl":S("l",fontSize=6.5,textColor=colors.HexColor("#444444")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=7.5),
    "sm":S("sm",fontSize=6.5,leading=8.5),"ch":S("ch",fontName="Helvetica-Bold",fontSize=6.5,alignment=TA_CENTER),
    "cd":S("cd",fontSize=6.5,leading=8.5),"cdr":S("cdr",fontSize=6.5,leading=8.5,alignment=TA_RIGHT),
    "cdc":S("cdc",fontSize=6.5,leading=8.5,alignment=TA_CENTER),}
def P(t,s="cd"): return Paragraph(str(t),ST[s])

MANIFEST_TYPES=["Ocean Freight","Air Freight"]

def generate_one(doc_id):
    m_type=random.choice(MANIFEST_TYPES)
    manifest_no=f"MAN-{random.randint(100000,999999)}"
    issue_date=fake.date_between(start_date="-2y",end_date="today")
    if m_type=="Ocean Freight":
        vessel=random.choice(VESSEL_NAMES); voyage=f"{random.randint(100,999)}N"
        carrier=random.choice(["Maersk Line","CMA CGM","MSC","Hapag-Lloyd","COSCO","ONE","Evergreen"])
        pol=random.choice(PORTS_SEA); pod=random.choice(PORTS_SEA)
        while pod==pol: pod=random.choice(PORTS_SEA)
        transport_id=vessel; voyage_flight=voyage
        from_loc=pol; to_loc=pod
    else:
        dep_name,dep_code=random.choice(AIRPORTS); dest_name,dest_code=random.choice(AIRPORTS)
        while dest_code==dep_code: dest_name,dest_code=random.choice(AIRPORTS)
        carrier=random.choice(["DHL Express","FedEx Express","UPS Airlines","Emirates SkyCargo","Lufthansa Cargo"])
        flight_no=f"{random.choice(['DL','LH','EK','SQ'])}{random.randint(100,999)}"
        transport_id=f"{flight_no} ({dep_code}-{dest_code})"; voyage_flight=flight_no
        from_loc=f"{dep_name} ({dep_code})"; to_loc=f"{dest_name} ({dest_code})"
    n_entries=random.randint(5,20)
    entries=[]
    for _ in range(n_entries):
        sn=random_company(); cn=random_company()
        sc=random_country(); dc=random_country()
        ref=random_bl_number() if m_type=="Ocean Freight" else random_hawb_number()
        n_pkgs=random.randint(1,50); pkg_type=random.choice(["CTN","PLT","DRM","CAS","BDL"])
        desc=random.choice(["General Cargo","Electronic Goods","Machinery Parts","Textile Products",
                            "Chemical Products","Consumer Goods","Auto Parts","Food Products"])
        gw=round(random.uniform(10,5000),2); cbm=round(random.uniform(0.1,20),3)
        entries.append({"ref_no":ref,"shipper":sn,"consignee":cn,
                        "origin":sc[0],"destination":dc[0],
                        "n_pkgs":n_pkgs,"pkg_type":pkg_type,"description":desc,
                        "gross_weight":gw,"cbm":cbm})
    total_pkgs=sum(e["n_pkgs"] for e in entries)
    total_gw=round(sum(e["gross_weight"] for e in entries),2)
    total_cbm=round(sum(e["cbm"] for e in entries),3)
    agent=random.choice(["DHL Global Forwarding","Kuehne + Nagel","DB Schenker","Panalpina","Expeditors"])

    fname=f"cargo_manifest_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=landscape(A4),
                          leftMargin=10*mm,rightMargin=10*mm,topMargin=10*mm,bottomMargin=10*mm)
    story=[]

    # Title
    tb=Table([[P(f"CARGO MANIFEST — {m_type.upper()}","title")]],colWidths=[PAGE_W])
    tb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",(0,0),(-1,-1),colors.white),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(tb); story.append(Spacer(1,2*mm))

    # Manifest header
    hdr=Table([[P("MANIFEST NUMBER","lbl"),P(manifest_no,"val"),
                P("VESSEL / FLIGHT","lbl"),P(transport_id,"val"),
                P("CARRIER","lbl"),P(carrier,"val"),
                P("DATE","lbl"),P(issue_date.strftime("%d %b %Y"),"val")],
               [P("PORT / AIRPORT OF LOADING","lbl"),P(from_loc,"val"),
                P("PORT / AIRPORT OF DISCHARGE","lbl"),P(to_loc,"val"),
                P("FREIGHT FORWARDER / AGENT","lbl"),P(agent,"val"),
                P("VOYAGE / FLIGHT NO.","lbl"),P(voyage_flight,"val")]],
              colWidths=[36*mm,42*mm,30*mm,44*mm,32*mm,46*mm,28*mm,19*mm])
    hdr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),3),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,-1),colors.HexColor("#EEEEEE")),("BACKGROUND",(6,0),(6,-1),colors.HexColor("#EEEEEE"))]))
    story.append(hdr); story.append(Spacer(1,1*mm))

    # Entries table
    CW=[26*mm,40*mm,38*mm,22*mm,22*mm,10*mm,12*mm,36*mm,18*mm,16*mm,17*mm]
    cols=[[P("AWB/B/L No.","ch"),P("Shipper","ch"),P("Consignee","ch"),
           P("Country\nof Origin","ch"),P("Country of\nDestination","ch"),
           P("No.\nPkgs","ch"),P("Pkg\nType","ch"),P("Description of Goods","ch"),
           P("Gross Wt\n(KG)","ch"),P("Vol\n(CBM)","ch"),P("Remarks","ch")]]
    for e in entries:
        cols.append([P(e["ref_no"],"cd"),P(e["shipper"],"cd"),P(e["consignee"],"cd"),
                     P(e["origin"],"cdc"),P(e["destination"],"cdc"),
                     P(e["n_pkgs"],"cdc"),P(e["pkg_type"],"cdc"),P(e["description"],"cd"),
                     P(f"{e['gross_weight']:,.1f}","cdr"),P(f"{e['cbm']:.2f}","cdr"),P("","cd")])
    cols.append([P("TOTALS","ch"),P("","cd"),P("","cd"),P("","cdc"),P("","cdc"),
                 P(str(total_pkgs),"cdc"),P("","cdc"),P("","cd"),
                 P(f"{total_gw:,.1f}","cdr"),P(f"{total_cbm:.2f}","cdr"),P("","cd")])
    it_t=Table(cols,colWidths=CW,repeatRows=1)
    ts=TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EEEEEE")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),1.5),("BOTTOMPADDING",(0,0),(-1,-1),1.5),
        ("LEFTPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"MIDDLE")])
    for r in range(1,len(entries)+1):
        if r%2==0: ts.add("BACKGROUND",(0,r),(-1,r),colors.HexColor("#FAFAFA"))
    it_t.setStyle(ts)
    story.append(it_t); story.append(Spacer(1,2*mm))

    sg=Table([[P(f"Prepared by: {agent}","sm"),
               P(f"Authorized Signature: ___________________________","sm"),
               P(f"Date: {issue_date.strftime('%d %b %Y')}","sm")]],
             colWidths=[80*mm,130*mm,67*mm])
    sg.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(sg)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Cargo Manifest","class_index":10,
         "fields":{"manifest_no":manifest_no,"manifest_type":m_type,"transport":transport_id,
                   "carrier":carrier,"issue_date":issue_date.strftime("%Y-%m-%d"),
                   "port_airport_loading":from_loc,"port_airport_discharge":to_loc,
                   "agent":agent,"total_entries":len(entries),
                   "total_packages":total_pkgs,"total_gross_weight_kg":total_gw,"total_cbm":total_cbm,
                   "entries":entries}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} Cargo Manifest documents...")
    for i in range(1,count+1):
        a=generate_one(i); f=a["fields"]
        print(f"  [{i:04d}] {f['manifest_no']}  {f['manifest_type']}  {f['total_entries']} entries")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
