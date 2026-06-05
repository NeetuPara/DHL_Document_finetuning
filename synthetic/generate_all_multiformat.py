"""Master runner for all 12 multi-format document generators — 1000 docs per class."""
import sys, time, importlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

GENERATORS = [
    ("01_Commercial_Invoice",          "generate_ci_multiformat",       1000),
    ("02_House_Bill_of_Lading",        "generate_hbl_multiformat",      1000),
    ("03_Certificate_of_Origin",       "generate_coo_multiformat",      1000),
    ("04_Shippers_Letter_of_Instruction","generate_sli_multiformat",    1000),
    ("05_Dangerous_Goods_Declaration", "generate_dgd_multiformat",      1000),
    ("06_Verified_Gross_Mass",         "generate_vgm_multiformat",      1000),
    ("07_House_Airway_Bill",           "generate_hawb_multiformat",     1000),
    ("08_Packing_List",                "generate_pl_multiformat",       1000),
    ("09_Customs_Declarations",        "generate_cn23_multiformat",     1000),
    ("10_Cargo_Manifest",              "generate_manifest_multiformat", 1000),
    ("11_Import_Export_License",       "generate_eei_multiformat",      1000),
    ("12_Power_of_Attorney",           "generate_poa_multiformat",      1000),
]

def run_all(skip_ci=False):
    total_start = time.time()
    results = {}
    for class_name, mod_name, count in GENERATORS:
        if skip_ci and "Commercial_Invoice" in class_name:
            print(f"[SKIP] {class_name} (already done)")
            results[class_name] = count
            continue
        print(f"\n{'='*60}")
        print(f"  {class_name}  ({count} docs)")
        print(f"{'='*60}")
        t0 = time.time()
        try:
            mod = importlib.import_module(mod_name)
            mod.generate(count)
            elapsed = time.time() - t0
            results[class_name] = count
            print(f"  Done in {elapsed:.1f}s")
        except Exception as e:
            import traceback; traceback.print_exc()
            results[class_name] = 0
            print(f"  ERROR: {e}")

    total = time.time() - total_start
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    grand = 0
    for class_name, count in results.items():
        tag = "OK  " if count > 0 else "FAIL"
        print(f"  [{tag}] {class_name:<42} {count:>5} docs")
        grand += count
    print(f"{'='*60}")
    print(f"  TOTAL: {grand:,} documents in {total:.1f}s")

    # Verify file counts
    base = Path(__file__).parent.parent / "Synthetic_Data"
    print("\nFile counts per class:")
    total_files = 0
    for d in sorted(base.iterdir()):
        if d.is_dir():
            pdfs = list(d.rglob("*.pdf"))
            jsons = list(d.rglob("*.json"))
            status = "OK  " if len(pdfs) >= 900 else "WARN"
            print(f"  [{status}] {d.name:<45} {len(pdfs):>5} PDFs  {len(jsons):>5} JSONs")
            total_files += len(pdfs)
    print(f"\n  Total PDFs: {total_files:,}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--skip-ci", action="store_true", help="Skip CI (already has 1000 docs)")
    run_all(skip_ci=p.parse_args().skip_ci)
