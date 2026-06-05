"""
Downloads actual shipping document FORMS for all 12 DHL document classes.
Only blank/fillable forms that show field structure — no guides, T&C, or brochures.
Source-agnostic: DHL, FedEx, UPS, IATA, CBP, Royal Mail, freight forwarders, etc.
"""

import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "Documents"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
        "Gecko/20100101 Firefox/121.0"
    ),
    "Accept": "application/pdf,application/octet-stream,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# (folder, save_as, url)
FORMS = [
    # ── 01 Commercial Invoice ─────────────────────────────────────────────
    # Already have: Commercial Invoice Template-DHL Express (2).pdf ✅
    ("01_Commercial_Invoice", "ups-commercial-invoice.pdf",
     "https://www.ups.com/media/en/commercial_invoice.pdf"),
    ("01_Commercial_Invoice", "fedex-commercial-invoice.pdf",
     "https://www.fedex.com/content/dam/fedex/us-united-states/services/FedEx_CommercialInvoice.pdf"),

    # ── 02 House Bill of Lading ───────────────────────────────────────────
    # Already have: gov-mb-bol-template.pdf ✅
    ("02_House_Bill_of_Lading", "fiata-fbl-negotiable-hbl.pdf",
     "https://www.legiscomex.com/sites/legiscomex/files/2025-02/Negotiable%20FIATA%20Multimodal%20Transport%20Bill%20of%20Lading.pdf"),
    ("02_House_Bill_of_Lading", "hapag-lloyd-bill-of-lading.pdf",
     "https://www.hapag-lloyd.com/content/dam/website/downloads/pdf/7345_BillofLading_A4.pdf"),
    ("02_House_Bill_of_Lading", "tbgfs-straight-house-bol.pdf",
     "https://www.tbgfs.com/wp-content/uploads/2013/01/Bill-of-Lading-Blank-Sample.pdf"),
    ("02_House_Bill_of_Lading", "dhx-multimodal-ocean-bol.pdf",
     "https://www.dhx.com/forms/DHX-Multimodal-Bill-of-Lading.pdf"),

    # ── 03 Certificate of Origin ──────────────────────────────────────────
    # Already have: dhl-ca-certificate-of-origin.pdf ✅
    ("03_Certificate_of_Origin", "fedex-certificate-of-origin-blank.pdf",
     "https://www.fedex.com/content/dam/fedex/us-united-states/International/images/2019/Q4/Certificate_Of_Origin_blank_form_1048425923.pdf"),
    ("03_Certificate_of_Origin", "ups-certificate-of-origin.pdf",
     "https://www.ups.com/media/en/cert_of_origin.pdf"),
    ("03_Certificate_of_Origin", "usmca-certificate-of-origin-wtc.pdf",
     "https://www.wtcdenver.org/wp-content/uploads/2020/07/USMCA-Certificate-of-Origin-Template-v.5.pdf"),
    ("03_Certificate_of_Origin", "mohawk-global-coo.pdf",
     "https://mohawkglobal.com/wp-content/uploads/2020/05/Certificate-of-origin.pdf"),

    # ── 04 Shipper's Letter of Instruction ───────────────────────────────
    # Already have: us_shippers_letter_of_instruction.pdf ✅, expeditors-sli.pdf ✅
    ("04_Shippers_Letter_of_Instruction", "dhl-us-sli-form.pdf",
     "https://www.dhl.com/content/dam/dhl/local/us/dhl-global-forwarding/documents/pdf/us-dgf-shippers-letter-of-instruction.pdf"),

    # ── 05 Dangerous Goods Declaration ───────────────────────────────────
    # Already have: iata-dgd-column-format-fillable.pdf ✅
    #               iata-dgd-open-format-fillable.pdf ✅
    #               iata-non-radioactive-checklist.pdf ✅
    #               trackon-non-dg-declaration.pdf ✅

    # ── 06 Verified Gross Mass ────────────────────────────────────────────
    ("06_Verified_Gross_Mass", "dhl-vgm-solas-submission-template.pdf",
     "https://www.dhl.com/content/dam/dhl/global/dhl-global-forwarding/documents/pdf/dhl-glo-dgf-solas-verified-gross-mass-submission-template.pdf"),
    ("06_Verified_Gross_Mass", "scarbrough-vgm-declaration-form.pdf",
     "https://scarbroughglobal.com/wp-content/uploads/2016/06/VGM-Form.pdf"),
    ("06_Verified_Gross_Mass", "worldwide-logistics-vgm-form.pdf",
     "https://worldwidelogisticsltd.com/wp-content/uploads/2020/02/WWL-VGM-FORM2-002.pdf"),
    ("06_Verified_Gross_Mass", "normankrieger-vgm-declaration.pdf",
     "https://www.nkinc.com/wp-content/uploads/2022/08/VGM-Declaration-Form-002.pdf"),

    # ── 07 House Airway Bill ──────────────────────────────────────────────
    # Already have: fresa-air-waybill-sample.pdf ✅
    ("07_House_Airway_Bill", "smartsheet-air-waybill-neutral.pdf",
     "https://www.smartsheet.com/sites/default/files/IC-Air-Waybill-9235-PDF.pdf"),
    ("07_House_Airway_Bill", "iata-awb-resolution600a.pdf",
     "https://quote-it.net/pdf/Air-Waybill-IATA-resolution-600a.pdf"),

    # ── 08 Packing List ───────────────────────────────────────────────────
    # Already have: gb-dgf-exporting-packing-list.pdf ✅ (DHL UK)
    ("08_Packing_List", "ups-packing-list.pdf",
     "https://www.ups.com/media/en/packinglist.pdf"),
    ("08_Packing_List", "fedex-universal-packing-list.pdf",
     "https://www.fedex.com/gtm/pdf/UPL.pdf"),
    ("08_Packing_List", "exfreight-packing-list.pdf",
     "https://www.exfreight.com/wp-content/uploads/2020/04/Packing-List.pdf"),

    # ── 09 Customs Declarations ───────────────────────────────────────────
    ("09_Customs_Declarations", "cn22-royalmail.pdf",
     "https://www.royalmail.com/sites/royalmail.com/files/2023-04/CN22A%20Jan%202021_0_0.pdf"),
    ("09_Customs_Declarations", "cn22-guernseypost-interactive.pdf",
     "https://www.guernseypost.com/sites/default/files/uploads/CN22%20(interactive).pdf"),
    ("09_Customs_Declarations", "cn23-royalmail.pdf",
     "https://www.royalmail.com/sites/default/files/CN23.pdf"),
    ("09_Customs_Declarations", "cn23-guernseypost-interactive.pdf",
     "https://www.guernseypost.com/sites/default/files/uploads/CN23%20(Interactive).pdf"),
    ("09_Customs_Declarations", "cn23-oxford-blank.pdf",
     "https://estates.web.ox.ac.uk/sites/default/files/estates/documents/media/cn23-form-blank.pdf"),

    # ── 10 Cargo Manifest ─────────────────────────────────────────────────
    # Already have: imo-fal-form2-cargo-declaration.docx ✅
    ("10_Cargo_Manifest", "cbp-7509-air-cargo-manifest.pdf",
     "https://www.cbp.gov/sites/default/files/assets/documents/2016-Mar/CBP%20Form%207509.pdf"),
    ("10_Cargo_Manifest", "cbsa-a6a-marine-cargo-manifest.pdf",
     "https://www.cbsa-asfc.gc.ca/publications/forms-formulaires/a6a.pdf"),
    ("10_Cargo_Manifest", "cbp-7533-inward-vessel-manifest.pdf",
     "https://www.cbp.gov/sites/default/files/assets/documents/2022-Dec/CBP%20Form%207533.pdf"),

    # ── 11 Import/Export License / EEI ───────────────────────────────────
    ("11_Import_Export_License", "cbp-7501-entry-summary-import.pdf",
     "https://www.cbp.gov/sites/default/files/2026-02/cbp_form_7501.pdf"),
    ("11_Import_Export_License", "cbp-3461-entry-immediate-delivery.pdf",
     "https://www.cbp.gov/sites/default/files/assets/documents/2016-Jun/CBP%20Form%203461.pdf"),
    ("11_Import_Export_License", "cbp-7512-transportation-in-bond.pdf",
     "https://www.cbp.gov/sites/default/files/assets/documents/2016-Jun/CBP%20Form%207512.pdf"),

    # ── 12 Power of Attorney ──────────────────────────────────────────────
    # Already have: combined-export-import-poa.pdf ✅, dhl-usa-import-poa.pdf ✅
    ("12_Power_of_Attorney", "dhl-us-poa-export.pdf",
     "https://www.dhl.com/content/dam/dhl/local/us/dhl-global-forwarding/documents/pdf/us-dgf-poa-form.pdf"),
]


def download_file(folder, filename, url, stats):
    dest = DOCS_DIR / folder / filename
    if dest.exists():
        print(f"  SKIP  {filename}")
        stats["skip"] += 1
        return

    try:
        resp = requests.get(url, headers=HEADERS, timeout=45, allow_redirects=True)
        if resp.status_code == 200:
            ct = resp.headers.get("Content-Type", "")
            if "text/html" in ct and len(resp.content) < 80_000:
                print(f"  FAIL  {filename} — HTML redirect/login page")
                stats["fail"] += 1
                return
            dest.write_bytes(resp.content)
            print(f"  OK    {filename}  ({len(resp.content)/1024:.0f} KB)")
            stats["ok"] += 1
        else:
            print(f"  FAIL  {filename} — HTTP {resp.status_code}")
            stats["fail"] += 1
    except Exception as e:
        print(f"  ERR   {filename} — {e}")
        stats["fail"] += 1


def main():
    print("=" * 65)
    print("Downloading actual document FORMS (blank templates)")
    print("=" * 65)

    stats = {"ok": 0, "skip": 0, "fail": 0}
    current_folder = None

    for i, (folder, filename, url) in enumerate(FORMS, 1):
        if folder != current_folder:
            current_folder = folder
            print(f"\n--- {folder} ---")
        print(f"  [{i:02d}/{len(FORMS)}]", end=" ")
        download_file(folder, filename, url, stats)
        time.sleep(1.0)

    print("\n" + "=" * 65)
    print(f"Downloaded: {stats['ok']}  |  Skipped: {stats['skip']}  |  Failed: {stats['fail']}")
    print()
    print("Files per class:")
    for path in sorted(DOCS_DIR.iterdir()):
        if path.is_dir():
            files = [f for f in path.iterdir() if f.is_file()]
            tag = "OK  " if files else "EMPTY"
            print(f"  {tag}  {path.name}: {len(files)} file(s)")
            for f in sorted(files):
                print(f"       {f.name}")


if __name__ == "__main__":
    main()
