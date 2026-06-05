"""
Master runner — generates synthetic documents for all 12 DHL document classes.
Run: python synthetic/generate_all.py [--count N] [--class CLASS_NAME] [--test]

Per-class targets:
  01 Commercial Invoice          : 900
  02 House Bill of Lading        : 900
  03 Certificate of Origin       : 500 (General) + 500 (FTA) = 1000
  04 SLI                         : 900
  05 Dangerous Goods Declaration : 900
  06 Verified Gross Mass         : 900
  07 House Airway Bill           : 900
  08 Packing List                : 900
  09 Customs Declaration CN23    : 900
  10 Cargo Manifest              : 900
  11 Import Entry Summary        : 900
  12 Power of Attorney           : 900
"""
import sys, argparse, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

CLASSES = {
    "commercial_invoice":         ("generate_commercial_invoice",  "generate", 900),
    "house_bol":                  ("generate_house_bol",           "generate", 900),
    "coo_general":                ("generate_coo_general",         "generate", 500),
    "coo_fta":                    ("generate_coo_fta",             "generate", 500),
    "sli":                        ("generate_sli",                 "generate", 900),
    "dgd":                        ("generate_dgd",                 "generate", 900),
    "vgm":                        ("generate_vgm",                 "generate", 900),
    "hawb":                       ("generate_hawb",                "generate", 900),
    "packing_list":               ("generate_packing_list",        "generate", 900),
    "cn23":                       ("generate_cn23",                "generate", 900),
    "cargo_manifest":             ("generate_cargo_manifest",      "generate", 900),
    "eei":                        ("generate_eei",                 "generate", 900),
    "poa":                        ("generate_poa_multiformat",      "generate", 900),
}

def run_all(count_override=None, only_class=None, test_mode=False):
    test_count = 5
    results = {}
    total_start = time.time()

    for key, (module_name, func_name, default_count) in CLASSES.items():
        if only_class and key != only_class:
            continue
        count = test_count if test_mode else (count_override or default_count)
        print(f"\n{'='*60}")
        print(f"  [{key}]  target={count}")
        print(f"{'='*60}")
        t0 = time.time()
        try:
            mod = __import__(module_name)
            fn  = getattr(mod, func_name)
            fn(count)
            elapsed = time.time() - t0
            results[key] = {"status": "OK", "count": count, "seconds": round(elapsed, 1)}
        except Exception as e:
            elapsed = time.time() - t0
            results[key] = {"status": f"ERROR: {e}", "count": 0, "seconds": round(elapsed, 1)}
            print(f"  ERROR: {e}")

    total = time.time() - total_start
    print(f"\n{'='*60}")
    print("GENERATION SUMMARY")
    print(f"{'='*60}")
    total_docs = 0
    for key, r in results.items():
        status_icon = "OK  " if r["status"] == "OK" else "FAIL"
        print(f"  [{status_icon}] {key:<30} {r['count']:>5} docs  {r['seconds']:>6.1f}s  {r['status'] if r['status']!='OK' else ''}")
        if r["status"] == "OK":
            total_docs += r["count"]
    print(f"{'='*60}")
    print(f"  Total: {total_docs} documents in {total:.1f}s")
    print(f"{'='*60}")

    # Final file count
    base = Path(__file__).parent.parent / "Synthetic_Data"
    if base.exists():
        print("\nFile counts per class folder:")
        for d in sorted(base.iterdir()):
            if d.is_dir():
                pdfs = list(d.rglob("*.pdf"))
                print(f"  {d.name}: {len(pdfs)} PDFs")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic DHL document training data")
    parser.add_argument("--count", type=int, default=None,
                        help="Override default count for all classes")
    parser.add_argument("--class", dest="cls", type=str, default=None,
                        help=f"Run only one class: {list(CLASSES.keys())}")
    parser.add_argument("--test", action="store_true",
                        help="Quick test mode: generate 5 of each")
    args = parser.parse_args()
    run_all(count_override=args.count, only_class=args.cls, test_mode=args.test)
