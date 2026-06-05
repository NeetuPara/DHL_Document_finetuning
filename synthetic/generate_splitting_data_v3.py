"""
Splitting data v3 — BALANCED class coverage, richer packets.

Targets:
  • Every class in ≥ 35% of packets
  • Average 6-8 pages per packet (range 4-12)
  • Same-class sequential (2-4× same doc type in one packet)
  • Diverse companions — not CI in every packet
  • All multipage-capable classes actually use their 2-page PDFs
"""
import json, random, argparse
from pathlib import Path
import fitz

BASE       = Path(__file__).parent.parent
SYNTH_DIR  = BASE / "Synthetic_Data"
MP_DIR     = BASE / "Synthetic_Data_MultiPage"
OUTPUT_DIR = BASE / "Synthetic_Data_Splitting_v2"
PDF_OUT    = OUTPUT_DIR / "pdfs"
ANN_OUT    = OUTPUT_DIR / "annotations"

# ── Class registry ────────────────────────────────────────────────────────
# (display_name, synth_folder, can_multipage, mp_folder)
CLASSES = {
    1:  ("Commercial Invoice",              "01_Commercial_Invoice",             True,  "01_Commercial_Invoice"),
    2:  ("House Bill of Lading",            "02_House_Bill_of_Lading",           True,  "02_House_Bill_of_Lading"),
    3:  ("Certificate of Origin",           "03_Certificate_of_Origin",          False, None),
    4:  ("Shipper's Letter of Instruction", "04_Shippers_Letter_of_Instruction", True,  "04_Shippers_Letter_of_Instruction"),
    5:  ("Dangerous Goods Declaration",     "05_Dangerous_Goods_Declaration",    True,  "05_Dangerous_Goods_Declaration"),
    6:  ("Verified Gross Mass",             "06_Verified_Gross_Mass",            True,  "06_Verified_Gross_Mass"),
    7:  ("House Airway Bill",               "07_House_Airway_Bill",              False, None),
    8:  ("Packing List",                    "08_Packing_List",                   True,  "08_Packing_List"),
    9:  ("Customs Declaration",             "09_Customs_Declarations",           False, None),
    10: ("Cargo Manifest",                  "10_Cargo_Manifest",                 True,  "10_Cargo_Manifest"),
    11: ("Import/Export License",           "11_Import_Export_License",          True,  "11_Import_Export_License"),
    12: ("Power of Attorney",               "12_Power_of_Attorney",              False, None),
}

# ── Template format ───────────────────────────────────────────────────────
# Each entry: (class_index, use_multipage)
# use_multipage=True → pick from Synthetic_Data_MultiPage (2 pages each)
# use_multipage=False → pick from Synthetic_Data (1 page each)
# Page count of a template = sum(2 if mp else 1 for each entry)

# ── Per-class template buckets ─────────────────────────────────────────────
# Rules:
#   • Focus class must appear at least once per template
#   • Min 5 entries per template → min 5 pages
#   • Mix single and multipage to hit 5-10 pages
#   • Same-class sequential included in most buckets
#   • Companions drawn from varied classes — not always CI

CLASS_BUCKETS = {

    # ── Class 1: Commercial Invoice ───────────────────────────────────────
    # CI is the most common doc — give it rich multi-format packets
    1: [
        # CI + PL + air set
        [(1,True),(8,True),(7,False),(3,False),(5,False)],          # 8pp: CI2+PL2+HAWB+COO+DGD
        [(1,False),(1,False),(8,True),(7,False),(4,False),(3,False)],# 8pp: CI+CI+PL2+HAWB+SLI+COO
        [(1,True),(1,False),(8,False),(7,False),(3,False),(12,False)],# 8pp: CI2+CI+PL+HAWB+COO+POA
        # CI + PL + ocean set
        [(1,True),(8,True),(2,False),(6,False),(3,False)],          # 8pp: CI2+PL2+HBL+VGM+COO
        [(1,False),(1,False),(8,False),(2,False),(6,False),(5,False)],# 7pp: 2×CI+PL+HBL+VGM+DGD
        [(1,True),(1,True),(8,False),(2,False),(3,False)],          # 7pp: CI2+CI2+PL+HBL+COO
        # CI + EEI / license
        [(1,True),(8,True),(11,False),(4,False),(7,False)],         # 8pp: CI2+PL2+EEI+SLI+HAWB
        [(1,False),(1,False),(1,False),(8,True),(7,False),(3,False)],# 8pp: 3×CI+PL2+HAWB+COO
        # CI heavy — same class sequential
        [(1,True),(1,True),(8,False),(3,False),(12,False)],         # 8pp: CI2+CI2+PL+COO+POA
        [(1,False),(1,False),(1,False),(1,False),(8,False),(7,False)],# 6pp: 4×CI+PL+HAWB
        # CI + postal
        [(1,True),(8,False),(9,False),(9,False),(7,False),(3,False)],# 8pp: CI2+PL+CN23+CN23+HAWB+COO
        [(1,False),(8,True),(9,False),(11,False),(4,False)],        # 7pp: CI+PL2+CN23+EEI+SLI
    ],

    # ── Class 2: House Bill of Lading (ocean freight) ────────────────────
    2: [
        # HBL + ocean companions (no CI)
        [(2,True),(6,False),(6,False),(5,True),(8,True)],           # 9pp: HBL2+VGM+VGM+DGD2+PL2
        [(2,False),(2,False),(6,True),(5,False),(8,False),(3,False)],# 8pp: HBL+HBL+VGM2+DGD+PL+COO
        [(2,True),(2,False),(6,False),(8,True),(3,False),(12,False)],# 8pp: HBL2+HBL+VGM+PL2+COO+POA
        # HBL + CI set
        [(2,False),(1,True),(8,True),(6,False),(3,False)],          # 8pp: HBL+CI2+PL2+VGM+COO
        [(2,True),(1,False),(8,False),(6,False),(5,False),(3,False)],# 8pp: HBL2+CI+PL+VGM+DGD+COO
        [(2,False),(2,False),(1,True),(8,False),(4,False)],         # 7pp: 2×HBL+CI2+PL+SLI
        # HBL sequential
        [(2,True),(2,True),(1,False),(6,False),(3,False)],          # 7pp: HBL2+HBL2+CI+VGM+COO
        [(2,False),(2,False),(2,False),(6,False),(8,False),(5,False)],# 7pp: 3×HBL+VGM+PL+DGD
        # HBL + manifest
        [(2,False),(10,True),(1,True),(6,False),(8,False)],         # 8pp: HBL+Manifest2+CI2+VGM+PL
        [(2,True),(10,False),(1,False),(8,False),(6,False),(3,False)],# 8pp: HBL2+Manifest+CI+PL+VGM+COO
        [(2,False),(2,False),(10,False),(6,True),(1,False),(3,False)],# 8pp: 2×HBL+Manifest+VGM2+CI+COO
        [(2,True),(2,False),(5,True),(6,False),(8,True)],           # 9pp: HBL2+HBL+DGD2+VGM+PL2
    ],

    # ── Class 3: Certificate of Origin ───────────────────────────────────
    3: [
        # COO + air
        [(3,False),(1,True),(8,False),(7,False),(4,False),(5,False)],# 8pp: COO+CI2+PL+HAWB+SLI+DGD
        [(3,False),(3,False),(1,False),(8,True),(7,False),(12,False)],# 8pp: 2×COO+CI+PL2+HAWB+POA
        [(3,False),(1,False),(7,False),(4,True),(8,False),(9,False)],# 8pp: COO+CI+HAWB+SLI2+PL+CN23
        # COO + ocean
        [(3,False),(2,False),(1,True),(8,False),(6,False)],         # 7pp: COO+HBL+CI2+PL+VGM
        [(3,False),(3,False),(2,True),(1,False),(8,False),(6,False)],# 8pp: 2×COO+HBL2+CI+PL+VGM
        [(3,False),(2,False),(6,False),(1,False),(8,True),(5,False)],# 8pp: COO+HBL+VGM+CI+PL2+DGD
        # COO sequential
        [(3,False),(3,False),(3,False),(1,True),(8,False),(7,False)],# 8pp: 3×COO+CI2+PL+HAWB
        [(3,False),(3,False),(1,False),(8,False),(2,False),(12,False)],# 7pp: 2×COO+CI+PL+HBL+POA
        # COO + EEI
        [(3,False),(11,False),(1,True),(8,False),(4,False)],        # 7pp: COO+EEI+CI2+PL+SLI
        [(3,False),(3,False),(11,False),(1,False),(8,True),(7,False)],# 8pp: 2×COO+EEI+CI+PL2+HAWB
        [(3,False),(1,False),(8,False),(2,False),(6,False),(5,False),(12,False)],# 8pp: full ocean set
        [(3,False),(3,False),(1,False),(7,False),(4,False),(8,False),(9,False)], # 8pp: 2×COO+air set
    ],

    # ── Class 4: Shipper's Letter of Instruction ─────────────────────────
    4: [
        # SLI + air freight
        [(4,True),(1,True),(8,False),(7,False),(3,False)],          # 8pp: SLI2+CI2+PL+HAWB+COO
        [(4,False),(4,False),(1,False),(8,True),(7,False),(5,False)],# 8pp: 2×SLI+CI+PL2+HAWB+DGD
        [(4,True),(1,False),(8,False),(7,False),(9,False),(3,False)],# 8pp: SLI2+CI+PL+HAWB+CN23+COO
        # SLI + ocean freight
        [(4,True),(2,False),(1,False),(8,False),(6,False),(3,False)],# 8pp: SLI2+HBL+CI+PL+VGM+COO
        [(4,False),(4,False),(2,True),(1,False),(6,False),(8,False)],# 8pp: 2×SLI+HBL2+CI+VGM+PL
        [(4,False),(2,False),(6,False),(1,True),(8,True),(3,False)], # 9pp: SLI+HBL+VGM+CI2+PL2+COO
        # SLI sequential
        [(4,True),(4,True),(1,False),(8,False),(3,False)],          # 7pp: SLI2+SLI2+CI+PL+COO
        [(4,False),(4,False),(4,False),(1,True),(8,False),(7,False)],# 8pp: 3×SLI+CI2+PL+HAWB
        # SLI + POA + EEI
        [(4,False),(12,False),(1,True),(8,False),(11,False)],       # 7pp: SLI+POA+CI2+PL+EEI
        [(4,True),(12,False),(11,False),(1,False),(8,False),(3,False)],# 8pp: SLI2+POA+EEI+CI+PL+COO
        [(4,False),(4,False),(1,False),(7,False),(8,False),(3,False),(5,False)], # 8pp: 2×SLI+CI+HAWB+PL+COO+DGD
        [(4,True),(1,False),(8,True),(5,True),(7,False)],           # 9pp: SLI2+CI+PL2+DGD2+HAWB
    ],

    # ── Class 5: Dangerous Goods Declaration ─────────────────────────────
    5: [
        # DGD + air
        [(5,True),(1,True),(7,False),(8,False),(4,False)],          # 8pp: DGD2+CI2+HAWB+PL+SLI
        [(5,False),(5,False),(1,False),(7,False),(8,True),(3,False)],# 8pp: 2×DGD+CI+HAWB+PL2+COO
        [(5,True),(1,False),(8,False),(7,False),(4,False),(3,False)],# 8pp: DGD2+CI+PL+HAWB+SLI+COO
        # DGD + ocean
        [(5,True),(2,False),(1,False),(8,False),(6,False),(3,False)],# 8pp: DGD2+HBL+CI+PL+VGM+COO
        [(5,False),(5,False),(2,True),(6,False),(1,False),(8,False)],# 8pp: 2×DGD+HBL2+VGM+CI+PL
        [(5,True),(5,False),(2,False),(6,True),(1,False),(8,False)], # 9pp: DGD2+DGD+HBL+VGM2+CI+PL
        # DGD sequential — multiple hazmat shipments
        [(5,True),(5,True),(1,False),(8,False),(4,False)],          # 7pp: DGD2+DGD2+CI+PL+SLI
        [(5,False),(5,False),(5,False),(1,True),(7,False),(8,False)],# 8pp: 3×DGD+CI2+HAWB+PL
        [(5,True),(5,True),(5,False),(2,False),(8,False),(3,False)], # 9pp: DGD2+DGD2+DGD+HBL+PL+COO
        [(5,False),(5,False),(5,False),(5,False),(1,False),(8,False)],# 7pp: 4×DGD+CI+PL (big hazmat)
        [(5,True),(1,False),(8,True),(2,False),(6,False),(11,False)],# 8pp: DGD2+CI+PL2+HBL+VGM+EEI
        [(5,False),(5,False),(7,False),(1,True),(4,False),(8,False)],# 8pp: 2×DGD+HAWB+CI2+SLI+PL
    ],

    # ── Class 6: Verified Gross Mass ─────────────────────────────────────
    6: [
        # VGM — always ocean, goes with HBL
        [(6,True),(2,False),(1,True),(8,False),(3,False)],          # 8pp: VGM2+HBL+CI2+PL+COO
        [(6,False),(6,False),(2,True),(1,False),(8,False),(5,False)],# 8pp: 2×VGM+HBL2+CI+PL+DGD
        [(6,True),(6,False),(2,False),(1,False),(8,True),(3,False)], # 9pp: VGM2+VGM+HBL+CI+PL2+COO
        # VGM sequential — multiple containers
        [(6,True),(6,True),(2,False),(1,False),(8,False),(3,False)], # 8pp: VGM2+VGM2+HBL+CI+PL+COO
        [(6,False),(6,False),(6,False),(2,True),(1,False),(8,False)],# 8pp: 3×VGM+HBL2+CI+PL
        [(6,True),(6,True),(6,False),(2,False),(1,False),(3,False)], # 9pp: VGM2+VGM2+VGM+HBL+CI+COO
        [(6,False),(6,False),(6,False),(6,False),(2,False),(1,False)],# 7pp: 4×VGM+HBL+CI (big shipment)
        # VGM + DGD (hazmat ocean)
        [(6,True),(5,True),(2,False),(1,False),(8,False),(3,False)], # 8pp: VGM2+DGD2+HBL+CI+PL+COO
        [(6,False),(6,False),(5,False),(2,True),(1,False),(8,False)],# 8pp: 2×VGM+DGD+HBL2+CI+PL
        [(6,True),(6,False),(5,True),(2,False),(8,True),(3,False)],  # 9pp: VGM2+VGM+DGD2+HBL+PL2+COO
        [(6,False),(6,False),(5,False),(5,False),(2,False),(1,True)],# 8pp: 2×VGM+2×DGD+HBL+CI2
        [(6,True),(10,False),(2,False),(1,False),(8,False),(3,False)],# 8pp: VGM2+Manifest+HBL+CI+PL+COO
    ],

    # ── Class 7: House Airway Bill ────────────────────────────────────────
    7: [
        # HAWB + air set
        [(7,False),(1,True),(8,False),(4,False),(3,False),(9,False)],# 8pp: HAWB+CI2+PL+SLI+COO+CN23
        [(7,False),(7,False),(1,False),(8,True),(4,False),(5,False)],# 8pp: 2×HAWB+CI+PL2+SLI+DGD
        [(7,False),(1,False),(8,False),(4,True),(5,False),(3,False)],# 8pp: HAWB+CI+PL+SLI2+DGD+COO
        # HAWB sequential — consolidated shipments
        [(7,False),(7,False),(7,False),(1,True),(8,False),(4,False)],# 8pp: 3×HAWB+CI2+PL+SLI
        [(7,False),(7,False),(1,False),(8,False),(4,False),(3,False),(5,False)], # 8pp: 2×HAWB+CI+PL+SLI+COO+DGD
        [(7,False),(7,False),(7,False),(7,False),(1,False),(8,False)],# 7pp: 4×HAWB+CI+PL (consolidation)
        # HAWB + EEI + postal
        [(7,False),(11,False),(1,True),(8,False),(4,False),(3,False)],# 8pp: HAWB+EEI+CI2+PL+SLI+COO
        [(7,False),(9,False),(9,False),(1,False),(8,True),(4,False)],# 8pp: HAWB+CN23+CN23+CI+PL2+SLI
        [(7,False),(7,False),(9,False),(1,False),(4,True),(8,False)],# 8pp: 2×HAWB+CN23+CI+SLI2+PL
        # HAWB + manifest
        [(7,False),(10,False),(1,True),(8,False),(4,False),(3,False)],# 8pp: HAWB+Manifest+CI2+PL+SLI+COO
        [(7,False),(7,False),(10,True),(1,False),(8,False),(5,False)],# 8pp: 2×HAWB+Manifest2+CI+PL+DGD
        [(7,False),(1,False),(8,False),(5,True),(4,False),(11,False)],# 8pp: HAWB+CI+PL+DGD2+SLI+EEI
    ],

    # ── Class 8: Packing List ─────────────────────────────────────────────
    8: [
        # PL + air
        [(8,True),(1,True),(7,False),(4,False),(3,False)],          # 7pp: PL2+CI2+HAWB+SLI+COO
        [(8,False),(8,False),(1,True),(7,False),(4,True),(3,False)], # 9pp: 2×PL+CI2+HAWB+SLI2+COO
        [(8,True),(1,False),(7,False),(4,False),(9,False),(3,False)],# 8pp: PL2+CI+HAWB+SLI+CN23+COO
        # PL + ocean
        [(8,True),(2,False),(1,True),(6,False),(3,False)],          # 8pp: PL2+HBL+CI2+VGM+COO
        [(8,False),(8,False),(2,True),(1,False),(6,False),(5,False)],# 8pp: 2×PL+HBL2+CI+VGM+DGD
        [(8,True),(8,False),(2,False),(6,True),(1,False),(3,False)], # 9pp: PL2+PL+HBL+VGM2+CI+COO
        # PL sequential
        [(8,True),(8,True),(1,False),(7,False),(3,False)],          # 7pp: PL2+PL2+CI+HAWB+COO
        [(8,False),(8,False),(8,False),(1,True),(7,False),(4,False)],# 8pp: 3×PL+CI2+HAWB+SLI
        [(8,True),(8,True),(8,False),(1,False),(2,False),(3,False)], # 8pp: PL2+PL2+PL+CI+HBL+COO
        # PL + EEI / license
        [(8,True),(11,False),(1,True),(4,False),(3,False)],         # 8pp: PL2+EEI+CI2+SLI+COO
        [(8,False),(8,False),(11,False),(1,False),(7,False),(4,False),(3,False)],# 8pp: 2×PL+EEI+CI+HAWB+SLI+COO
        [(8,True),(12,False),(1,False),(7,False),(4,False),(3,False)],# 8pp: PL2+POA+CI+HAWB+SLI+COO
    ],

    # ── Class 9: Customs Declaration (CN22/CN23) ─────────────────────────
    # Postal / express parcels — realistic batch scenarios
    9: [
        # CN23 batch — multiple parcels
        [(9,False),(9,False),(9,False),(1,True),(7,False),(8,False)],# 8pp: 3×CN23+CI2+HAWB+PL
        [(9,False),(9,False),(1,False),(8,False),(7,False),(4,False),(3,False)],# 8pp: 2×CN23+CI+PL+HAWB+SLI+COO
        [(9,False),(9,False),(9,False),(9,False),(1,False),(7,False)],# 7pp: 4×CN23+CI+HAWB (parcel batch)
        [(9,False),(9,False),(9,False),(1,False),(8,True),(7,False)],# 8pp: 3×CN23+CI+PL2+HAWB
        [(9,False),(9,False),(9,False),(9,False),(9,False),(1,True)],# 7pp: 5×CN23+CI2 (bulk parcels)
        # CN23 + POA + CI
        [(9,False),(9,False),(12,False),(1,True),(8,False),(7,False)],# 8pp: 2×CN23+POA+CI2+PL+HAWB
        [(9,False),(12,False),(1,False),(7,False),(8,False),(4,False),(3,False)],# 8pp: CN23+POA+CI+HAWB+PL+SLI+COO
        # CN23 + EEI
        [(9,False),(9,False),(11,False),(1,True),(7,False),(4,False)],# 8pp: 2×CN23+EEI+CI2+HAWB+SLI
        [(9,False),(11,False),(1,False),(8,False),(7,False),(4,False),(9,False)],# 8pp: CN23+EEI+CI+PL+HAWB+SLI+CN23
        # CN23 heavy batch
        [(9,False),(9,False),(9,False),(9,False),(7,False),(8,False)],# 7pp: 4×CN23+HAWB+PL (no CI)
        [(9,False),(9,False),(9,False),(1,False),(7,False),(4,True)],# 8pp: 3×CN23+CI+HAWB+SLI2
        [(9,False),(9,False),(1,True),(8,False),(7,False),(3,False)],# 8pp: 2×CN23+CI2+PL+HAWB+COO
    ],

    # ── Class 10: Cargo Manifest ──────────────────────────────────────────
    10: [
        # Manifest + ocean
        [(10,True),(2,False),(1,True),(6,False),(8,False)],         # 8pp: Manifest2+HBL+CI2+VGM+PL
        [(10,False),(10,False),(2,True),(6,False),(1,False),(8,False)],# 8pp: 2×Manifest+HBL2+VGM+CI+PL
        [(10,True),(2,False),(6,True),(1,False),(5,False),(3,False)],# 9pp: Manifest2+HBL+VGM2+CI+DGD+COO
        # Manifest + air
        [(10,False),(7,False),(7,False),(1,True),(8,False),(4,False)],# 8pp: Manifest+2×HAWB+CI2+PL+SLI
        [(10,True),(7,False),(1,False),(8,False),(4,False),(3,False)],# 8pp: Manifest2+HAWB+CI+PL+SLI+COO
        [(10,False),(10,False),(7,False),(1,False),(8,True),(4,False)],# 8pp: 2×Manifest+HAWB+CI+PL2+SLI
        # Manifest sequential
        [(10,True),(10,False),(2,False),(1,False),(8,False),(6,False)],# 8pp: Manifest2+Manifest+HBL+CI+PL+VGM
        [(10,False),(10,False),(10,False),(2,False),(1,True),(6,False)],# 8pp: 3×Manifest+HBL+CI2+VGM
        # Manifest + EEI
        [(10,False),(11,False),(2,True),(1,False),(8,False),(6,False)],# 8pp: Manifest+EEI+HBL2+CI+PL+VGM
        [(10,True),(11,False),(7,False),(1,False),(4,False),(8,False)],# 8pp: Manifest2+EEI+HAWB+CI+SLI+PL
        [(10,False),(10,False),(11,False),(2,False),(6,True),(1,False)],# 8pp: 2×Manifest+EEI+HBL+VGM2+CI
        [(10,True),(10,True),(2,False),(5,False),(1,False),(3,False)], # 9pp: Manifest2+Manifest2+HBL+DGD+CI+COO
    ],

    # ── Class 11: Import/Export License / EEI ────────────────────────────
    11: [
        # EEI + air export
        [(11,True),(1,True),(8,False),(7,False),(4,False)],         # 8pp: EEI2+CI2+PL+HAWB+SLI
        [(11,False),(11,False),(1,False),(8,True),(7,False),(4,False)],# 8pp: 2×EEI+CI+PL2+HAWB+SLI
        [(11,True),(1,False),(7,False),(4,True),(8,False),(3,False)],# 9pp: EEI2+CI+HAWB+SLI2+PL+COO
        # EEI + ocean import
        [(11,True),(2,False),(1,True),(8,False),(6,False)],         # 8pp: EEI2+HBL+CI2+PL+VGM
        [(11,False),(11,False),(2,True),(1,False),(6,False),(8,False)],# 8pp: 2×EEI+HBL2+CI+VGM+PL
        [(11,True),(2,False),(6,False),(10,False),(1,False),(8,False)],# 8pp: EEI2+HBL+VGM+Manifest+CI+PL
        # EEI sequential — multiple entries
        [(11,True),(11,True),(1,False),(8,False),(4,False)],        # 7pp: EEI2+EEI2+CI+PL+SLI
        [(11,False),(11,False),(11,False),(1,True),(8,False),(7,False)],# 8pp: 3×EEI+CI2+PL+HAWB
        [(11,True),(11,False),(11,False),(2,False),(1,False),(6,False)],# 8pp: EEI2+2×EEI+HBL+CI+VGM
        # EEI + POA + COO
        [(11,False),(12,False),(1,True),(8,False),(4,False),(3,False)],# 8pp: EEI+POA+CI2+PL+SLI+COO
        [(11,True),(3,False),(1,False),(8,False),(7,False),(4,False)],# 8pp: EEI2+COO+CI+PL+HAWB+SLI
        [(11,False),(11,False),(3,False),(1,True),(8,True),(2,False)],# 9pp: 2×EEI+COO+CI2+PL2+HBL
    ],

    # ── Class 12: Power of Attorney ───────────────────────────────────────
    12: [
        # POA + air customs set
        [(12,False),(1,True),(8,False),(7,False),(4,False),(3,False)],# 8pp: POA+CI2+PL+HAWB+SLI+COO
        [(12,False),(12,False),(1,False),(8,True),(7,False),(4,False)],# 8pp: 2×POA+CI+PL2+HAWB+SLI
        [(12,False),(1,False),(8,False),(7,False),(4,True),(9,False)],# 8pp: POA+CI+PL+HAWB+SLI2+CN23
        # POA + ocean customs set
        [(12,False),(2,False),(1,True),(8,False),(6,False),(3,False)],# 8pp: POA+HBL+CI2+PL+VGM+COO
        [(12,False),(12,False),(2,True),(1,False),(6,False),(8,False)],# 8pp: 2×POA+HBL2+CI+VGM+PL
        [(12,False),(2,False),(6,False),(11,False),(1,True),(8,False)],# 8pp: POA+HBL+VGM+EEI+CI2+PL
        # POA sequential — multiple authorisations
        [(12,False),(12,False),(12,False),(1,True),(8,False),(4,False)],# 8pp: 3×POA+CI2+PL+SLI
        [(12,False),(12,False),(1,False),(8,False),(4,False),(3,False),(7,False)],# 8pp: 2×POA+CI+PL+SLI+COO+HAWB
        # POA + EEI + CN23
        [(12,False),(11,False),(1,True),(8,False),(4,False),(3,False)],# 8pp: POA+EEI+CI2+PL+SLI+COO
        [(12,False),(9,False),(9,False),(1,False),(7,False),(4,False),(8,False)],# 8pp: POA+2×CN23+CI+HAWB+SLI+PL
        [(12,False),(12,False),(11,True),(1,False),(8,False),(3,False)],# 8pp: 2×POA+EEI2+CI+PL+COO
        [(12,False),(4,False),(1,False),(8,False),(2,False),(6,False),(3,False)],# 8pp: POA+SLI+CI+PL+HBL+VGM+COO
    ],
}

# ── Pool helpers ──────────────────────────────────────────────────────────
_sp = {}; _mp = {}

def sp(folder):
    if folder not in _sp:
        p = sorted((SYNTH_DIR / folder / "pdfs").rglob("*.pdf"))
        _sp[folder] = p
    return _sp[folder]

def mp(mf):
    if mf not in _mp:
        p = sorted((MP_DIR / mf / "pdfs").rglob("*.pdf"))
        _mp[mf] = p
    return _mp[mf]

def pick(cls_idx, force_multipage=False):
    name, folder, can_mp, mp_folder = (CLASSES[cls_idx][0], CLASSES[cls_idx][1],
                                        CLASSES[cls_idx][2], CLASSES[cls_idx][3])
    if force_multipage and can_mp and mp_folder:
        pool = mp(mp_folder)
        if pool:
            return random.choice(pool), True
    pool = sp(folder)
    return (random.choice(pool), False) if pool else (None, False)


# Classes that are under-represented as companions and need injection boosting.
# Probability = chance a packet gets one extra copy of that class injected,
# provided the class isn't already in the template.
INJECT_PROBS = {
    5:  0.22,   # Dangerous Goods Declaration
    9:  0.32,   # Customs Declaration (CN23)
    10: 0.28,   # Cargo Manifest
    11: 0.18,   # Import/Export License
    12: 0.32,   # Power of Attorney
}


def build_packet(packet_id, template):
    blocks = []
    for cls_idx, force_mp in template:
        path, is_mp = pick(cls_idx, force_mp)
        if path is None:
            continue
        blocks.append((cls_idx, path, is_mp))

    if len(blocks) < 2:
        return None

    # Inject underrepresented classes if not already in the packet
    present = {cls_idx for cls_idx, _, _ in blocks}
    for inject_cls, prob in INJECT_PROBS.items():
        if inject_cls not in present and random.random() < prob:
            path, is_mp = pick(inject_cls, False)
            if path:
                blocks.append((inject_cls, path, is_mp))
                present.add(inject_cls)

    # Shuffle so injected docs don't always land at the end
    random.shuffle(blocks)

    merged = fitz.open()
    docs = []
    cur = 1
    for cls_idx, path, is_mp in blocks:
        try:
            src = fitz.open(str(path))
        except Exception:
            continue
        n = len(src)
        merged.insert_pdf(src)
        src.close()
        docs.append({
            "doc_class":        CLASSES[cls_idx][0],
            "class_index":      cls_idx,
            "page_start":       cur,
            "page_end":         cur + n - 1,
            "n_pages":          n,
            "is_multipage_doc": is_mp,
            "source_file":      path.name,
        })
        cur += n

    total_pages = cur - 1
    if total_pages < 2:
        merged.close()
        return None

    fname = f"packet_{packet_id:04d}.pdf"
    merged.save(str(PDF_OUT / fname))
    merged.close()

    ann = {
        "packet_id":      fname.replace(".pdf", ""),
        "total_pages":    total_pages,
        "n_documents":    len(docs),
        "class_sequence": [d["doc_class"] for d in docs],
        "task":           "splitting",
        "note":           "is_multipage_doc=true means consecutive pages are CONTINUATION of same document instance.",
        "documents":      docs,
    }
    (ANN_OUT / fname.replace(".pdf", ".json")).write_text(json.dumps(ann, indent=2))
    return ann


def generate(count=5000):
    PDF_OUT.mkdir(parents=True, exist_ok=True)
    ANN_OUT.mkdir(parents=True, exist_ok=True)
    for f in list(PDF_OUT.glob("*.pdf")) + list(ANN_OUT.glob("*.json")):
        f.unlink()

    print(f"Generating {count} BALANCED splitting packets (all 12 classes)...")

    # Weighted own-bucket allocation.
    # CI/PL appear as companions in every bucket so they need fewer own-bucket
    # packets. Niche classes (CN23/Manifest/POA/DGD) rarely appear as companions
    # so they get a larger own-bucket share. Injection (see build_packet) then
    # brings them up to ≥35% coverage without inflating total packet count.
    BUCKET_WEIGHTS = {
        1: 0.40,  # CI  — companion in every bucket
        2: 0.80,
        3: 0.80,
        4: 1.00,
        5: 1.50,  # DGD — boosted
        6: 0.80,
        7: 0.80,
        8: 0.40,  # PL  — companion in every bucket
        9: 2.50,  # CN23 — rare companion
        10: 2.50, # Manifest — rare companion
        11: 1.20,
        12: 2.50, # POA — rare companion
    }
    total_weight = sum(BUCKET_WEIGHTS.values())
    schedule = []
    for cls_idx in range(1, 13):
        bucket = CLASS_BUCKETS[cls_idx]
        n_this = max(1, round(count * BUCKET_WEIGHTS[cls_idx] / total_weight))
        for i in range(n_this):
            schedule.append(bucket[i % len(bucket)])

    random.shuffle(schedule)

    ok = fail = 0
    page_counts = []
    doc_counts  = []
    mp_count    = 0

    for i, tmpl in enumerate(schedule, 1):
        ann = build_packet(i, tmpl)
        if ann:
            ok += 1
            page_counts.append(ann["total_pages"])
            doc_counts.append(ann["n_documents"])
            mp_count += sum(1 for d in ann["documents"] if d["is_multipage_doc"])
            if i <= 5 or i % 500 == 0:
                seq = " + ".join(
                    f"{d['doc_class'][:10]}(pp{d['page_start']}-{d['page_end']})"
                    for d in ann["documents"]
                )
                print(f"  [{i:04d}] {ann['total_pages']}pp  {ann['n_documents']} docs  |  {seq}")
        else:
            fail += 1

    # ── Coverage report ───────────────────────────────────────────────────
    from collections import Counter, defaultdict
    class_count = Counter()
    packet_has  = defaultdict(int)
    same_class_sequential = 0

    for f in sorted(ANN_OUT.glob("*.json")):
        d = json.loads(f.read_text())
        seen = set()
        seq = d["class_sequence"]
        # Count same-class sequential pairs
        for j in range(len(seq) - 1):
            if seq[j] == seq[j + 1]:
                same_class_sequential += 1
        for doc in d["documents"]:
            class_count[doc["doc_class"]] += 1
            seen.add(doc["doc_class"])
        for cls in seen:
            packet_has[cls] += 1

    total = ok
    print(f"\n{'='*78}")
    print(f"Results: {ok} generated, {fail} failed")
    print(f"Avg pages/packet: {sum(page_counts)/len(page_counts):.1f}  "
          f"min={min(page_counts)}  max={max(page_counts)}")
    print(f"Avg docs/packet:  {sum(doc_counts)/len(doc_counts):.1f}")
    print(f"Multi-page doc rate: {100*mp_count/sum(doc_counts):.0f}%")
    print(f"Same-class sequential pairs: {same_class_sequential:,}")

    print(f"\n{'Class':<42} {'Instances':>10} {'Packets':>10} {'Coverage':>10} {'Status':>8}")
    print('-' * 82)
    all_ok = True
    for cls_idx in range(1, 13):
        cls_name = CLASSES[cls_idx][0]
        n   = class_count.get(cls_name, 0)
        p   = packet_has.get(cls_name, 0)
        pct = 100 * p / total if total else 0
        status = "OK " if pct >= 35 else ("LOW" if pct >= 20 else "!!!")
        if pct < 35:
            all_ok = False
        print(f"  [{status}] {cls_name:<38} {n:>10,} {p:>10,} {pct:>9.1f}% ")
    print('-' * 82)
    if all_ok:
        print("  All 12 classes >= 35% coverage")
    else:
        print("  WARNING: some classes below 35% target")
    print(f"\nOutput: {OUTPUT_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=5000)
    generate(p.parse_args().count)
