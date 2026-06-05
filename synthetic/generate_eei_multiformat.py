"""
EEI / Import-Export License — 3 distinct real-world format variants.
Format 1: CBP Entry Summary (Form 7501 style) — US Customs entry
Format 2: US SED/EEI Export Filing Reference — AES export filing
Format 3: Import License / Export License Document — formal government license
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

OUT_DIR = Path(__file__).parent.parent / "Synthetic_Data" / "11_Import_Export_License"
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
    sc = random_country(); rc = random_country()
    while rc[1] == sc[1]: rc = random_country()

    entry_types = ["01 - Free and Dutiable", "03 - Consumption - Quota", "06 - FTZ Consumption",
                   "11 - Informal - Free", "12 - Informal - Dutiable"]
    transport_modes = ["Air", "Ocean", "Truck", "Rail", "Hand-Carried"]
    ports_of_entry = ["JFK - New York", "LAX - Los Angeles", "ORD - Chicago", "MIA - Miami",
                      "SEA - Seattle", "BOS - Boston", "HOU - Houston", "SFO - San Francisco"]
    eccn_codes = ["EAR99", "5E992", "3A992", "7A994", "9A515", "2B350", "1A002", "0A919"]
    export_reasons = ["NLR - No License Required", "GBS - License Exception",
                      "TSR - Technology and Software", "BIS - Bureau of Industry", "TMP - Temporary"]
    license_authorities = ["BIS - Bureau of Industry and Security",
                           "DDTC - Directorate of Defense Trade Controls",
                           "OFAC - Office of Foreign Assets Control",
                           "CBP - US Customs and Border Protection",
                           "FDA - Food and Drug Administration"]

    n_items = random.randint(2, 8)
    items = []
    for _ in range(n_items):
        cat = random.choice(COMMODITY_CATEGORIES)
        qty = random.randint(1, 500)
        unit_val = round(random.uniform(5.0, 500.0), 2)
        duty_rate = round(random.uniform(0.0, 25.0), 1)
        total_val = round(qty * unit_val, 2)
        duty_amt = round(total_val * duty_rate / 100, 2)
        items.append({
            "hts_no": cat["hs_code"],
            "description": cat["description"],
            "country_of_origin": random_country()[0],
            "qty": qty,
            "unit": cat["unit"],
            "entered_value": total_val,
            "duty_rate": duty_rate,
            "duty_amount": duty_amt,
            "eccn": random.choice(eccn_codes),
            "schedule_b": cat["hs_code"],
            "export_reason": random.choice(export_reasons),
        })

    total_value = round(sum(i["entered_value"] for i in items), 2)
    total_duty = round(sum(i["duty_amount"] for i in items), 2)
    currency = random.choice(CURRENCIES)

    # License specific
    license_no = f"LIC-{fake.bothify('??####-####').upper()}"
    license_authority = random.choice(license_authorities)
    qty_authorized = random.randint(100, 10000)
    validity_start = fake.date_between(start_date="-1y", end_date="today")
    validity_end = fake.date_between(start_date=validity_start, end_date="+2y")

    # AES/ITN
    itn_number = f"X{fake.date_this_decade().strftime('%Y%m%d')}{fake.bothify('######')}"
    aes_options = ["AES Filing", "AES Post Departure", "EEI Exemption", "EEI Exception"]

    return dict(
        entry_number=fake.bothify("###-########-#"),
        entry_type=random.choice(entry_types),
        entry_date=fake.date_between(start_date="-1y", end_date="today"),
        port_of_entry=random.choice(ports_of_entry),
        transport_mode=random.choice(transport_modes),
        carrier=random.choice(["DHL Express", "FedEx", "UPS", "Maersk", "MSC", "Lufthansa Cargo"]),
        bl_awb=random_hawb_number(),
        importer_name=random_company(),
        importer_ein=fake.bothify("##-#######"),
        consignee_name=random_company(),
        customs_broker=random_company(),
        broker_filer_code=fake.bothify("???"),
        country_of_origin=sc[0],
        destination_country=rc[0],
        items=items,
        total_value=total_value,
        total_duty=total_duty,
        currency=currency,
        signatory=fake.name(),
        signatory_title=random.choice(["Import Coordinator", "Compliance Officer",
                                        "Trade Finance Manager", "Logistics Director"]),
        # Export specific
        usppi_name=random_company(),
        usppi_ein=fake.bothify("##-#######"),
        usppi_address=fake.address().replace("\n", ", ") + f", {sc[0]}",
        ultimate_consignee=random_company(),
        intermediate_consignee=random_company(),
        forwarding_agent=random_company(),
        itn_number=itn_number,
        aes_option=random.choice(aes_options),
        export_date=fake.date_between(start_date="-1y", end_date="today"),
        # License specific
        license_no=license_no,
        license_authority=license_authority,
        licensee_name=random_company(),
        licensee_address=fake.address().replace("\n", ", ") + f", {sc[0]}",
        authorized_commodity=random.choice(COMMODITY_CATEGORIES)["description"],
        qty_authorized=qty_authorized,
        qty_unit=random.choice(["units", "kilograms", "liters", "sets", "pieces"]),
        validity_start=validity_start,
        validity_end=validity_end,
        issuing_officer=fake.name(),
        issuing_officer_title=random.choice(["Export Control Officer", "Senior Trade Specialist",
                                              "Deputy Director", "Licensing Officer"]),
        conditions=random.choice([
            "This license is subject to all applicable Export Administration Regulations.",
            "Items may not be re-exported without prior written authorization.",
            "Licensee must maintain records for a period of 5 years.",
            "Subject to end-use verification requirements.",
        ]),
        eccn=random.choice(eccn_codes),
    )


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 1 — CBP Entry Summary (Form 7501 style)
# ═══════════════════════════════════════════════════════════════════════════
def fmt1(doc_id, d, path):
    CBP = colors.HexColor("#003366")
    LCBP = colors.HexColor("#E6EEF7")
    MCBP = colors.HexColor("#C5D8F0")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=colors.white),
        "agency": S("ag", fontName="Helvetica-Bold", fontSize=10, textColor=CBP),
        "form":   S("fm", fontSize=8, textColor=CBP),
        "lbl":    S("l", fontSize=6.5, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=7.5),
        "sm":     S("sm", fontSize=7, leading=8.5),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=6.5, leading=8),
        "cdr":    S("cdr", fontSize=6.5, leading=8, alignment=TA_RIGHT),
        "cdc":    S("cdc", fontSize=6.5, leading=8, alignment=TA_CENTER),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=8),
        "grand":  S("gr", fontName="Helvetica-Bold", fontSize=9, alignment=TA_RIGHT, textColor=CBP),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    # Header
    story.append(Table([[
        [Ps("U.S. CUSTOMS AND BORDER PROTECTION", "agency"),
         Ps("DEPARTMENT OF HOMELAND SECURITY", "sm")],
        Ps("ENTRY SUMMARY", "title"),
        [Ps("CBP FORM 7501", "form"),
         Ps(f"Entry No: {d['entry_number']}", "bold"),
         Ps(f"Date: {d['entry_date'].strftime('%d %b %Y')}", "sm")],
    ]], colWidths=[68*mm, 80*mm, 38*mm]))
    story[-1].setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), CBP),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Spacer(1, 1*mm))

    # Entry details row
    entry_t = Table([[
        Ps("ENTRY TYPE", "lbl"), Ps(d["entry_type"], "val"),
        Ps("PORT OF ENTRY", "lbl"), Ps(d["port_of_entry"], "val"),
        Ps("MODE", "lbl"), Ps(d["transport_mode"], "val"),
        Ps("CARRIER / AWB-BL", "lbl"), Ps(f"{d['carrier']} / {d['bl_awb']}", "val"),
    ]], colWidths=[22*mm, 36*mm, 22*mm, 30*mm, 14*mm, 18*mm, 30*mm, 14*mm])
    entry_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, 0), LCBP), ("BACKGROUND", (2, 0), (2, 0), LCBP),
        ("BACKGROUND", (4, 0), (4, 0), LCBP), ("BACKGROUND", (6, 0), (6, 0), LCBP),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(entry_t)
    story.append(Spacer(1, 1*mm))

    # Importer / Consignee / Broker block
    party_t = Table([[
        [Ps("IMPORTER OF RECORD", "lbl"), Ps(d["importer_name"], "val"),
         Ps(f"EIN: {d['importer_ein']}", "sm")],
        [Ps("CONSIGNEE", "lbl"), Ps(d["consignee_name"], "val")],
        [Ps("CUSTOMS BROKER / FILER", "lbl"),
         Ps(d["customs_broker"], "val"),
         Ps(f"Filer Code: {d['broker_filer_code']}", "sm")],
    ]], colWidths=[62*mm, 62*mm, 62*mm])
    party_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(party_t)
    story.append(Spacer(1, 1*mm))

    # Line items table
    CW = [26*mm, 44*mm, 18*mm, 14*mm, 10*mm, 24*mm, 18*mm, 22*mm]
    rows = [[Ps("HTS NUMBER", "ch"), Ps("Description of Goods", "ch"),
             Ps("Country of\nOrigin", "ch"), Ps("Qty", "ch"), Ps("UOM", "ch"),
             Ps(f"Entered Value\n({d['currency']})", "ch"),
             Ps("Duty Rate", "ch"), Ps(f"Duty Amount\n({d['currency']})", "ch")]]
    n_data = len(d["items"])
    for it in d["items"]:
        rows.append([
            Ps(it["hts_no"], "cdc"),
            Ps(it["description"][:42], "cd"),
            Ps(it["country_of_origin"][:12], "cdc"),
            Ps(str(it["qty"]), "cdr"),
            Ps(it["unit"], "cdc"),
            Ps(f"{it['entered_value']:,.2f}", "cdr"),
            Ps(f"{it['duty_rate']:.1f}%", "cdc"),
            Ps(f"{it['duty_amount']:,.2f}", "cdr"),
        ])
    # Totals
    rows.append([
        Ps("", "cdc"), Ps("TOTAL", "bold"), Ps("", "cdc"), Ps("", "cdr"),
        Ps("", "cdc"),
        Ps(f"{d['total_value']:,.2f}", "cdr"),
        Ps("", "cdc"),
        Ps(f"{d['total_duty']:,.2f}", "cdr"),
    ])

    stripe = [("BACKGROUND", (0, r), (-1, r), LCBP) for r in range(1, n_data + 1) if r % 2 == 0]
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CBP), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), MCBP), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(it_t)
    story.append(Spacer(1, 1*mm))

    # Financial summary
    fin_t = Table([[
        Ps("TOTAL ENTERED VALUE", "lbl"),
        Ps(f"{d['currency']} {d['total_value']:,.2f}", "bold"),
        Ps("TOTAL ESTIMATED DUTY", "lbl"),
        Ps(f"{d['currency']} {d['total_duty']:,.2f}", "bold"),
        Ps("COUNTRY OF ORIGIN", "lbl"),
        Ps(d["country_of_origin"], "val"),
    ]], colWidths=[36*mm, 30*mm, 36*mm, 30*mm, 30*mm, 24*mm])
    fin_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (0, 0), LCBP), ("BACKGROUND", (2, 0), (2, 0), LCBP),
        ("BACKGROUND", (4, 0), (4, 0), LCBP),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(fin_t)
    story.append(Spacer(1, 2*mm))

    # Certification
    cert_t = Table([[
        [Ps("IMPORTER CERTIFICATION", "lbl"),
         Ps("I declare that the statements in the documents herein are true and correct, and "
            "that all goods were imported in accordance with applicable laws and regulations.", "sm"),
         Spacer(1, 4*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"{d['signatory']}  —  {d['signatory_title']}", "sm"),
         Ps(f"Date: {d['entry_date'].strftime('%d %b %Y')}", "sm")],
        [Ps("CBP OFFICIAL USE ONLY", "lbl"),
         Ps("Liquidation Date: ______________", "sm"),
         Ps("Officer Badge: ______________", "sm"),
         Spacer(1, 3*mm),
         Ps(f"Port: {d['port_of_entry']}", "sm"),
         Ps(f"Entry No: {d['entry_number']}", "bold")],
    ]], colWidths=[120*mm, 66*mm])
    cert_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(cert_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 2 — US SED/EEI Export Filing Reference (AES)
# ═══════════════════════════════════════════════════════════════════════════
def fmt2(doc_id, d, path):
    BIS_BLUE = colors.HexColor("#1A237E")
    LBIS = colors.HexColor("#E8EAF6")
    MBIS = colors.HexColor("#C5CAE9")
    st = {
        "title":  S("t", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=colors.white),
        "agency": S("ag", fontName="Helvetica-Bold", fontSize=9, textColor=BIS_BLUE),
        "lbl":    S("l", fontSize=6.5, textColor=colors.HexColor("#555555")),
        "val":    S("v", fontName="Helvetica-Bold", fontSize=7.5),
        "sm":     S("sm", fontSize=7, leading=8.5),
        "ch":     S("ch", fontName="Helvetica-Bold", fontSize=6.5, alignment=TA_CENTER, textColor=colors.white),
        "cd":     S("cd", fontSize=6.5, leading=8),
        "cdr":    S("cdr", fontSize=6.5, leading=8, alignment=TA_RIGHT),
        "cdc":    S("cdc", fontSize=6.5, leading=8, alignment=TA_CENTER),
        "bold":   S("b", fontName="Helvetica-Bold", fontSize=8),
        "itn":    S("itn", fontName="Helvetica-Bold", fontSize=11, textColor=BIS_BLUE),
        "warn":   S("w", fontSize=7, textColor=colors.HexColor("#B71C1C")),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    story.append(Table([[
        [Ps("ELECTRONIC EXPORT INFORMATION (EEI)", "agency"),
         Ps("AUTOMATED EXPORT SYSTEM (AES) FILING REFERENCE", "sm")],
        Ps("SHIPPER'S EXPORT DECLARATION / EEI", "title"),
        [Ps(f"ITN: {d['itn_number']}", "itn"),
         Ps(f"Export Date: {d['export_date'].strftime('%d %b %Y')}", "sm"),
         Ps(f"AES Option: {d['aes_option']}", "sm")],
    ]], colWidths=[75*mm, 75*mm, 36*mm]))
    story[-1].setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), BIS_BLUE),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Spacer(1, 1*mm))

    # USPPI / Consignees / Agent
    party_t = Table([[
        [Ps("U.S. PRINCIPAL PARTY IN INTEREST (USPPI)", "lbl"),
         Ps(d["usppi_name"], "val"),
         Ps(d["usppi_address"], "sm"),
         Ps(f"EIN: {d['usppi_ein']}", "sm")],
        [Ps("ULTIMATE CONSIGNEE", "lbl"),
         Ps(d["ultimate_consignee"], "val"),
         Ps(f"Country: {d['destination_country']}", "sm"),
         Spacer(1, 2*mm),
         Ps("INTERMEDIATE CONSIGNEE", "lbl"),
         Ps(d["intermediate_consignee"], "sm")],
        [Ps("FORWARDING AGENT", "lbl"),
         Ps(d["forwarding_agent"], "val"),
         Spacer(1, 2*mm),
         Ps("CARRIER / AWB", "lbl"),
         Ps(f"{d['carrier']} / {d['bl_awb']}", "sm"),
         Spacer(1, 2*mm),
         Ps("DESTINATION COUNTRY", "lbl"),
         Ps(d["destination_country"], "val")],
    ]], colWidths=[65*mm, 65*mm, 56*mm])
    party_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(party_t)
    story.append(Spacer(1, 1*mm))

    # Schedule B / EEI items table
    CW = [22*mm, 40*mm, 18*mm, 14*mm, 10*mm, 22*mm, 28*mm, 32*mm]
    rows = [[Ps("SCHEDULE B\nNUMBER", "ch"), Ps("Description of Goods", "ch"),
             Ps("Country of\nOrigin", "ch"), Ps("Qty", "ch"), Ps("UOM", "ch"),
             Ps(f"Value ({d['currency']})", "ch"),
             Ps("Export Control", "ch"), Ps("ECCN / Export Reason", "ch")]]
    n_data = len(d["items"])
    for it in d["items"]:
        rows.append([
            Ps(it["schedule_b"], "cdc"),
            Ps(it["description"][:38], "cd"),
            Ps(it["country_of_origin"][:12], "cdc"),
            Ps(str(it["qty"]), "cdr"),
            Ps(it["unit"], "cdc"),
            Ps(f"{it['entered_value']:,.2f}", "cdr"),
            Ps(it["export_reason"][:20], "cd"),
            Ps(f"ECCN: {it['eccn']}", "cdc"),
        ])
    rows.append([
        Ps("", "cdc"), Ps("TOTAL", "bold"), Ps("", "cdc"), Ps("", "cdr"),
        Ps("", "cdc"), Ps(f"{d['total_value']:,.2f}", "cdr"),
        Ps("", "cd"), Ps("", "cdc"),
    ])

    stripe = [("BACKGROUND", (0, r), (-1, r), LBIS) for r in range(1, n_data + 1) if r % 2 == 0]
    it_t = Table(rows, colWidths=CW, repeatRows=1)
    it_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BIS_BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), MBIS), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, BORDER), ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + stripe))
    story.append(it_t)
    story.append(Spacer(1, 1*mm))

    # AES confirmation box
    aes_t = Table([[
        [Ps("AES FILING CONFIRMATION", "lbl"),
         Ps(f"Internal Transaction Number (ITN): {d['itn_number']}", "bold"),
         Ps(f"AES Option: {d['aes_option']}", "sm"),
         Ps(f"Export Date: {d['export_date'].strftime('%d %b %Y')}", "sm"),
         Ps(f"Total Export Value: {d['currency']} {d['total_value']:,.2f}", "bold")],
        [Ps("EXPORT CONTROL NOTICE", "lbl"),
         Ps("These items are controlled by the U.S. Government and authorized for export only "
            "to the country of final destination for use by the ultimate consignee. "
            "Diversion contrary to U.S. law is prohibited.", "warn")],
    ]], colWidths=[W])
    aes_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, -1), LBIS),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(aes_t)
    story.append(Spacer(1, 2*mm))

    # Signature
    sig_t = Table([[
        [Ps("AUTHORIZED AGENT CERTIFICATION", "lbl"),
         Ps("I hereby certify that the statements herein are true and complete to the best "
            "of my knowledge and belief, and that the information in this EEI is in "
            "accordance with applicable export regulations.", "sm"),
         Spacer(1, 4*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"{d['signatory']}  |  {d['forwarding_agent']}", "sm"),
         Ps(f"Date: {d['export_date'].strftime('%d %b %Y')}", "sm")],
        [Ps("USPPI SIGNATURE", "lbl"),
         Spacer(1, 4*mm),
         Ps("Signature: _______________________________", "sm"),
         Ps(f"{d['usppi_name']}", "sm"),
         Ps(f"EIN: {d['usppi_ein']}", "sm")],
    ]], colWidths=[120*mm, 66*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# FORMAT 3 — Import/Export License Document (formal government style)
# ═══════════════════════════════════════════════════════════════════════════
def fmt3(doc_id, d, path):
    DARK_GREEN = colors.HexColor("#1B5E20")
    LGREEN = colors.HexColor("#F1F8E9")
    MGREEN = colors.HexColor("#C8E6C9")
    GOLD = colors.HexColor("#F9A825")
    st = {
        "title":   S("t", fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER, textColor=colors.white),
        "agency":  S("ag", fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER, textColor=DARK_GREEN),
        "lic_no":  S("ln", fontName="Helvetica-Bold", fontSize=14, alignment=TA_CENTER, textColor=DARK_GREEN),
        "lbl":     S("l", fontSize=7, textColor=colors.HexColor("#555555")),
        "val":     S("v", fontName="Helvetica-Bold", fontSize=8),
        "sm":      S("sm", fontSize=7.5, leading=10),
        "bold":    S("b", fontName="Helvetica-Bold", fontSize=8),
        "body":    S("bd", fontSize=8, leading=11),
        "seal":    S("sl", fontSize=7, alignment=TA_CENTER, textColor=colors.HexColor("#888888")),
        "foot":    S("ft", fontSize=6.5, textColor=colors.HexColor("#777777"), alignment=TA_CENTER),
        "auth":    S("au", fontName="Helvetica-Bold", fontSize=9, textColor=DARK_GREEN, alignment=TA_CENTER),
    }
    def Ps(t, s): return P(t, st[s])

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    W3 = 180 * mm
    story = []

    # Government header
    story.append(Table([[
        Ps("UNITED STATES DEPARTMENT OF COMMERCE", "title"),
    ]], colWidths=[W3], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK_GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
    ])))
    story.append(Spacer(1, 1*mm))
    story.append(Table([[
        Ps(d["license_authority"], "agency"),
    ]], colWidths=[W3], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
    ])))
    story.append(Spacer(1, 2*mm))

    # License number — prominent
    story.append(Table([[
        [Ps("LICENSE NUMBER", "lbl"), Ps(d["license_no"], "lic_no")],
        [Ps("Validity Period", "lbl"),
         Ps(f"{d['validity_start'].strftime('%d %B %Y')}  —  {d['validity_end'].strftime('%d %B %Y')}", "bold")],
    ]], colWidths=[W3], style=TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])))
    story.append(Spacer(1, 2*mm))

    # Licensee details
    lic_t = Table([[
        [Ps("LICENSEE", "lbl"), Ps(d["licensee_name"], "val"),
         Ps(d["licensee_address"], "sm")],
        [Ps("ISSUING AUTHORITY", "lbl"), Ps(d["license_authority"], "val")],
        [Ps("ISSUING OFFICER", "lbl"), Ps(d["issuing_officer"], "val"),
         Ps(d["issuing_officer_title"], "sm")],
    ]], colWidths=[W3])
    lic_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, -1), LGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(lic_t)
    story.append(Spacer(1, 2*mm))

    # Authorized commodity + codes
    comm_t = Table([[
        Ps("AUTHORIZED COMMODITY DESCRIPTION", "lbl"),
        Ps("HS / HTS CODE", "lbl"),
        Ps("ECCN", "lbl"),
        Ps("QTY AUTHORIZED", "lbl"),
    ], [
        Ps(d["authorized_commodity"], "sm"),
        Ps(d["items"][0]["hts_no"] if d["items"] else "N/A", "val"),
        Ps(d["eccn"], "val"),
        Ps(f"{d['qty_authorized']:,} {d['qty_unit']}", "bold"),
    ]], colWidths=[80*mm, 30*mm, 30*mm, 40*mm])
    comm_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (0, 0), (-1, 0), MGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(comm_t)
    story.append(Spacer(1, 2*mm))

    # Conditions / restrictions
    cond_t = Table([[
        [Ps("CONDITIONS AND RESTRICTIONS", "lbl"),
         Ps(d["conditions"], "body"),
         Spacer(1, 2*mm),
         Ps("This license is subject to all provisions of the Export Administration Act "
            "and the Export Administration Regulations. Any unauthorized use of this "
            "license may result in civil and criminal penalties.", "body")],
    ]], colWidths=[W3])
    cond_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(cond_t)
    story.append(Spacer(1, 3*mm))

    # Signature blocks (Issuing officer + Licensee)
    HRFlowable(width=W3, thickness=1, color=DARK_GREEN)
    sig_t = Table([[
        [Ps("ISSUING OFFICER", "auth"),
         Spacer(1, 8*mm),
         Ps("____________________________", "seal"),
         Ps(d["issuing_officer"], "sm"),
         Ps(d["issuing_officer_title"], "sm"),
         Ps(d["license_authority"][:30], "sm"),
         Ps(f"Date: {d['validity_start'].strftime('%d %B %Y')}", "sm")],
        [Ps("CORPORATE SEAL", "auth"),
         Spacer(1, 12*mm),
         Ps("[SEAL]", "seal"),
         Ps("Official Seal Area", "seal")],
        [Ps("LICENSEE ACCEPTANCE", "auth"),
         Spacer(1, 8*mm),
         Ps("____________________________", "seal"),
         Ps(d["licensee_name"][:30], "sm"),
         Ps(f"Authorized Representative", "sm"),
         Ps(f"Date: ______________", "sm")],
    ]], colWidths=[70*mm, 40*mm, 70*mm])
    sig_t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), .3, LN),
        ("BACKGROUND", (1, 0), (1, 0), MGREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sig_t)
    story.append(Spacer(1, 2*mm))
    story.append(P(f"License No: {d['license_no']}  |  This license is not transferable.  "
                   f"|  Retain this document for a period of 5 years.",
                   st["foot"]))
    doc.build(story)


# ═══════════════════════════════════════════════════════════════════════════
# Main generator
# ═══════════════════════════════════════════════════════════════════════════
FORMAT_FNS = [fmt1, fmt2, fmt3]
FORMAT_NAMES = ["CBP-Entry-Summary-7501", "US-SED-EEI-Export-Filing", "Import-Export-License-Document"]

def generate_one(doc_id: int) -> dict:
    d = make_data()
    fmt_idx = (doc_id - 1) % 3
    fmt_fn  = FORMAT_FNS[fmt_idx]
    fname   = f"eei_{doc_id:04d}.pdf"
    fmt_fn(doc_id, d, PDF_DIR / fname)

    # Build format-conditional fields — three completely different document types.
    # fmt1 (CBP-Entry-Summary-7501): US Customs import entry form
    if fmt_idx == 0:
        fields = {
            "entry_number": d["entry_number"],
            "entry_type": d["entry_type"],
            "entry_date": d["entry_date"].strftime("%Y-%m-%d"),
            "port_of_entry": d["port_of_entry"],
            "transport_mode": d["transport_mode"],
            "carrier": d["carrier"],
            "bl_awb": d["bl_awb"],
            "importer_name": d["importer_name"],
            "importer_ein": d["importer_ein"],
            "consignee_name": d["consignee_name"],
            "customs_broker": d["customs_broker"],
            "broker_filer_code": d["broker_filer_code"],
            "country_of_origin": d["country_of_origin"],
            "total_value": d["total_value"],
            "total_duty": d["total_duty"],
            "currency": d["currency"],
            "signatory": d["signatory"],
            "signatory_title": d["signatory_title"],
            "line_items": d["items"],
        }
    # fmt2 (US-SED-EEI-Export-Filing): AES export filing / EEI document
    elif fmt_idx == 1:
        fields = {
            "itn_number": d["itn_number"],
            "export_date": d["export_date"].strftime("%Y-%m-%d"),
            "aes_option": d["aes_option"],
            "usppi_name": d["usppi_name"],
            "usppi_ein": d["usppi_ein"],
            "usppi_address": d["usppi_address"],
            "ultimate_consignee": d["ultimate_consignee"],
            "intermediate_consignee": d["intermediate_consignee"],
            "forwarding_agent": d["forwarding_agent"],
            "destination_country": d["destination_country"],
            "carrier": d["carrier"],
            "bl_awb": d["bl_awb"],
            "total_value": d["total_value"],
            "currency": d["currency"],
            "signatory": d["signatory"],
            "line_items": d["items"],
        }
    # fmt3 (Import-Export-License-Document): formal government license
    else:
        fields = {
            "license_number": d["license_no"],
            "license_authority": d["license_authority"],
            "licensee_name": d["licensee_name"],
            "licensee_address": d["licensee_address"],
            "issuing_officer": d["issuing_officer"],
            "issuing_officer_title": d["issuing_officer_title"],
            "authorized_commodity": d["authorized_commodity"],
            "eccn": d["eccn"],
            "qty_authorized": d["qty_authorized"],
            "qty_unit": d["qty_unit"],
            "validity_start": d["validity_start"].strftime("%Y-%m-%d"),
            "validity_end": d["validity_end"].strftime("%Y-%m-%d"),
            "conditions": d["conditions"],
        }

    ann = {
        "document_id":    fname.replace(".pdf", ""),
        "document_class": "Import Export License",
        "format_variant": FORMAT_NAMES[fmt_idx],
        "class_index":    11,
        "fields": fields,
    }
    (ANN_DIR / fname.replace(".pdf", ".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=1000):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_DIR.glob("*.pdf")) + list(ANN_DIR.glob("*.json")): f.unlink()

    fmt_counts = {n: 0 for n in FORMAT_NAMES}
    print(f"Generating {count} Import/Export License documents (3 format variants)...")
    for i in range(1, count + 1):
        a = generate_one(i)
        fmt_counts[a["format_variant"]] += 1
        if i % 100 == 0 or i <= 5:
            f = a["fields"]
            # Fields vary by format; use .get() with fallbacks for safe printing
            ref_key = f.get("entry_number") or f.get("itn_number") or f.get("license_number", "N/A")
            val = f.get("total_value", 0)
            cur = f.get("currency", "USD")
            print(f"  [{i:04d}] {a['format_variant'][:28]:<28}  Ref: {ref_key}  "
                  f"{cur} {val:>10,.2f}")

    print(f"\nFormat distribution:")
    for n, c in fmt_counts.items(): print(f"  {n}: {c}")
    print(f"Done -> {PDF_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate synthetic EEI/Import-Export License documents")
    p.add_argument("--count", type=int, default=1000)
    generate(p.parse_args().count)
