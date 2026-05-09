"""Nice classification of goods and services (12th edition, in force 2024+).

45 classes total: 1-34 are goods, 35-45 are services. Used by trademark
applicants worldwide. Reference data, doesn't change between yearly
revisions for the high-level descriptions.

Source: WIPO Nice Classification (https://www.wipo.int/classifications/nice/).
"""

NICE_CLASSES: list[dict] = [
    {"number": 1, "kind": "goods", "title": "Chemicals"},
    {"number": 2, "kind": "goods", "title": "Paints, varnishes, anti-corrosives"},
    {"number": 3, "kind": "goods", "title": "Cosmetics and cleaning products"},
    {"number": 4, "kind": "goods", "title": "Industrial oils, fuels, lubricants"},
    {"number": 5, "kind": "goods", "title": "Pharmaceuticals, dietetic substances"},
    {"number": 6, "kind": "goods", "title": "Common metals and goods of common metal"},
    {"number": 7, "kind": "goods", "title": "Machines and machine tools"},
    {"number": 8, "kind": "goods", "title": "Hand-operated tools"},
    {"number": 9, "kind": "goods", "title": "Computers, software, electronics"},
    {"number": 10, "kind": "goods", "title": "Medical apparatus"},
    {"number": 11, "kind": "goods", "title": "Lighting, heating, cooling, sanitary"},
    {"number": 12, "kind": "goods", "title": "Vehicles"},
    {"number": 13, "kind": "goods", "title": "Firearms, ammunition, fireworks"},
    {"number": 14, "kind": "goods", "title": "Precious metals, jewellery, watches"},
    {"number": 15, "kind": "goods", "title": "Musical instruments"},
    {"number": 16, "kind": "goods", "title": "Paper goods, printed matter, stationery"},
    {"number": 17, "kind": "goods", "title": "Rubber, plastics, insulation"},
    {"number": 18, "kind": "goods", "title": "Leather, luggage, umbrellas"},
    {"number": 19, "kind": "goods", "title": "Non-metallic building materials"},
    {"number": 20, "kind": "goods", "title": "Furniture, frames, containers"},
    {"number": 21, "kind": "goods", "title": "Household and kitchen utensils"},
    {"number": 22, "kind": "goods", "title": "Ropes, nets, tents, awnings, sails"},
    {"number": 23, "kind": "goods", "title": "Yarns and threads"},
    {"number": 24, "kind": "goods", "title": "Textiles"},
    {"number": 25, "kind": "goods", "title": "Clothing, footwear, headwear"},
    {"number": 26, "kind": "goods", "title": "Lace, ribbons, buttons, zippers"},
    {"number": 27, "kind": "goods", "title": "Carpets, rugs, wall hangings"},
    {"number": 28, "kind": "goods", "title": "Games, toys, sporting articles"},
    {"number": 29, "kind": "goods", "title": "Meat, fish, dairy, processed foods"},
    {"number": 30, "kind": "goods", "title": "Coffee, tea, flour, baked goods"},
    {"number": 31, "kind": "goods", "title": "Live animals, raw fruits, seeds"},
    {"number": 32, "kind": "goods", "title": "Beers, non-alcoholic beverages"},
    {"number": 33, "kind": "goods", "title": "Alcoholic beverages (excl. beer)"},
    {"number": 34, "kind": "goods", "title": "Tobacco, smokers' articles"},
    {"number": 35, "kind": "services", "title": "Advertising, business management"},
    {"number": 36, "kind": "services", "title": "Insurance, financial, real estate"},
    {"number": 37, "kind": "services", "title": "Construction, repair, installation"},
    {"number": 38, "kind": "services", "title": "Telecommunications"},
    {"number": 39, "kind": "services", "title": "Transport, packaging, storage, travel"},
    {"number": 40, "kind": "services", "title": "Treatment of materials"},
    {"number": 41, "kind": "services", "title": "Education, entertainment, sport"},
    {"number": 42, "kind": "services", "title": "Scientific & technological services, design, software"},
    {"number": 43, "kind": "services", "title": "Food services, temporary accommodation"},
    {"number": 44, "kind": "services", "title": "Medical, veterinary, agricultural services"},
    {"number": 45, "kind": "services", "title": "Legal, security, social services"},
]


def all_classes() -> list[dict]:
    return NICE_CLASSES
