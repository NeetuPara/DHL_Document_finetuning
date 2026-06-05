"""
Synthetic Commercial Invoice — matches DHL Express original template.
Clean white form, title top-right (gray bg), exact column names, totals inside table.
"""
import json, random, argparse
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_line_items, random_invoice_number, random_vat_number,
    random_dhl_account, INCOTERMS, CURRENCIES, PAYMENT_TERMS, EXPORT_TYPES)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "01_Commercial_Invoice"
PDF_DIR, ANN_DIR = OUT_DIR/"pdfs", OUT_DIR/"annotations"

TITLE_BG = colors.HexColor("#D0D0D0")
HDR_BG   = colors.HexColor("#EEEEEE")
BORDER   = colors.HexColor("#555555")
LN       = colors.HexColor("#AAAAAA")
PAGE_W   = 186*mm
LW, RW   = 88*mm, 98*mm

def S(n,**k):
    d=dict(fontName="Helvetica",fontSize=8,leading=10,textColor=colors.black,spaceAfter=0,spaceBefore=0)
    d.update(k); return ParagraphStyle(n,**d)

ST = {
    "title":   S("t", fontName="Helvetica-Bold", fontSize=15, alignment=TA_CENTER),
    "lbl":     S("l", fontSize=7.5, textColor=colors.HexColor("#444444")),
    "val":     S("v", fontName="Helvetica-Bold", fontSize=8),
    "sm":      S("s", fontSize=7, leading=9),
    "ch":      S("ch", fontName="Helvetica-Bold", fontSize=7, alignment=TA_CENTER),
    "cd":      S("cd", fontSize=7, leading=9),
    "cdr":     S("cdr", fontSize=7, leading=9, alignment=TA_RIGHT),
    "cdc":     S("cdc", fontSize=7, leading=9, alignment=TA_CENTER),
    "tlbl":    S("tl", fontName="Helvetica-Bold", fontSize=7.5),
    "glbl":    S("gl", fontSize=8),
    "gval":    S("gv", fontName="Helvetica-Bold", fontSize=8.5),
    "decl":    S("dc", fontSize=7.5, leading=10),
    "sig":     S("sg", fontSize=8),
}

def P(t, s="cd"): return Paragraph(str(t), ST[s])
def lv(label, val):
    return [P(label,"lbl"), P(val,"val")]
def addr_blk(hdr, name, addr, phone, vat, extra=None):
    r=[P(hdr,"lbl"),P(name,"val"),P(addr,"sm"),Spacer(1,1.5*mm),
       P(f"Phone:      {phone}","sm"),P(f"VAT/GST No: {vat}","sm")]
    if extra:
        for k,v in extra.items(): r.append(P(f"{k}: {v}","sm"))
    return r

def generate_one(doc_id):
    sc = random_country(); rc = random_country()
    while rc[1]==sc[1]: rc=random_country()
    sn=random_company(); sa=fake.address().replace("\n",", ")+f", {sc[0]}"
    sp=fake.phone_number(); sv=random_vat_number(sc[1])
    rn=random_company(); ra=fake.address().replace("\n",", ")+f", {rc[0]}"
    rp=fake.phone_number(); rv=random_vat_number(rc[1]); ra2=random_dhl_account()
    dt=fake.date_between(start_date="-2y",end_date="today")
    inv=random_invoice_number(); ref=f"REF-{random.randint(100000,999999)}"
    awb=f"{random.randint(100,999)}-{random.randint(10000000,99999999)}"
    b3p=random.choice(["Yes","No","No","No"])
    cmt=random.choice(["","","Fragile - Handle with care","Sample - No commercial value",
                        f"PO# {random.randint(10000,99999)}","Diplomatic shipment"])
    cur=random.choice(CURRENCIES); inc=random.choice(INCOTERMS)
    pay=random.choice(PAYMENT_TERMS); exp=random.choice(EXPORT_TYPES)
    gst=random.choice(["Shipper","Receiver","Third Party"])
    con=fake.name()
    items=random_line_items(random.randint(1,7))
    tv=round(sum(i["total_value"] for i in items),2)
    tn=round(sum(i["total_weight_kg"] for i in items),2)
    tg=round(tn*random.uniform(1.05,1.25),2)
    tp=random.randint(len(items),len(items)*20)
    sig=fake.name()
    pos=random.choice(["Export Manager","Logistics Director","Operations Manager",
                       "Compliance Officer","Trade Manager","Finance Controller"])

    fname = f"commercial_invoice_{doc_id:04d}.pdf"
    doc = SimpleDocTemplate(str(PDF_DIR/fname), pagesize=A4,
                            leftMargin=12*mm,rightMargin=12*mm,topMargin=12*mm,bottomMargin=12*mm)
    story=[]

    # ── HEADER TABLE ─────────────────────────────────────────────────────
    # 8 rows x 2 cols. Spans: left rows 0-2 = shipper, left rows 3-5 = receiver
    # right rows 0-2 = title, right rows 3-5 = Date/Invoice/ShipRef
    # rows 6 and 7 span full width for Bill2TP/Comments and AWB
    s_blk = addr_blk("Shipper:", sn, sa, sp, sv)
    r_blk = addr_blk("Receiver:", rn, ra, rp, rv, {"DHL Account No": ra2})

    # Full-width row 6: Bill to Third Party | Comments (inner 2-col)
    b3p_row = Table([[
        [P("Bill to Third Party:", "lbl"), P(b3p, "val")],
        [P("Comments:", "lbl"), P(cmt if cmt else "-", "sm")],
    ]], colWidths=[LW, RW])
    b3p_row.setStyle(TableStyle([
        ("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))

    # Full-width row 7: Airway Bill Number
    awb_row = [P("Airway Bill Number:", "lbl"), P(awb, "val")]

    hdr = [
        [s_blk,  [Spacer(1,4*mm), P("Commercial Invoice","title"), Spacer(1,4*mm)]],
        ["",     ""],
        ["",     ""],
        [r_blk,  lv("Date:", dt.strftime("%d %b %Y"))],
        ["",     lv("Invoice Number:", inv)],
        ["",     lv("Shipment Reference:", ref)],
        [b3p_row,""],
        [awb_row,""],
    ]
    ROW_H=[None,None,None,None,6*mm,6*mm,None,None]
    ht=Table(hdr, colWidths=[LW,RW], rowHeights=ROW_H)
    ht.setStyle(TableStyle([
        ("SPAN",(0,0),(0,2)),("SPAN",(1,0),(1,2)),  # shipper / title
        ("SPAN",(0,3),(0,5)),                        # receiver
        ("SPAN",(0,6),(1,6)),                        # bill2tp row
        ("SPAN",(0,7),(1,7)),                        # awb row
        ("BACKGROUND",(1,0),(1,2),TITLE_BG),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),
        ("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("VALIGN",(1,0),(1,2),"MIDDLE"),
    ]))
    story.append(ht); story.append(Spacer(1,1*mm))

    # ── ITEMS TABLE ───────────────────────────────────────────────────────
    CW=[8*mm,50*mm,10*mm,10*mm,20*mm,17*mm,17*mm,17*mm,17*mm,20*mm]
    rows=[[P("No.","ch"),P("Full Description of Goods","ch"),P("Qty.","ch"),P("UOM","ch"),
           P("Commodity\nCode","ch"),P(f"Unit\nValue","ch"),P("Subtotal\nValue","ch"),
           P("Unit Net\nWeight","ch"),P("Subtotal\nWeight","ch"),P("Country of\nOrigin","ch")]]
    for i,it in enumerate(items,1):
        rows.append([P(i,"cdc"),P(it["description"],"cd"),P(it["qty"],"cdr"),
                     P(it["unit"],"cdc"),P(it["hs_code"],"cdc"),
                     P(f"{it['unit_value']:,.2f}","cdr"),P(f"{it['total_value']:,.2f}","cdr"),
                     P(f"{it['unit_weight_kg']:.3f}","cdr"),P(f"{it['total_weight_kg']:.2f}","cdr"),
                     P(it["country_of_origin"],"cd")])
    for _ in range(max(0,8-len(items))):
        rows.append([P("")]*10)
    # Totals — put label+value in same cell, span halves
    rows.append([P(f"Total Declared Value:    {cur} {tv:,.2f}","tlbl"),
                 "","","","","",
                 P(f"Total Net Weight:    {tn:,.3f} KG","tlbl"),
                 "","",""])
    rows.append([P(f"Total Pieces:    {tp}","tlbl"),
                 "","","","","",
                 P(f"Total Gross Weight:    {tg:,.3f} KG","tlbl"),
                 "","",""])
    tr1=1+len(items)+max(0,8-len(items)); tr2=tr1+1
    it_t=Table(rows,colWidths=CW,repeatRows=1)
    its=TableStyle([
        ("BACKGROUND",(0,0),(-1,0),HDR_BG),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("BOX",(0,0),(-1,-1),0.5,BORDER),("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("SPAN",(0,tr1),(5,tr1)),("SPAN",(6,tr1),(9,tr1)),
        ("SPAN",(0,tr2),(5,tr2)),("SPAN",(6,tr2),(9,tr2)),
        ("BACKGROUND",(0,tr1),(-1,tr2),colors.HexColor("#F5F5F5")),
    ])
    for r in range(1,1+len(items)):
        if r%2==0: its.add("BACKGROUND",(0,r),(-1,r),colors.HexColor("#FAFAFA"))
    it_t.setStyle(its)
    story.append(it_t); story.append(Spacer(1,3*mm))

    # ── GST/VAT SECTION ───────────────────────────────────────────────────
    gd=[[P("Payer of GST/VAT:","glbl"),P(gst,"gval"),P("Currency Code:","glbl"),P(cur,"gval")],
        [P("Type of Export:","glbl"),P(exp,"gval"),P("Incoterm:","glbl"),P(inc,"gval")],
        [P("Terms of Payment:","glbl"),P(pay,"gval"),P("","glbl"),P("","gval")]]
    gt=Table(gd,colWidths=[36*mm,46*mm,30*mm,74*mm])
    gt.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),
        ("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(gt); story.append(Spacer(1,3*mm))

    # ── SIGNATURE ─────────────────────────────────────────────────────────
    decl=("I/We hereby certify that the information of this invoice is true and correct "
          "and that the contents of this shipment are as stated above.")
    sd=[[P(decl,"decl"), P("")],
        [Spacer(1,6*mm), Spacer(1,6*mm)],
        [P("Signature:", "sig"), P("Company Stamp:", "sig")],
        [P(f"Position in Company:  {pos}", "sig"), P("")],
        [P(f"Shipping Consultant:  {con}", "sig"), P(sn, "sig")]]
    st2=Table(sd, colWidths=[PAGE_W*0.55, PAGE_W*0.45])
    st2.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,BORDER),
        ("INNERGRID",(0,0),(-1,-1),0.3,LN),
        ("SPAN",(0,0),(-1,0)),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(st2)
    doc.build(story)

    ann={"document_id":fname.replace(".pdf",""),"document_class":"Commercial Invoice","class_index":1,
         "fields":{"shipper_name":sn,"shipper_address":sa,"shipper_phone":sp,"shipper_vat":sv,
                   "shipper_country":sc[0],"shipper_country_code":sc[1],
                   "receiver_name":rn,"receiver_address":ra,"receiver_phone":rp,
                   "receiver_vat":rv,"receiver_dhl_account":ra2,
                   "receiver_country":rc[0],"receiver_country_code":rc[1],
                   "invoice_date":dt.strftime("%Y-%m-%d"),"invoice_number":inv,
                   "shipment_reference":ref,"airway_bill_number":awb,
                   "bill_to_third_party":b3p,"comments":cmt,"currency":cur,
                   "incoterm":inc,"payment_terms":pay,"export_type":exp,"gst_vat_payer":gst,
                   "total_declared_value":tv,"total_net_weight_kg":tn,
                   "total_gross_weight_kg":tg,"total_pieces":tp,
                   "signatory_name":sig,"signatory_position":pos,
                   "shipping_consultant":con,"line_items":items}}
    (ANN_DIR/fname.replace(".pdf",".json")).write_text(json.dumps(ann,indent=2))
    return ann

def generate(count=10):
    PDF_DIR.mkdir(parents=True,exist_ok=True)
    ANN_DIR.mkdir(parents=True,exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf"))+list(ANN_DIR.glob("*.json")): f.unlink()
    print(f"Generating {count} Commercial Invoice documents...")
    for i in range(1,count+1):
        a=generate_one(i)
        f=a["fields"]
        print(f"  [{i:04d}] {f['invoice_number']}  {f['currency']} {f['total_declared_value']:>12,.2f}  {len(f['line_items'])} items")
    print(f"\nDone -> {PDF_DIR}")

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser()
    p.add_argument("--count",type=int,default=10); args=p.parse_args()
    generate(args.count)
