"""
Supplementary downloader for empty/under-filled document class folders.
Also retries dhl.com CDN with longer timeout and different headers.
"""

import os
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "Documents"

# Rotate user-agents and add referer to bypass some CDN blocks
DHL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
        "Gecko/20100101 Firefox/121.0"
    ),
    "Accept": "application/pdf,application/octet-stream,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.dhl.com/",
    "DNT": "1",
    "Connection": "keep-alive",
}

STANDARD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/octet-stream,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# (folder, filename, url, headers_key)
# headers_key: "dhl" or "std"
SUPPLEMENT = [
    # ── 02_House_Bill_of_Lading ── need more samples (only 1 currently)
    ("02_House_Bill_of_Lading", "xpo-bol-form-2024.pdf",
     "https://www.xpo.com/cdn/files/s1/Bill-of-Lading-Form_2024.pdf", "std"),

    # ── 06_Verified_Gross_Mass ── empty, need alternatives
    ("06_Verified_Gross_Mass", "hapag-lloyd-vgm-declaration.pdf",
     "https://www.hapag-lloyd.com/content/dam/website/downloads/en/service/vgm-declaration.pdf", "std"),
    ("06_Verified_Gross_Mass", "shipping-freight-vgm-certificate-sample.pdf",
     "https://www.shippingandfreightresource.com/wp-content/uploads/2016/05/VGM-Certificate-Sample.pdf", "std"),
    ("06_Verified_Gross_Mass", "dhl-glo-vgm-template-retry.pdf",
     "https://www.dhl.com/content/dam/dhl/global/dhl-global-forwarding/documents/pdf/dhl-glo-dgf-solas-verified-gross-mass-submission-template.pdf", "dhl"),

    # ── 09_Customs_Declarations ── empty, need alternatives
    ("09_Customs_Declarations", "royalmail-cn22-customs-form.pdf",
     "https://www.royalmail.com/sites/default/files/CN22_0.pdf", "std"),
    ("09_Customs_Declarations", "cbp-entry-summary-form-7501.pdf",
     "https://www.cbp.gov/sites/default/files/assets/documents/2023-Sep/CBP%20Form%207501%20-%20Entry%20Summary.pdf", "std"),
    ("09_Customs_Declarations", "cbp-entry-immediate-delivery-3461.pdf",
     "https://www.cbp.gov/sites/default/files/assets/documents/2016-Jun/CBP%20Form%203461.pdf", "std"),
    ("09_Customs_Declarations", "dhl-se-customs-export-retry.pdf",
     "https://www.dhl.com/content/dam/dhl/local/se/dhl-freight/documents/pdf/se-freight-customs-information-export-en.pdf", "dhl"),

    # ── 11_Import_Export_License ── empty, need alternatives
    ("11_Import_Export_License", "bis-export-license-form-748P.pdf",
     "https://efts.usitc.gov/OTSS/pdf/hts_import_form.pdf", "std"),
    ("11_Import_Export_License", "usitc-hts-import-entry-form.pdf",
     "https://efts.usitc.gov/OTSS/pdf/hts_import_form.pdf", "std"),
    ("11_Import_Export_License", "cbp-inbond-transportation-7512.pdf",
     "https://www.cbp.gov/sites/default/files/assets/documents/2016-Jun/CBP%20Form%207512.pdf", "std"),

    # ── Retry dhl.com CDN failures with longer timeout ──
    ("01_Commercial_Invoice", "dhl-sg-commercial-invoice-retry.pdf",
     "https://www.dhl.com/discover/content/dam/singapore/files/sg_commercial_invoice.pdf", "dhl"),
    ("04_Shippers_Letter_of_Instruction", "dhl-us-sli-v1-retry.pdf",
     "https://www.dhl.com/content/dam/dhl/local/us/dhl-global-forwarding/documents/pdf/us-dgf-shippers-letter-of-instruction.pdf", "dhl"),
    ("07_House_Airway_Bill", "dhl-glo-hawb-terms-retry.pdf",
     "https://www.dhl.com/content/dam/dhl/global/dhl-global-forwarding/documents/pdf/glo-dgf-hawb-terms.pdf", "dhl"),
    ("12_Power_of_Attorney", "dhl-us-poa-export-retry.pdf",
     "https://www.dhl.com/content/dam/dhl/local/us/dhl-global-forwarding/documents/pdf/us-dgf-poa-form.pdf", "dhl"),
    ("02_House_Bill_of_Lading", "dhl-us-ocean-bl-terms-retry.pdf",
     "https://www.dhl.com/content/dam/dhl/local/us/dhl-global-forwarding/documents/pdf/us-dgf-ocean-bill-of-lading-terms-conditions.pdf", "dhl"),
    ("08_Packing_List", "dhl-tw-packing-list-retry.pdf",
     "https://www.dhl.com/discover/content/dam/taiwan/shipping-with-dhl/start-shipping-with-dhl/-%E5%BF%85%E8%A6%81%E6%96%87%E4%BB%B6%E6%BA%96%E5%82%99-%E8%A3%9D%E7%AE%B1%E5%96%AE.pdf", "dhl"),
]


def download_file(folder, filename, url, headers, timeout=60):
    dest = DOCS_DIR / folder / filename
    if dest.exists():
        print(f"  SKIP  [{folder}] {filename} ({dest.stat().st_size:,} bytes)")
        return "skip"

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            ct = resp.headers.get("Content-Type", "")
            if "text/html" in ct and len(resp.content) < 80_000:
                print(f"  FAIL  [{folder}] {filename} — got HTML (redirect/login)")
                return "fail"
            dest.write_bytes(resp.content)
            print(f"  OK    [{folder}] {filename} ({len(resp.content)/1024:.1f} KB)")
            return "ok"
        else:
            print(f"  FAIL  [{folder}] {filename} — HTTP {resp.status_code}")
            return "fail"
    except Exception as e:
        print(f"  ERR   [{folder}] {filename} — {e}")
        return "fail"


def main():
    print("=" * 70)
    print("Supplementary Downloader — Filling Empty Folders")
    print("=" * 70)
    print()

    counts = {"ok": 0, "skip": 0, "fail": 0}

    for i, (folder, filename, url, hkey) in enumerate(SUPPLEMENT, 1):
        headers = DHL_HEADERS if hkey == "dhl" else STANDARD_HEADERS
        timeout = 60 if hkey == "dhl" else 30
        print(f"[{i:02d}/{len(SUPPLEMENT)}]", end=" ")
        result = download_file(folder, filename, url, headers, timeout)
        counts[result] += 1
        time.sleep(1.5 if hkey == "dhl" else 1.0)

    print()
    print("=" * 70)
    print(f"  Downloaded : {counts['ok']}")
    print(f"  Skipped    : {counts['skip']}")
    print(f"  Failed     : {counts['fail']}")
    print()

    print("File counts per class folder:")
    folders = sorted(DOCS_DIR.iterdir()) if DOCS_DIR.exists() else []
    for path in folders:
        if path.is_dir():
            files = [f for f in path.iterdir() if f.is_file()]
            status = "OK" if files else "EMPTY"
            print(f"  [{status:5s}] {path.name}: {len(files)} file(s)")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
