"""
Shared synthetic data generators for all 12 DHL document classes.
Produces realistic logistics field values using Faker + curated domain data.
"""

import random
from faker import Faker

fake = Faker()

# ── Curated shipping domain data ───────────────────────────────────────────

COUNTRIES = [
    ("United States", "US"), ("Germany", "DE"), ("China", "CN"),
    ("United Kingdom", "GB"), ("Japan", "JP"), ("France", "FR"),
    ("Netherlands", "NL"), ("Singapore", "SG"), ("India", "IN"),
    ("Brazil", "BR"), ("Australia", "AU"), ("Canada", "CA"),
    ("South Korea", "KR"), ("Italy", "IT"), ("Mexico", "MX"),
    ("Spain", "ES"), ("United Arab Emirates", "AE"), ("Hong Kong", "HK"),
    ("Malaysia", "MY"), ("Thailand", "TH"), ("Belgium", "BE"),
    ("Sweden", "SE"), ("Switzerland", "CH"), ("Poland", "PL"),
]

PORTS_SEA = [
    "Shanghai, CN", "Singapore, SG", "Rotterdam, NL", "Los Angeles, US",
    "Hamburg, DE", "Antwerp, BE", "Hong Kong, HK", "Qingdao, CN",
    "Busan, KR", "Dubai, AE", "Felixstowe, GB", "Long Beach, US",
    "New York, US", "Tokyo, JP", "Colombo, LK", "Tanjung Pelepas, MY",
]

AIRPORTS = [
    ("Los Angeles International", "LAX"), ("Frankfurt Airport", "FRA"),
    ("Hong Kong International", "HKG"), ("Dubai International", "DXB"),
    ("Singapore Changi", "SIN"), ("London Heathrow", "LHR"),
    ("Tokyo Narita", "NRT"), ("Shanghai Pudong", "PVG"),
    ("JFK New York", "JFK"), ("Amsterdam Schiphol", "AMS"),
    ("Chicago O'Hare", "ORD"), ("Paris CDG", "CDG"),
    ("Seoul Incheon", "ICN"), ("Sydney Kingsford Smith", "SYD"),
    ("Toronto Pearson", "YYZ"), ("Miami International", "MIA"),
]

INCOTERMS = ["EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF"]

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CNY", "SGD", "AUD", "CAD", "CHF", "AED"]

PAYMENT_TERMS = [
    "Net 30", "Net 60", "Net 90", "Due on Receipt",
    "50% Advance, 50% on Delivery", "Letter of Credit", "Telegraphic Transfer",
    "Open Account", "Cash Against Documents",
]

EXPORT_TYPES = ["Permanent", "Temporary", "Re-export", "Gift", "Personal Effects", "Repair"]

COMMODITY_CATEGORIES = [
    {
        "description": "Electronic Components - Printed Circuit Boards",
        "hs_code": "8534.00.00", "unit": "PCS", "unit_value_range": (15.0, 250.0),
        "unit_weight_kg": (0.05, 0.5),
    },
    {
        "description": "Industrial Machinery Parts - Steel Gears",
        "hs_code": "8483.40.00", "unit": "PCS", "unit_value_range": (45.0, 800.0),
        "unit_weight_kg": (0.5, 15.0),
    },
    {
        "description": "Pharmaceutical Products - Vitamins and Supplements",
        "hs_code": "2936.90.00", "unit": "BOX", "unit_value_range": (8.0, 120.0),
        "unit_weight_kg": (0.2, 2.0),
    },
    {
        "description": "Textile Fabrics - Woven Polyester",
        "hs_code": "5407.42.00", "unit": "MTR", "unit_value_range": (2.5, 18.0),
        "unit_weight_kg": (0.3, 1.2),
    },
    {
        "description": "Automotive Spare Parts - Brake Pads",
        "hs_code": "8708.30.00", "unit": "SET", "unit_value_range": (25.0, 180.0),
        "unit_weight_kg": (0.8, 4.0),
    },
    {
        "description": "Consumer Electronics - Wireless Earbuds",
        "hs_code": "8518.30.00", "unit": "PCS", "unit_value_range": (18.0, 95.0),
        "unit_weight_kg": (0.05, 0.15),
    },
    {
        "description": "Chemical Compounds - Industrial Solvents",
        "hs_code": "2901.10.00", "unit": "LTR", "unit_value_range": (3.0, 40.0),
        "unit_weight_kg": (0.9, 1.1),
    },
    {
        "description": "Plastic Products - Injection Moulded Components",
        "hs_code": "3926.90.00", "unit": "PCS", "unit_value_range": (1.5, 35.0),
        "unit_weight_kg": (0.1, 1.5),
    },
    {
        "description": "Medical Devices - Disposable Syringes",
        "hs_code": "9018.31.00", "unit": "CTN", "unit_value_range": (12.0, 80.0),
        "unit_weight_kg": (1.0, 5.0),
    },
    {
        "description": "Food Products - Processed Nuts and Seeds",
        "hs_code": "2008.19.00", "unit": "KGS", "unit_value_range": (4.0, 22.0),
        "unit_weight_kg": (1.0, 1.0),
    },
    {
        "description": "Optical Equipment - Camera Lenses",
        "hs_code": "9002.11.00", "unit": "PCS", "unit_value_range": (120.0, 1800.0),
        "unit_weight_kg": (0.2, 1.5),
    },
    {
        "description": "Rubber Goods - Industrial Seals and Gaskets",
        "hs_code": "4016.93.00", "unit": "PKG", "unit_value_range": (8.0, 95.0),
        "unit_weight_kg": (0.3, 3.0),
    },
    {
        "description": "Steel Products - Hot Rolled Coils",
        "hs_code": "7208.37.00", "unit": "KGS", "unit_value_range": (0.6, 2.5),
        "unit_weight_kg": (1.0, 1.0),
    },
    {
        "description": "Wooden Furniture - Office Chairs",
        "hs_code": "9401.30.00", "unit": "PCS", "unit_value_range": (85.0, 450.0),
        "unit_weight_kg": (8.0, 22.0),
    },
    {
        "description": "Paper Products - Packaging Cartons",
        "hs_code": "4819.10.00", "unit": "CTN", "unit_value_range": (2.0, 15.0),
        "unit_weight_kg": (0.5, 3.0),
    },
]

UN_NUMBERS = [
    ("UN1263", "Paint", "3", "II", "Flammable liquid"),
    ("UN1950", "Aerosols", "2.1", None, "Flammable gas"),
    ("UN3480", "Lithium ion batteries", "9", "II", "Miscellaneous"),
    ("UN1993", "Flammable liquid, n.o.s.", "3", "III", "Flammable liquid"),
    ("UN2794", "Batteries, wet, filled with acid", "8", None, "Corrosive"),
    ("UN1017", "Chlorine", "2.3", None, "Toxic gas"),
    ("UN1203", "Gasoline", "3", "II", "Flammable liquid"),
    ("UN3077", "Environmentally hazardous substance, solid, n.o.s.", "9", "III", "Miscellaneous"),
    ("UN2315", "Polychlorinated biphenyls", "9", "II", "Miscellaneous"),
    ("UN1072", "Oxygen, compressed", "2.2", None, "Non-flammable gas"),
]

VESSEL_NAMES = [
    "MSC OSCAR", "EVER GOLDEN", "CSCL GLOBE", "MOL TRIUMPH",
    "MADRID MAERSK", "CMA CGM ANTOINE DE SAINT EXUPERY",
    "OOCL HONG KONG", "MSC GULSUN", "HMM ALGECIRAS",
    "COSCO SHIPPING UNIVERSE", "EVERGREEN EVER ACE",
    "YANG MING MYTH", "ONE INNOVATION", "PIL PACIFIC",
]

PACKAGE_TYPES = ["Carton", "Pallet", "Crate", "Drum", "Bag", "Roll", "Bundle", "Case", "Cylinder"]

SHIPPING_MARKS_PREFIXES = ["ABC", "XYZ", "GLB", "TRD", "EXP", "IMP", "LOG", "FRT", "CRG"]


# ── Helper functions ────────────────────────────────────────────────────────

def random_company():
    suffixes = ["Ltd", "LLC", "Inc.", "GmbH", "Co.", "Corp.", "S.A.", "B.V.", "Pte Ltd", "AG"]
    words = [fake.last_name(), random.choice(["Global", "International", "Pacific", "Trade", "Industry", "Tech", "Commerce"])]
    random.shuffle(words)
    return f"{' '.join(words)} {random.choice(suffixes)}"

def random_address(country_code=None):
    if country_code:
        try:
            f = Faker(country_code)
            return f.address().replace("\n", ", ")
        except Exception:
            pass
    return fake.address().replace("\n", ", ")

def random_country():
    return random.choice(COUNTRIES)

def random_port_pair():
    ports = random.sample(PORTS_SEA, 2)
    return ports[0], ports[1]

def random_airport_pair():
    airports = random.sample(AIRPORTS, 2)
    return airports[0], airports[1]

def random_invoice_number():
    return f"INV-{fake.date_this_decade().strftime('%Y%m')}-{random.randint(1000, 9999)}"

def random_hawb_number():
    airline_code = random.choice(["020", "074", "176", "057", "618", "085", "125", "006", "045", "160"])
    return f"{airline_code}-{random.randint(10000000, 99999999)}"

def random_mawb_number():
    airline_code = random.choice(["020", "074", "176", "057", "618", "085", "125"])
    return f"{airline_code}-{random.randint(10000000, 99999999)}"

def random_bl_number():
    prefix = random.choice(["DHLG", "OOLU", "MAEU", "COSU", "EGLV", "YMLU"])
    return f"{prefix}{random.randint(100000000, 999999999)}"

def random_container_number():
    owner = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4))
    serial = ''.join(random.choices('0123456789', k=6))
    check = random.randint(0, 9)
    return f"{owner}{serial}{check}"

def random_seal_number():
    return f"{random.choice(['SL', 'CL', 'BL'])}{random.randint(100000, 999999)}"

def random_shipping_marks(shipper_abbr):
    po = f"PO-{random.randint(10000, 99999)}"
    return f"{shipper_abbr}\n{po}\nC/No. 1-{random.randint(5, 50)}"

def random_line_items(n_items=None):
    if n_items is None:
        n_items = random.randint(1, 6)
    items = []
    chosen = random.sample(COMMODITY_CATEGORIES, min(n_items, len(COMMODITY_CATEGORIES)))
    for cat in chosen:
        qty = random.randint(5, 500)
        unit_val = round(random.uniform(*cat["unit_value_range"]), 2)
        unit_wt = round(random.uniform(*cat["unit_weight_kg"]), 3)
        items.append({
            "description": cat["description"],
            "hs_code": cat["hs_code"],
            "unit": cat["unit"],
            "qty": qty,
            "unit_value": unit_val,
            "total_value": round(qty * unit_val, 2),
            "unit_weight_kg": unit_wt,
            "total_weight_kg": round(qty * unit_wt, 2),
            "country_of_origin": random_country()[0],
        })
    return items

def random_vat_number(country_code):
    prefixes = {"DE": "DE", "GB": "GB", "FR": "FR", "NL": "NL", "SG": "SG", "AU": "ABN"}
    prefix = prefixes.get(country_code, country_code)
    return f"{prefix}{random.randint(100000000, 999999999)}"

def random_dhl_account():
    return f"{random.randint(100000000, 999999999)}"

def random_dg_entry():
    return random.choice(UN_NUMBERS)

def random_voyage_number():
    return f"{random.randint(100, 999)}{''.join(random.choices('NESW', k=1))}"

def random_vgm_weight():
    # Realistic container VGM: 2,000 to 28,000 kg
    cargo = round(random.uniform(2000, 24000), 1)
    tare = random.choice([2100, 2200, 2300, 2400, 3800, 4000])  # standard container tares
    return cargo, tare, round(cargo + tare, 1)

def random_package_count():
    return random.randint(1, 500)

def random_cbm(packages):
    return round(packages * random.uniform(0.01, 0.08), 3)
