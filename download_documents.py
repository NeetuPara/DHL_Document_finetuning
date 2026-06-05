"""
DHL Document Corpus Downloader
Downloads representative samples of all 12 DHL document classes into organized subfolders.
"""

import os
import time
import shutil
import requests
from pathlib import Path

BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "Documents"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/octet-stream,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

FOLDERS = [
    "01_Commercial_Invoice",
    "02_House_Bill_of_Lading",
    "03_Certificate_of_Origin",
    "04_Shippers_Letter_of_Instruction",
    "05_Dangerous_Goods_Declaration",
    "06_Verified_Gross_Mass",
    "07_House_Airway_Bill",
    "08_Packing_List",
    "09_Customs_Declarations",
    "10_Cargo_Manifest",
    "11_Import_Export_License",
    "12_Power_of_Attorney",
]

# (folder, filename, url)
DOWNLOADS = [
    # --- Priority 1: Official DHL ---
    ("01_Commercial_Invoice", "dhl-sg-commercial-invoice.pdf",
     "https://www.dhl.com/discover/content/dam/singapore/files/sg_commercial_invoice.pdf"),
    ("01_Commercial_Invoice", "dhl-my-commercial-invoice.pdf",
     "https://www.dhl.com/discover/content/dam/malaysia/logistics-advise/commercial-invoice/Commercial%20Invoice%20Template-DHL%20Express.pdf"),
    ("01_Commercial_Invoice", "mydhl-digital-customs-invoice-guide-pl.pdf",
     "https://mydhl.express.dhl/content/dam/downloads/pl/en/mydhl-guides/Digital_customs_invoice_pl_en.pdf.coredownload.pdf"),
    ("01_Commercial_Invoice", "mydhl-create-shipment-guide.pdf",
     "https://mydhl.express.dhl/content/dam/downloads/us/en/guides-and-tips/create_shipment_step_by_step_guide_am_en.pdf.coredownload.pdf"),
    ("02_House_Bill_of_Lading", "dhl-us-ocean-bl-terms.pdf",
     "https://www.dhl.com/content/dam/dhl/local/us/dhl-global-forwarding/documents/pdf/us-dgf-ocean-bill-of-lading-terms-conditions.pdf"),
    ("02_House_Bill_of_Lading", "dhl-glo-danmar-ocean-bl-terms.pdf",
     "https://www.dhl.com/content/dam/dhl/global/dhl-global-forwarding/documents/pdf/glo-dgf-ocean-danmar-line-terms-and-conditions.pdf"),
    ("02_House_Bill_of_Lading", "dhl-glo-ocean-lcl-charges-nl.pdf",
     "https://www.dhl.com/content/dam/dhl/local/nl/dhl-global-forwarding/documents/pdf/dhl-nl-en-oceanfreight-lcl-export-local-terms-and-conditions-charges-mar21.pdf"),
    ("03_Certificate_of_Origin", "dhl-ca-certificate-of-origin.pdf",
     "https://mydhl.express.dhl/content/dam/downloads/ca/en/customs-papewrok/dhl_ca_certificate_of_origin_en.pdf.coredownload.pdf"),
    ("04_Shippers_Letter_of_Instruction", "dhl-us-sli-v1.pdf",
     "https://www.dhl.com/content/dam/dhl/local/us/dhl-global-forwarding/documents/pdf/us-dgf-shippers-letter-of-instruction.pdf"),
    ("05_Dangerous_Goods_Declaration", "dhl-fi-multimodal-dgd.xls",
     "https://www.dhl.com/content/dam/dhl/local/fi/dhl-freight/documents/docs/fi-freight-multimodal-dangerous-goods-form.xls"),
    ("05_Dangerous_Goods_Declaration", "dhl-cn-non-dg-declaration.doc",
     "https://www.dhl.com/content/dam/dhl/local/cn/dhl-ecommerce/documents/docs/cn-ecommerce-onboarding-declaration-non-dangerous-dry-batteries-en.doc"),
    ("06_Verified_Gross_Mass", "dhl-glo-vgm-submission-template.pdf",
     "https://www.dhl.com/content/dam/dhl/global/dhl-global-forwarding/documents/pdf/dhl-glo-dgf-solas-verified-gross-mass-submission-template.pdf"),
    ("06_Verified_Gross_Mass", "dhl-glo-solas-customer-update.pdf",
     "https://www.dhl.com/content/dam/dhl/global/dhl-global-forwarding/documents/pdf/dhl-glo-dgf-solas-customer-update.pdf"),
    ("07_House_Airway_Bill", "dhl-glo-hawb-terms.pdf",
     "https://www.dhl.com/content/dam/dhl/global/dhl-global-forwarding/documents/pdf/glo-dgf-hawb-terms.pdf"),
    ("07_House_Airway_Bill", "dhl-glo-air-freight-brochure.pdf",
     "https://www.dhl.com/content/dam/dhl/global/dhl-global-forwarding/documents/pdf/dhl-glo-dgf-air-freight-brochure.pdf"),
    ("08_Packing_List", "dhl-tw-packing-list.pdf",
     "https://www.dhl.com/discover/content/dam/taiwan/shipping-with-dhl/start-shipping-with-dhl/-%E5%BF%85%E8%A6%81%E6%96%87%E4%BB%B6%E6%BA%96%E5%82%99-%E8%A3%9D%E7%AE%B1%E5%96%AE.pdf"),
    ("08_Packing_List", "mydhl-packing-guide.pdf",
     "https://mydhl.express.dhl/content/dam/downloads/global/en/packing-with-care/dhl_express_packing_guide_en.pdf.coredownload.pdf"),
    ("09_Customs_Declarations", "dhl-se-customs-info-export.pdf",
     "https://www.dhl.com/content/dam/dhl/local/se/dhl-freight/documents/pdf/se-freight-customs-information-export-en.pdf"),
    ("12_Power_of_Attorney", "dhl-us-poa-export.pdf",
     "https://www.dhl.com/content/dam/dhl/local/us/dhl-global-forwarding/documents/pdf/us-dgf-poa-form.pdf"),

    # --- Priority 2: IATA / IMO / Government / Industry ---
    ("05_Dangerous_Goods_Declaration", "iata-dgd-column-format-fillable.pdf",
     "https://www.iata.org/contentassets/a9f496cd8c87466b98142fa6d4cdb209/shippers-declaration-column-format-fillable.pdf"),
    ("05_Dangerous_Goods_Declaration", "iata-dgd-open-format-fillable.pdf",
     "https://www.iata.org/contentassets/a9f496cd8c87466b98142fa6d4cdb209/shippers-declaration-open-format-fillable.pdf"),
    ("05_Dangerous_Goods_Declaration", "iata-non-radioactive-checklist.pdf",
     "https://www.iata.org/contentassets/b08040a138dc4442a4f066e6fb99fe2a/en_form_nonrad.pdf"),
    ("10_Cargo_Manifest", "imo-fal-form2-cargo-declaration.docx",
     "https://wwwcdn.imo.org/localresources/en/OurWork/Facilitation/Documents/FAL%20FORM%202.docx"),
    ("09_Customs_Declarations", "fedex-cn22-postal-declaration-fillable.pdf",
     "https://www.fedex.com/content/dam/fedex/us-united-states/services/CN_22_Postal_Clearance_Declaration_Fillable_Form.pdf"),
    ("01_Commercial_Invoice", "eforms-dhl-commercial-invoice.pdf",
     "https://eforms.com/download/2016/10/dhl-commercial-invoice-template.pdf"),
    ("02_House_Bill_of_Lading", "guided-imports-hbl-template.pdf",
     "https://guidedimports.com/wp-content/uploads/2025/01/downloadable-bill-of-lading-pdf-template-hbl.pdf"),
    ("02_House_Bill_of_Lading", "tbgfs-bl-blank-sample.pdf",
     "https://www.tbgfs.com/wp-content/uploads/2013/01/Bill-of-Lading-Blank-Sample.pdf"),
    ("02_House_Bill_of_Lading", "fresa-bill-of-lading-sample.pdf",
     "https://fresatechnologies.com/wp-content/uploads/2020/02/Bill-of-Lading.pdf"),
    ("07_House_Airway_Bill", "fresa-air-waybill-sample.pdf",
     "https://fresatechnologies.com/wp-content/uploads/2020/02/Air-waybill.pdf"),
    ("02_House_Bill_of_Lading", "gov-mb-bol-template.pdf",
     "https://www.gov.mb.ca/agriculture/food-and-ag-processing/starting-a-food-business/pubs/bill-of-lading-template.pdf"),
    ("06_Verified_Gross_Mass", "oceanair-vgm-form-lcl.pdf",
     "http://oceanair.net/wp-content/uploads/2017/11/VGM-Form-LCL-Interactive.pdf"),
    ("05_Dangerous_Goods_Declaration", "trackon-non-dg-declaration.pdf",
     "https://www.trackon.in/Downloads/Non-DG-Declaration.pdf"),
    ("04_Shippers_Letter_of_Instruction", "expeditors-sli.pdf",
     "https://www.expeditors.com/media/1413/expeditors-sli.pdf"),
    ("12_Power_of_Attorney", "combined-export-import-poa.pdf",
     "https://preferredship.com/wp-content/uploads/2012/10/power_of_attorney_combined_export_and_import.pdf"),
    ("12_Power_of_Attorney", "dhl-usa-import-poa.pdf",
     "https://www.globexcourier.com/wp-content/uploads/2024/03/DHL-USA-Import-Power-of-Attorney.pdf"),
]

# Existing files to move into correct subfolders
EXISTING_FILES = [
    ("Commercial Invoice Template-DHL Express (2).pdf", "01_Commercial_Invoice"),
    ("gb-dgf-exporting-packing-list.pdf", "08_Packing_List"),
    ("us_shippers_letter_of_instruction.pdf", "04_Shippers_Letter_of_Instruction"),
]


def create_folders():
    for folder in FOLDERS:
        (DOCS_DIR / folder).mkdir(parents=True, exist_ok=True)
    print(f"Created {len(FOLDERS)} document class folders in {DOCS_DIR}\n")


def move_existing_files():
    print("=== Moving existing files to class folders ===")
    for filename, folder in EXISTING_FILES:
        src = DOCS_DIR / filename
        dst = DOCS_DIR / folder / filename
        if src.exists():
            shutil.move(str(src), str(dst))
            print(f"  MOVED: {filename} -> {folder}/")
        elif dst.exists():
            print(f"  SKIP:  {filename} already in {folder}/")
        else:
            print(f"  MISS:  {filename} not found at root")
    print()


def download_file(folder: str, filename: str, url: str, stats: dict):
    dest = DOCS_DIR / folder / filename
    if dest.exists():
        print(f"  SKIP  [{folder}] {filename} (already exists, {dest.stat().st_size:,} bytes)")
        stats["skipped"] += 1
        return

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            # Reject HTML error pages masquerading as success
            if "text/html" in content_type and len(resp.content) < 50_000:
                print(f"  FAIL  [{folder}] {filename} — got HTML page (likely login/redirect), status 200")
                stats["failed"] += 1
                return
            dest.write_bytes(resp.content)
            size_kb = len(resp.content) / 1024
            print(f"  OK    [{folder}] {filename} ({size_kb:.1f} KB)")
            stats["downloaded"] += 1
        else:
            print(f"  FAIL  [{folder}] {filename} — HTTP {resp.status_code}")
            stats["failed"] += 1
    except Exception as e:
        print(f"  ERR   [{folder}] {filename} — {e}")
        stats["failed"] += 1


def main():
    print("=" * 70)
    print("DHL Document Corpus Downloader")
    print("=" * 70)
    print()

    create_folders()
    move_existing_files()

    stats = {"downloaded": 0, "skipped": 0, "failed": 0}
    failed_list = []

    print(f"=== Downloading {len(DOWNLOADS)} documents ===")
    for i, (folder, filename, url) in enumerate(DOWNLOADS, 1):
        print(f"[{i:02d}/{len(DOWNLOADS)}]", end=" ")
        before = stats["failed"]
        download_file(folder, filename, url, stats)
        if stats["failed"] > before:
            failed_list.append((folder, filename, url))
        if i < len(DOWNLOADS):
            time.sleep(1.0)  # polite delay

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Downloaded : {stats['downloaded']}")
    print(f"  Skipped    : {stats['skipped']} (already existed)")
    print(f"  Failed     : {stats['failed']}")
    print()

    if failed_list:
        print("Failed downloads (manual download needed):")
        for folder, filename, url in failed_list:
            print(f"  -> {folder}/{filename}")
            print(f"     {url}")
        print()

    print("File counts per class folder:")
    for folder in sorted(FOLDERS):
        path = DOCS_DIR / folder
        files = list(path.iterdir()) if path.exists() else []
        status = "OK" if files else "EMPTY"
        print(f"  [{status:5s}] {folder}: {len(files)} file(s)")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
