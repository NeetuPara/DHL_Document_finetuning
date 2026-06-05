"""Power of Attorney — DHL / customs broker authorization form."""
import json, random
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import fake, random, random_company, random_country

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "12_Power_of_Attorney"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"
BORDER=colors.HexColor("#555555"); LN=colors.HexColor("#BBBBBB"); PAGE_W=166*mm

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=9,leading=12,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)
ST={"title":S("t",fontName="Helvetica-Bold",fontSize=14,alignment=TA_CENTER),
    "sub":S("s",fontSize=9,alignment=TA_CENTER),"hdr":S("h",fontName="Helvetica-Bold",fontSize=10),
    "lbl":S("l",fontSize=8,textColor=colors.HexColor("#444444")),
    "val":S("v",fontName="Helvetica-Bold",fontSize=9.5),"sm":S("sm",fontSize=8.5,leading=12),
    "body":S("b",fontSize=9,leading=13),
    "sig_lbl":S("sl",fontName="Helvetica-Bold",fontSize=9),"note":S("nt",fontSize=7.5,leading=10,textColor=colors.HexColor("#555555")),}
def P(t,s="body"): return Paragraph(str(t),ST[s])

POA_SCOPES=[("Export","to transact business, including but not limited to the preparation and filing of Electronic Export Information (EEI) through the Automated Export System (AES), and to act as agent for export"),
            ("Import","to transact customs business, including the making of entry, the execution of bonds, and to perform other acts required by law"),
            ("Export and Import","to transact all customs and export business, including Electronic Export Information (EEI) filing, customs entry, bond execution, and all related documentation and regulatory compliance")]
AGENT_ENTITIES=["DHL Global Forwarding (USA) Inc.","DHL Global Forwarding Ltd.","DHL Express (USA) Inc.","DB Schenker Inc.","Kuehne + Nagel Inc.","Expeditors International of Washington, Inc.","C.H. Robinson International, Inc."]

def generate_one(doc_id):
    sc=random_country()
    grantor=random_company(); grantor_addr=fake.address().replace("\n",", ")+", "+sc[0]
    grantor_state=fake.state() if sc[1]=="US" else fake.city()
    grantor_ein=fake.bothify("##-#######")
    grantor_duns=fake.bothify("#########")
    authorized_person=fake.name()
    auth_title=random.choice(["President","CEO","CFO","Vice President Operations","Export Compliance Manager",
                               "Director of Logistics","General Manager","Managing Director"])
    agent=random.choice(AGENT_ENTITIES)
    scope_type,scope_desc=random.choice(POA_SCOPES)
    issue_date=fake.date_between(start_date="-2y",end_date="today")
    effective_date=issue_date
    expiry_years=random.choice([1,2,3,5,"indefinite"])
    notary=fake.name(); notary_state=fake.state() if sc[1]=="US" else fake.city()
    notary_county=fake.city() if sc[1]=="US" else ""
    notary_exp=fake.date_between(start_date="today",end_date="+3y")
    witness1=fake.name(); witness2=fake.name()
    poa_no=f"POA-{random.randint(100000,999999)}"

    fname=f"poa_{doc_id:04d}.pdf"
    doc=SimpleDocTemplate(str(PDF_DIR/fname),pagesize=A4,
                          leftMargin=22*mm,rightMargin=22*mm,topMargin=15*mm,bottomMargin=15*mm)
    story=[]

    # Title
    story.append(P("POWER OF ATTORNEY","title")); story.append(Spacer(1,1*mm))
    story.append(P("Customs and Trade Compliance Authorization","sub")); story.append(Spacer(1,4*mm))
    story.append(HRFlowable(width=PAGE_W,thickness=1.5,color=BORDER)); story.append(Spacer(1,4*mm))

    # Reference / Date
    ref=Table([[P("POA Reference No.:","lbl"),P(poa_no,"val"),P("Effective Date:","lbl"),P(effective_date.strftime("%d %B %Y"),"val"),
                P("Expiry:","lbl"),P(str(expiry_years)+" year(s)" if expiry_years!="indefinite" else "Indefinite","val")]],
              colWidths=[32*mm,42*mm,26*mm,36*mm,16*mm,14*mm])
    ref.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#EEEEEE")),("BACKGROUND",(2,0),(2,0),colors.HexColor("#EEEEEE")),
        ("BACKGROUND",(4,0),(4,0),colors.HexColor("#EEEEEE"))]))
    story.append(ref); story.append(Spacer(1,4*mm))

    # Grantor details
    story.append(P("GRANTOR (Principal Party in Interest)","hdr")); story.append(Spacer(1,1*mm))
    gr=Table([[P("Company / Individual Name:","lbl"),P(grantor,"val")],
              [P("Address:","lbl"),P(grantor_addr,"sm")],
              [P("EIN / Tax ID:","lbl"),P(grantor_ein,"sm")],
              [P("DUNS Number:","lbl"),P(grantor_duns,"sm")]],
             colWidths=[46*mm,120*mm])
    gr.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F5F5F5"))]))
    story.append(gr); story.append(Spacer(1,3*mm))

    # Agent
    story.append(P("GRANTEE (Authorized Agent)","hdr")); story.append(Spacer(1,1*mm))
    ag=Table([[P("Agent / Customs Broker:","lbl"),P(agent,"val")]],colWidths=[46*mm,120*mm])
    ag.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F5F5F5"))]))
    story.append(ag); story.append(Spacer(1,4*mm))

    # Authorization body
    scope_txt=(f"KNOW ALL PERSONS BY THESE PRESENTS, that the undersigned, {grantor}, organized and existing "
               f"under the laws of {sc[0]}, having its principal place of business at {grantor_addr}, "
               f"hereby constitutes and appoints {agent} as its true and lawful agent and attorney in fact "
               f"for and in its name, place and stead, {scope_desc}, before the Bureau of Industry and Security, "
               f"U.S. Customs and Border Protection, and any other government agencies as required.")
    story.append(P(scope_txt,"body")); story.append(Spacer(1,3*mm))
    story.append(P(f"<b>SCOPE OF AUTHORIZATION:  {scope_type}</b>","body")); story.append(Spacer(1,2*mm))
    story.append(P("This Power of Attorney shall remain in full force and effect until revoked in writing by "
                   "the Grantor, with written notice delivered to the Grantee at least 30 days prior to the "
                   "intended date of revocation.","body")); story.append(Spacer(1,4*mm))

    # Signature block
    story.append(HRFlowable(width=PAGE_W,thickness=0.5,color=colors.HexColor("#AAAAAA")))
    story.append(Spacer(1,3*mm))
    story.append(P("EXECUTED BY AUTHORIZED OFFICER:","hdr")); story.append(Spacer(1,2*mm))
    sig=Table([[P("Signature:","sig_lbl"),P("_________________________________","sm"),
                P("Date:","sig_lbl"),P(issue_date.strftime("%d %B %Y"),"sm")],
               [P("Printed Name:","sig_lbl"),P(authorized_person,"sm"),P("","sig_lbl"),P("","sm")],
               [P("Title:","sig_lbl"),P(auth_title,"sm"),P("","sig_lbl"),P("","sm")],
               [P("Company:","sig_lbl"),P(grantor,"sm"),P("","sig_lbl"),P("","sm")]],
              colWidths=[28*mm,56*mm,16*mm,66*mm])
    sig.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F5F5F5"))]))
    story.append(sig); story.append(Spacer(1,4*mm))

    # Notarization
    story.append(P("NOTARIZATION / CERTIFICATION:","hdr")); story.append(Spacer(1,2*mm))
    notary_text=(f"State of {notary_state}{(', County of '+notary_county) if notary_county else ''}\n"
                 f"Subscribed and sworn before me, {notary}, Notary Public, on {issue_date.strftime('%d %B %Y')}.\n"
                 f"My commission expires: {notary_exp.strftime('%d %B %Y')}")
    nt=Table([[P(notary_text,"sm")]],colWidths=[PAGE_W])
    nt.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(-1,-1),6),
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#FFFDE7"))]))
    story.append(nt); story.append(Spacer(1,3*mm))

    # Witnesses
    wt=Table([[P(f"Witness 1: {witness1}","sm"),P(f"Witness 2: {witness2}","sm")],
              [P("Signature: ___________________________","sm"),P("Signature: ___________________________","sm")]],
             colWidths=[PAGE_W//2,PAGE_W//2])
    wt.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5)]))
    story.append(wt)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Power of Attorney","class_index":12,
         "fields":{"poa_reference":poa_no,"grantor_name":grantor,"grantor_address":grantor_addr,
                   "grantor_ein":grantor_ein,"authorized_person":authorized_person,"title":auth_title,
                   "agent_name":agent,"scope":scope_type,"effective_date":effective_date.strftime("%Y-%m-%d"),
                   "expiry":str(expiry_years),"notary":notary,"issue_date":issue_date.strftime("%Y-%m-%d")}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True); ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} Power of Attorney documents...")
    for i in range(1,count+1):
        a=generate_one(i); f=a["fields"]
        print(f"  [{i:04d}] {f['poa_reference']}  {f['grantor_name']}  Scope: {f['scope']}")
    print(f"Done -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=10)
    generate(p.parse_args().count)
