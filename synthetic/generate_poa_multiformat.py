"""
Power of Attorney — 3 distinct real-world format variants.
Format 1: Standard Customs POA (DHL style) — company letterhead, notarization block
Format 2: Limited/Specific POA — single-transaction or time-limited authorization
Format 3: Corporate/Legal Style POA — full legal language, recitals, numbered paragraphs
Generates 1000 diverse documents distributed across all 3 formats.
"""
import json, random, argparse
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import sys; sys.path.insert(0, str(Path(__file__).parent))
from data_generators import (fake, random, random_company, random_country,
    random_hawb_number, random_mawb_number, random_bl_number, random_invoice_number,
    random_vat_number, AIRPORTS, PORTS_SEA, VESSEL_NAMES, CURRENCIES,
    COMMODITY_CATEGORIES, PACKAGE_TYPES, INCOTERMS)

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "12_Power_of_Attorney"
PDF_DIR, ANN_DIR = OUT_DIR / "pdfs", OUT_DIR / "annotations"

W = 186 * mm
BORDER = colors.HexColor("#444444")
LN = colors.HexColor("#CCCCCC")

def S(n, **k):
    d = dict(fontName="Helvetica", fontSize=8, leading=10,
             textColor=colors.black, spaceAfter=0, spaceBefore=0)
    d.update(k)
    return ParagraphStyle(n, **d)

def P(t, s):
    return Paragraph(str(t), s)


# ── Synthetic data builder ─────────────────────────────────────────────────
def make_data():
    sc = random_country()
    grantor_name = random_company()
    grantor_address = fake.address().replace("\n", ", ") + f", {sc[0]}"
    grantor_ein = fake.bothify("##-#######")
    grantor_duns = fake.bothify("#########")
    authorized_person = fake.name()
    authorized_title = random.choice([
        "President", "Chief Executive Officer", "Chief Financial Officer",
        "Vice President Operations", "Director of Logistics", "Compliance Officer",
        "Export Manager", "Import Manager", "Corporate Secretary",
    ])

    agents = ["DHL Express", "DHL Global Forwarding", "DHL Supply Chain",
              "Customs Broker International LLC", "Trade Compliance Partners Inc.",
              "Global Customs Services Ltd", "International Freight Associates"]
    agent_name = random.choice(agents)

    scopes = ["Import Only", "Export Only", "Import and Export", "Customs Clearance", "All Trade Activities"]
    scope = random.choice(scopes)

    effective_date = fake.date_between(start_date="-1y", end_date="today")
    expiry = fake.date_between(start_date=effective_date, end_date="+3y")
    issue_date = effective_date

    us_states = ["California", "New York", "Texas", "Florida", "Illinois",
                 "Washington", "Georgia", "New Jersey", "Pennsylvania", "Ohio"]
    notary_state = random.choice(us_states)
    notary_county = fake.city()
    notary_name = fake.name()
    notary_commission = fake.date_between(start_date="today", end_date="+5y")
    witness1 = fake.name()
    witness2 = fake.name()

    # Fmt2 specific
    entry_ref = fake.bothify("###-########-#")
    specific_goods = random.choice(COMMODITY_CATEGORIES)["description"]
    specific_hts = random.choice(COMMODITY_CATEGORIES)["hs_code"]
    restriction_clauses = [
        "Limited to a single customs entry as specified above.",
        f"Valid only for shipments originating from {random_country()[0]}.",
        "Restricted to the specific goods described herein.",
        "Subject to annual review and renewal by the grantor.",
        "Not valid for any shipment exceeding USD 50,000 in value.",
    ]

    # Fmt3 authority list
    authority_items = [
        "To sign, execute, file, and withdraw any and all customs entries on behalf of the Grantor.",
        "To make, sign, and endorse checks and drafts payable to the United States Treasury for duties.",
        "To execute any bond or other obligation required by law or regulation.",
        "To sign and file export declarations and Electronic Export Information (EEI).",
        "To receive, endorse, and collect the proceeds of any check, note, or other instrument.",
        "To appear before any officer of the United States Customs and Border Protection.",
        "To execute protests and appeals relating to customs duties, classifications, and valuations.",
        "To authorize and designate sub-agents for the purposes set forth herein.",
        "To execute and file any documents required for compliance with export control regulations.",
        "To perform all acts necessary and proper to carry out the foregoing powers.",
    ]

    corp_resolution_no = fake.bothify("CR-####-##")
    governing_law_state = random.choice(us_states)
    secretary_name = fake.name()
    ceo_name = fake.name()

    return dict(
        poa_reference=f"POA-{fake.bothify('####-######')}",
        grantor_name=grantor_name,
        grantor_address=grantor_address,
        grantor_ein=grantor_ein,
        grantor_duns=grantor_duns,
        grantor_country=sc,
        authorized_person=authorized_person,
        authorized_title=authorized_title,
        agent_name=agent_name,
        scope=scope,
        effective_date=effective_date,
        expiry=expiry,
        issue_date=issue_date,
        notary_state=notary_state,
        notary_county=notary_county,
        notary_name=notary_name,
        notary_commission=notary_commission,
        witness1=witness1,
        witness2=witness2,
        entry_ref=entry_ref,
        specific_goods=specific_goods,
        specific_hts=specific_hts,
        restriction_clauses=restriction_clauses,
        authority_items=authority_items,
        corp_resolution_no=corp_resolution_no,
        governing_law_state=governing_law_state,
        secretary_name=secretary_name,
        ceo_name=ceo_name,
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — Standard Customs POA (DHL style)
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    NAVY = colors.HexColor("#00205B")
    RED_DHL = colors.HexColor("#D40511")
    LIGHT = colors.HexColor("#E8EDF5")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, textColor=colors.white),
        "brand":  S("br", fontName="Helvetica-Bold", fontSize=16, textColor=RED_DHL),
        "lbl":    S("l", fontSize=6.5, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=8),
        "sm":     S("sm", fontSize=7.5, leading=10),
        "body":   S("bd", fontSize=8, leading=12),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=8),
        "sec":    S("sec", fontName="Helvetica-Bold", fontSize=8.5, textColor=NAVY),
        "notary": S("nt", fontSize=7, leading=9, textColor=colors.HexColor("#444444")),
        "foot":   S("ft", fontSize=6.5, textColor=colors.HexColor("#888888"), alignment=TA_CENTER),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    W1 = 174 * mm
    story = []

    # DHL Letterhead
    lh = Table([[
        [Ps("DHL", "brand"), Ps("GLOBAL FORWARDING", "sm"),
         Ps(d["agent_name"], "sm")],
        [Ps("POWER OF ATTORNEY", "title"),
         Ps("CUSTOMS POWER OF ATTORNEY", "title")],
    ]], colWidths=[60*mm, 114*mm])
    lh.setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(lh)
    story.append(Spacer(1, 2*mm))

    # POA reference + date
    ref_t = Table([[
        Ps("POA REFERENCE", "lbl"), Ps(d["poa_reference"], "val"),
        Ps("EFFECTIVE DATE", "lbl"), Ps(d["effective_date"].strftime("%d %B %Y"), "val"),
        Ps("EXPIRY DATE", "lbl"), Ps(d["expiry"].strftime("%d %B %Y"), "val"),
        Ps("SCOPE", "lbl"), Ps(d["scope"], "val"),
    ]], colWidths=[24*mm, 32*mm, 24*mm, 30*mm, 22*mm, 30*mm, 14*mm, 24*mm])
    ref_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, 0), LIGHT), ("BACKGROUND", (2, 0), (2, 0), LIGHT),
        ("BACKGROUND", (4, 0), (4, 0), LIGHT), ("BACKGROUND", (6, 0), (6, 0), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(ref_t)
    story.append(Spacer(1, 2*mm))

    # Grantor details
    gran_t = Table([[
        [Ps("GRANTOR (PRINCIPAL)", "sec"),
         Spacer(1, 1*mm),
         Ps("Company / Legal Name:", "lbl"), Ps(d["grantor_name"], "val"),
         Ps("Registered Address:", "lbl"), Ps(d["grantor_address"], "sm"),
         Ps("EIN / Tax ID:", "lbl"), Ps(d["grantor_ein"], "val"),
         Ps("DUNS Number:", "lbl"), Ps(d["grantor_duns"], "val")],
        [Ps("GRANTEE (AGENT)", "sec"),
         Spacer(1, 1*mm),
         Ps("Agent / Broker:", "lbl"), Ps(d["agent_name"], "val"),
         Spacer(1, 2*mm),
         Ps("AUTHORIZED REPRESENTATIVE", "sec"),
         Ps("Name:", "lbl"), Ps(d["authorized_person"], "val"),
         Ps("Title:", "lbl"), Ps(d["authorized_title"], "val")],
    ]], colWidths=[87*mm, 87*mm])
    gran_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(gran_t)
    story.append(Spacer(1, 3*mm))

    # Authorization body text
    auth_body = (
        f"KNOW ALL PERSONS BY THESE PRESENTS: That {d['grantor_name']}, "
        f"a corporation organized and existing under the laws of {d['grantor_country'][0]}, "
        f"with its principal office at {d['grantor_address']}, hereby authorizes and appoints "
        f"{d['agent_name']}, its true and lawful agent and attorney, for and in its name, "
        f"place, and stead, to make, endorse, sign, declare, or swear to any entry, withdrawal, "
        f"declaration, certificate, bill of lading, or any other document required by law or "
        f"regulation in connection with the importation, exportation, or transportation of any "
        f"merchandise shipped or consigned by or to said principal; to perform any act or "
        f"condition which may be required by law or regulation in connection with such merchandise; "
        f"to receive any merchandise and to make any payment."
    )
    story.append(Table([[Ps(auth_body, "body")]], colWidths=[W1],
                       style=TableStyle([
                           ("BOX", (0, 0), (-1, -1), .5, BORDER),
                           ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                       ])))
    story.append(Spacer(1, 3*mm))

    # Signature block
    sig_t = Table([[
        [Ps("AUTHORIZED OFFICER SIGNATURE", "sec"),
         Spacer(1, 6*mm),
         Ps("Signature: _______________________________", "sm"),
         Spacer(1, 1*mm),
         Ps(f"Name: {d['authorized_person']}", "sm"),
         Ps(f"Title: {d['authorized_title']}", "sm"),
         Ps(f"{d['grantor_name']}", "sm"),
         Ps(f"Date: {d['issue_date'].strftime('%d %B %Y')}", "sm")],
        [Ps("WITNESS 1", "sec"),
         Spacer(1, 6*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"Name: {d['witness1']}", "sm"),
         Spacer(1, 3*mm),
         Ps("WITNESS 2", "sec"),
         Spacer(1, 6*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"Name: {d['witness2']}", "sm")],
    ]], colWidths=[100*mm, 74*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    story.append(Spacer(1, 2*mm))

    # Notarization block
    notary_text = (
        f"State of {d['notary_state']}, County of {d['notary_county']}\n\n"
        f"Before me, {d['notary_name']}, a Notary Public, on this day personally appeared "
        f"{d['authorized_person']}, known to me to be the {d['authorized_title']} of "
        f"{d['grantor_name']}, and acknowledged to me that he/she executed the foregoing "
        f"Power of Attorney for the purposes therein expressed.\n\n"
        f"Witness my hand and official seal.\n\n"
        f"Notary Public: _______________________________\n"
        f"Commission Expires: {d['notary_commission'].strftime('%d %B %Y')}"
    )
    story.append(Table([[Ps(notary_text, "notary")]], colWidths=[W1],
                       style=TableStyle([
                           ("BOX", (0, 0), (-1, -1), .5, BORDER),
                           ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F5F5")),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8),
                       ])))
    story.append(Spacer(1, 2*mm))
    story.append(P(f"POA Ref: {d['poa_reference']}  |  {d['grantor_name']}  |  "
                   f"Effective: {d['effective_date'].strftime('%d %b %Y')}  |  "
                   f"Expires: {d['expiry'].strftime('%d %b %Y')}",
                   st["foot"]))
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — Limited / Specific POA
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    AMBER = colors.HexColor("#E65100")
    LAMBER = colors.HexColor("#FFF3E0")
    MAMBER = colors.HexColor("#FFE0B2")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER, textColor=colors.white),
        "lbl":    S("l", fontSize=7, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=8.5),
        "sm":     S("sm", fontSize=7.5, leading=10),
        "body":   S("bd", fontSize=8, leading=12),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=8.5),
        "expiry": S("ex", fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER, textColor=AMBER),
        "sec":    S("sec", fontName="Helvetica-Bold", fontSize=8.5, textColor=AMBER),
        "warn":   S("w", fontSize=7.5, textColor=colors.HexColor("#B71C1C")),
        "item":   S("it", fontSize=7.5, leading=10),
        "foot":   S("ft", fontSize=6.5, textColor=colors.HexColor("#888888"), alignment=TA_CENTER),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    W2 = 174 * mm
    story = []

    # Title
    story.append(Table([[
        Ps("LIMITED POWER OF ATTORNEY", "title"),
        Ps("SPECIFIC / TIME-LIMITED AUTHORIZATION", "title"),
    ]], colWidths=[100*mm, 74*mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AMBER),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("INNERGRID", (0, 0), (-1, -1), .5, colors.white),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
    ])))
    story.append(Spacer(1, 2*mm))

    # Expiry prominent display
    story.append(Table([[
        [Ps("POA REFERENCE", "lbl"), Ps(d["poa_reference"], "bold")],
        [Ps("ENTRY / SHIPMENT REFERENCE", "lbl"), Ps(d["entry_ref"], "bold")],
    ], [
        Ps("EXPIRY DATE", "lbl"),
        Ps(d["expiry"].strftime("%d %B %Y"), "expiry"),
    ]], colWidths=[W2], style=TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, -1), LAMBER),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ])))
    story.append(Spacer(1, 2*mm))

    # Grantor + Grantee
    party_t = Table([[
        [Ps("GRANTOR (PRINCIPAL)", "sec"),
         Ps("Name:", "lbl"), Ps(d["grantor_name"], "val"),
         Ps("Address:", "lbl"), Ps(d["grantor_address"], "sm"),
         Ps("EIN:", "lbl"), Ps(d["grantor_ein"], "val")],
        [Ps("GRANTEE (AUTHORIZED AGENT)", "sec"),
         Ps("Agent:", "lbl"), Ps(d["agent_name"], "val"),
         Spacer(1, 2*mm),
         Ps("AUTHORIZED PERSON", "sec"),
         Ps("Name:", "lbl"), Ps(d["authorized_person"], "val"),
         Ps("Title:", "lbl"), Ps(d["authorized_title"], "val")],
    ]], colWidths=[87*mm, 87*mm])
    party_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, -1), LAMBER),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(party_t)
    story.append(Spacer(1, 2*mm))

    # Limited scope description
    scope_text = (
        f"This Limited Power of Attorney authorizes {d['agent_name']} to act as agent "
        f"for {d['grantor_name']} for the SOLE PURPOSE of clearing the following specific "
        f"shipment through U.S. Customs and Border Protection. This authorization is "
        f"strictly limited and does not extend to any other shipment or transaction."
    )
    story.append(Table([[Ps(scope_text, "body")]], colWidths=[W2],
                       style=TableStyle([
                           ("BOX", (0, 0), (-1, -1), .5, BORDER),
                           ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                       ])))
    story.append(Spacer(1, 2*mm))

    # Specific goods + HTS
    goods_t = Table([[
        Ps("SPECIFIC GOODS AUTHORIZED", "lbl"),
        Ps("HTS / HS CODE", "lbl"),
        Ps("ENTRY REFERENCE", "lbl"),
    ], [
        Ps(d["specific_goods"][:60], "sm"),
        Ps(d["specific_hts"], "val"),
        Ps(d["entry_ref"], "val"),
    ]], colWidths=[100*mm, 34*mm, 40*mm])
    goods_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, 0), MAMBER),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(goods_t)
    story.append(Spacer(1, 2*mm))

    # Restriction clauses
    story.append(Ps("RESTRICTION CLAUSES AND CONDITIONS:", "sec"))
    story.append(Spacer(1, 1*mm))
    for i, clause in enumerate(d["restriction_clauses"][:4], 1):
        story.append(P(f"{i}. {clause}", st["item"]))
        story.append(Spacer(1, 1*mm))
    story.append(Spacer(1, 1*mm))
    story.append(P("WARNING: This authorization is non-transferable and expires on the date shown above. "
                   "Unauthorized use of this document may result in civil and criminal liability.",
                   st["warn"]))
    story.append(Spacer(1, 3*mm))

    # Signature
    sig_t = Table([[
        [Ps("GRANTOR SIGNATURE", "sec"),
         Spacer(1, 6*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"Name: {d['authorized_person']}", "sm"),
         Ps(f"Title: {d['authorized_title']}", "sm"),
         Ps(f"Company: {d['grantor_name']}", "sm"),
         Ps(f"Date: {d['issue_date'].strftime('%d %B %Y')}", "sm")],
        [Ps("EFFECTIVE / EXPIRY", "sec"),
         Spacer(1, 3*mm),
         Ps(f"Effective: {d['effective_date'].strftime('%d %b %Y')}", "bold"),
         Ps(f"Expires:  {d['expiry'].strftime('%d %b %Y')}", "expiry"),
         Spacer(1, 3*mm),
         Ps("WITNESS", "sec"),
         Ps(f"{d['witness1']}", "sm"),
         Ps("Signature: _______________________________", "sm")],
    ]], colWidths=[100*mm, 74*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, -1), LAMBER),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    story.append(Spacer(1, 2*mm))
    story.append(P(f"Limited POA  |  Ref: {d['poa_reference']}  |  Entry: {d['entry_ref']}  |  "
                   f"Grantor: {d['grantor_name']}  |  Agent: {d['agent_name']}",
                   st["foot"]))
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — Corporate / Legal Style POA
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    DARK = colors.HexColor("#212121")
    LGRAY = colors.HexColor("#F5F5F5")
    MGRAY = colors.HexColor("#E0E0E0")
    GOLD3 = colors.HexColor("#B8860B")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER, textColor=DARK),
        "know":   S("kn", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=DARK),
        "lbl":    S("l", fontSize=7, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=8.5),
        "sm":     S("sm", fontSize=8, leading=11),
        "body":   S("bd", fontSize=8, leading=12.5),
        "legal":  S("lg", fontSize=7.5, leading=11, textColor=DARK),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=8.5),
        "para":   S("par", fontSize=8, leading=12, firstLineIndent=10),
        "num":    S("nm", fontName="Helvetica-Bold", fontSize=8),
        "sec":    S("sec", fontName="Helvetica-Bold", fontSize=9, textColor=DARK),
        "seal":   S("sl", fontSize=7, alignment=TA_CENTER, textColor=colors.HexColor("#888888")),
        "foot":   S("ft", fontSize=6.5, textColor=colors.HexColor("#888888"), alignment=TA_CENTER),
        "recital":S("rc", fontSize=8, leading=12, textColor=DARK),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    W3 = 170 * mm
    story = []

    # Header border line
    story.append(HRFlowable(width=W3, thickness=3, color=DARK))
    story.append(Spacer(1, 2*mm))

    # Title
    story.append(P("CUSTOMS POWER OF ATTORNEY", st["title"]))
    story.append(Spacer(1, 1*mm))
    story.append(HRFlowable(width=W3, thickness=1, color=GOLD3))
    story.append(Spacer(1, 2*mm))

    # Reference block
    ref_t = Table([[
        Ps("Document Reference:", "lbl"), Ps(d["poa_reference"], "bold"),
        Ps("Corporate Resolution:", "lbl"), Ps(d["corp_resolution_no"], "bold"),
        Ps("Date:", "lbl"), Ps(d["issue_date"].strftime("%d %B %Y"), "bold"),
    ]], colWidths=[36*mm, 36*mm, 36*mm, 30*mm, 12*mm, 20*mm])
    ref_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, -1), LGRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(ref_t)
    story.append(Spacer(1, 3*mm))

    # KNOW ALL PERSONS recital
    story.append(P("KNOW ALL PERSONS BY THESE PRESENTS:", st["know"]))
    story.append(Spacer(1, 2*mm))

    # Whereas clauses
    whereas_clauses = [
        f"WHEREAS, {d['grantor_name']} (hereinafter referred to as the \"Principal\") is a corporation "
        f"duly organized and existing under applicable laws, with its principal place of business at "
        f"{d['grantor_address']};",
        f"WHEREAS, the Principal desires to authorize {d['agent_name']} (hereinafter referred to as "
        f"the \"Agent\") to act on its behalf in connection with import and export transactions;",
        f"WHEREAS, the Board of Directors of the Principal has duly authorized the execution of this "
        f"Power of Attorney by Corporate Resolution No. {d['corp_resolution_no']};",
        "WHEREAS, the Agent possesses the expertise, licenses, and authority necessary to perform "
        "the duties herein described;",
    ]
    for wh in whereas_clauses:
        story.append(P(wh, st["recital"]))
        story.append(Spacer(1, 1.5*mm))
    story.append(Spacer(1, 1*mm))

    story.append(P("NOW, THEREFORE, in consideration of the mutual covenants and agreements set forth "
                   "herein, and for other good and valuable consideration, the receipt and sufficiency "
                   "of which are hereby acknowledged, the Principal hereby grants to the Agent the "
                   "following powers and authorities:", st["body"]))
    story.append(Spacer(1, 2*mm))

    # Numbered authority list
    story.append(Ps("AGENT AUTHORITY:", "sec"))
    story.append(Spacer(1, 1*mm))
    for i, item in enumerate(d["authority_items"], 1):
        story.append(P(f"  {i}.  {item}", st["para"]))
        story.append(Spacer(1, 1*mm))
    story.append(Spacer(1, 2*mm))

    # Ratification + governing law
    rat_text = (
        f"RATIFICATION: The Principal hereby ratifies and confirms all acts lawfully done by the "
        f"Agent pursuant to this Power of Attorney. This Power of Attorney shall be effective as "
        f"of {d['effective_date'].strftime('%d %B %Y')} and shall remain in full force and effect "
        f"until {d['expiry'].strftime('%d %B %Y')}, unless sooner revoked in writing.\n\n"
        f"GOVERNING LAW: This Power of Attorney shall be governed by and construed in accordance "
        f"with the laws of the State of {d['governing_law_state']}, without regard to its "
        f"conflict of law provisions."
    )
    story.append(Table([[Ps(rat_text, "legal")]], colWidths=[W3],
                       style=TableStyle([
                           ("BOX", (0, 0), (-1, -1), .5, BORDER),
                           ("BACKGROUND", (0, 0), (-1, -1), LGRAY),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                       ])))
    story.append(Spacer(1, 3*mm))

    # IN WITNESS WHEREOF
    story.append(P("IN WITNESS WHEREOF, the Principal has caused this Power of Attorney to be "
                   "executed by its duly authorized officers as of the date first written above.",
                   st["body"]))
    story.append(Spacer(1, 3*mm))

    # Multiple signature lines: CEO + Secretary + Corporate Seal
    sig_t = Table([[
        [Ps("CHIEF EXECUTIVE OFFICER", "sec"),
         Spacer(1, 8*mm),
         Ps("____________________________", "seal"),
         Ps(f"{d['ceo_name']}", "sm"),
         Ps("Chief Executive Officer", "sm"),
         Ps(d["grantor_name"][:30], "sm"),
         Ps(f"Date: ______________", "sm")],
        [Ps("CORPORATE SEAL", "sec"),
         Spacer(1, 10*mm),
         Ps("[CORPORATE SEAL]", "seal"),
         Ps("(Affix Corporate Seal Here)", "seal")],
        [Ps("CORPORATE SECRETARY", "sec"),
         Spacer(1, 8*mm),
         Ps("____________________________", "seal"),
         Ps(f"{d['secretary_name']}", "sm"),
         Ps("Corporate Secretary", "sm"),
         Ps(d["grantor_name"][:30], "sm"),
         Ps(f"Date: ______________", "sm")],
    ]], colWidths=[66*mm, 38*mm, 66*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (1, 0), (1, 0), MGRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    story.append(Spacer(1, 2*mm))
    story.append(HRFlowable(width=W3, thickness=1, color=GOLD3))
    story.append(Spacer(1, 1*mm))
    story.append(P(f"Corporate POA  |  {d['poa_reference']}  |  Resolution No. {d['corp_resolution_no']}  |  "
                   f"Governing Law: {d['governing_law_state']}  |  Expires: {d['expiry'].strftime('%d %b %Y')}",
                   st["foot"]))
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["Standard-Customs-POA-DHL-Style", "Limited-Specific-POA", "Corporate-Legal-Style-POA"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"poa_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Base fields rendered in all 3 format PDFs:
    fields = {
        "poa_reference": d["poa_reference"],
        "grantor_name": d["grantor_name"],
        "grantor_address": d["grantor_address"],
        "authorized_person": d["authorized_person"],
        "authorized_title": d["authorized_title"],
        "agent_name": d["agent_name"],
        "effective_date": d["effective_date"].strftime("%Y-%m-%d"),
        "expiry_date": d["expiry"].strftime("%Y-%m-%d"),
        "issue_date": d["issue_date"].strftime("%Y-%m-%d"),
    }
    # fmt1 (Standard-Customs-POA-DHL-Style): renders grantor_ein, grantor_duns, scope,
    #   notary block (notary_state, notary_county, notary_name, notary_commission),
    #   and both witness1 + witness2
    if fmt_idx == 0:
        fields["grantor_ein"] = d["grantor_ein"]
        fields["grantor_duns"] = d["grantor_duns"]
        fields["grantor_country"] = d["grantor_country"][0]
        fields["scope"] = d["scope"]
        fields["notary_state"] = d["notary_state"]
        fields["notary_county"] = d["notary_county"]
        fields["notary_name"] = d["notary_name"]
        fields["notary_commission_expiry"] = d["notary_commission"].strftime("%Y-%m-%d")
        fields["witness1"] = d["witness1"]
        fields["witness2"] = d["witness2"]
    # fmt2 (Limited-Specific-POA): renders grantor_ein, entry_ref, specific_goods,
    #   specific_hts, and witness1 only (no notary block, no DUNS, no scope, no witness2)
    #   grantor_country is visible as the last token of grantor_address in the party table
    if fmt_idx == 1:
        fields["grantor_country"] = d["grantor_country"][0]
        fields["grantor_ein"] = d["grantor_ein"]
        fields["entry_reference"] = d["entry_ref"]
        fields["specific_goods"] = d["specific_goods"]
        fields["specific_hts_code"] = d["specific_hts"]
        fields["witness1"] = d["witness1"]
    # fmt3 (Corporate-Legal-Style-POA): renders corp_resolution_no, governing_law_state,
    #   ceo_name, secretary_name; no grantor_ein, no DUNS, no scope, no notary, no witnesses
    #   grantor_country is visible as the last token of grantor_address in the WHEREAS clause
    if fmt_idx == 2:
        fields["grantor_country"] = d["grantor_country"][0]
        fields["corp_resolution_no"] = d["corp_resolution_no"]
        fields["governing_law_state"] = d["governing_law_state"]
        fields["ceo_name"] = d["ceo_name"]
        fields["secretary_name"] = d["secretary_name"]

    ann = {
        "document_id":    fname.replace(".pdf", ""),
        "document_class": "Power of Attorney",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    12,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf", ".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} Power of Attorney documents (3 format variants)...")
    for i in range(1, count + 1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            print(f"  [{i:04d}] {a['format_variant'][:30]:<30}  Ref: {f['poa_reference']}  "
                  f"Grantor: {f['grantor_name'][:25]}  Expires: {f['expiry_date']}")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate synthetic Power of Attorney documents")
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
