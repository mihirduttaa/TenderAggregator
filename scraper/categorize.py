import logging
import psycopg2

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "dbname": "tenderaggregator",
    "user": "",
    "password": "",
    "host": "localhost",
    "port": 5432,
}

CATEGORY_RULES = {
    "Roads & Bridges": [
        "road", "bridge", "highway", "flyover", "culvert", "pavement",
        "bitumen", "sadak", "pul", "bypass", "underpass", "footpath",
        "divider", "tar", "pitch"
    ],
    "Water Supply & Sanitation": [
        "water supply", "pipeline", "drinking water", "drainage", "sewage",
        "borewell", "submersible", "water tank", "overhead tank", "sewerage",
        "handpump", "tubewell", "water treatment", "nal jal", "jal jeevan",
        "sewer", "naali", "nala", "PAC", "ferric alum", "water chemical",
        "pump house", "submersible pump", "motor set", "water supply maintenance",
        "water maintenance"
    ],
    "Electrical Works": [
        "electrical", "electric", "streetlight", "street light", "wiring",
        "transformer", "substation", "solar", "mpeb", "generator",
        "inverter", "cable", "HT line", "LT line", "LED", "vidyut", "bijli",
        "pole", "fitting", "electrification"
    ],
    "Buildings & Construction": [
        "construction of", "building", "shed", "school", "hostel",
        "office construction", "hall", "toilet block", "anganwadi",
        "ashram", "bhavan", "awas", "dormitory", "classroom",
        "boundary wall", "compound wall", "plaster", "RCC", "ITI campus",
        "girls hostel", "boys hostel", "repair of building", "construction material"
    ],
    "Civil Works": [
        "civil", "dam", "canal", "foundation", "retaining wall",
        "embankment", "bund", "weir", "barrage", "check dam",
        "earthwork", "excavation", "geological", "structural", "nirman",
        "drain", "nalla", "paving", "paver block", "stage", "helipad",
        "painting", "white washing", "repair work", "CD maintenance"
    ],
    "Medical Equipment & Supplies": [
        "medical", "hospital", "USG", "surgical", "ambulance",
        "medicine", "drug", "pharmacy", "diagnostic", "x-ray",
        "ventilator", "oxygen", "ICU", "health equipment", "swasthya"
    ],
    "IT & Software": [
        "software", "website", "web portal", "mobile app", "server",
        "network", "ERP", "digital", "computer lab", "IT system",
        "hardware supply", "data center"
    ],
    "CCTV & Security Systems": [
        "CCTV", "surveillance camera", "IP camera", "biometric",
        "access control", "security camera"
    ],
    "Vehicle & Transport": [
        "vehicle", "bus", "truck", "tyre", "tube", "transport",
        "hiring of", "car hiring", "tractor", "crane", "JCB",
        "roller", "vahan", "ambulance purchase", "tanker", "tyres"
    ],
    "Furniture & Office Supplies": [
        "furniture", "chair", "table", "almirah", "cupboard",
        "bench", "stationery", "photocopier", "paper supply"
    ],
    "Security Services": [
        "security guard", "guard service", "watchman", "armed guard",
        "security agency", "suraksha"
    ],
    "Electric Fencing": [
        "electric fencing", "barbed wire", "wire fencing",
        "chain link", "boundary fencing", "jail fencing"
    ],
    "Agriculture & Horticulture": [
        "agriculture", "irrigation", "drip", "sprinkler", "seed",
        "fertilizer", "horticulture", "nursery", "plantation", "krishi",
        "garden", "beautification", "vertical garden", "landscaping"
    ],
    "Manpower & Labour": [
        "manpower", "labour", "housekeeping", "cleaning service",
        "sweeping", "contractual", "outsource", "daily wage", "safai",
        "maintenance", "rent of shop", "outsourcing", "cleaning work",
        "composting", "sanitary pad machine", "hand dryer"
    ],
    "Goods & Materials Supply": [
        "steel", "lohari", "udhyog", "khad", "beej", "krashi", "dawaiya",
        "samagri"
    ],
}

PRIORITY = [
    "Water Supply & Sanitation",
    "Medical Equipment & Supplies",
    "CCTV & Security Systems",
    "Electric Fencing",
    "IT & Software",
    "Electrical Works",
    "Roads & Bridges",
    "Vehicle & Transport",
    "Buildings & Construction",
    "Civil Works",
    "Agriculture & Horticulture",
    "Security Services",
    "Furniture & Office Supplies",
    "Manpower & Labour",
    "Goods & Materials Supply",
]

PRODUCT_CATEGORY_MAP = {
    "civil works - buildings":          "Buildings & Construction",
    "civil works - others":             "Civil Works",
    "civil works - roads":              "Roads & Bridges",
    "civil works - electrical":         "Electrical Works",
    "roads":                            "Roads & Bridges",
    "electrical works":                 "Electrical Works",
    "medical equipments/waste":         "Medical Equipment & Supplies",
    "hiring of vehicles":               "Vehicle & Transport",
    "miscellaneous goods":              "Goods & Materials Supply",
    "miscellaneous services":           "Manpower & Labour",
    "it services":                      "IT & Software",
    "computer hardware":                "IT & Software",
    "water supply":                     "Water Supply & Sanitation",
    "sanitation":                       "Water Supply & Sanitation",
    "furniture":                        "Furniture & Office Supplies",
    "office equipment":                 "Furniture & Office Supplies",
    "agriculture":                      "Agriculture & Horticulture",
    "security services":                "Security Services",
}

def classify(title: str, work_description: str, product_category: str) -> str:

    if product_category:
        pc = product_category.lower().strip()
        for key, cat in PRODUCT_CATEGORY_MAP.items():
            if key in pc:
                return cat
            
    text = f"{title} {work_description} {product_category}".lower()

    for category in PRIORITY:
        keywords = CATEGORY_RULES[category]
        if any(kw.lower() in text for kw in keywords):
            return category

    return "Miscellaneous"


def categorize_all():
    conn = psycopg2.connect(**DB_CONFIG)

    print("Connecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    print("Connected.")

    with conn.cursor() as cur:
        cur.execute("UPDATE tenders SET work_category = NULL")
    conn.commit()
    print("Reset all categories. Re-categorizing...")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, work_description, product_category
            FROM tenders
            ORDER BY id
        """)
        rows = cur.fetchall()

    print(f"Found {len(rows)} tenders to categorize.")

    logger.info(f"Found {len(rows)} tenders to categorize.")

    updated = 0
    category_counts = {}

    with conn.cursor() as cur:
        for tid, title, work_description, product_category in rows:
            category = classify(
                title or "",
                work_description or "",
                product_category or ""
            )

            cur.execute(
                "UPDATE tenders SET work_category = %s WHERE id = %s",
                (category, tid)
            )

            category_counts[category] = category_counts.get(category, 0) + 1
            updated += 1

    conn.commit()
    conn.close()

    logger.info(f"Categorized {updated} tenders.")
    print("\n── Category Distribution ──")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        bar = "█" * (count // 5)
        print(f"  {cat:<35} {count:>4}  {bar}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    categorize_all()