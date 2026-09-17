"""Seed data for Hallo Magic Pizza – imported from the current public menu (read-only reference).
Prices/products are TEST DATA and fully editable from the admin panel."""

IMG = {
    "pizza": "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=900&q=80",
    "pizza2": "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?w=900&q=80",
    "pizza3": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=900&q=80",
    "pizza4": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=900&q=80",
    "pizza5": "https://images.unsplash.com/photo-1571407970349-bc81e7e96d47?w=900&q=80",
    "pizza6": "https://images.unsplash.com/photo-1593560708920-61dd98c46a4e?w=900&q=80",
    "pizza7": "https://images.unsplash.com/photo-1628840042765-356cda07504e?w=900&q=80",
    "pizza8": "https://images.unsplash.com/photo-1595854341625-f33ee10dbf94?w=900&q=80",
    "calzone": "https://images.unsplash.com/photo-1536964549204-cce9eab227bd?w=900&q=80",
    "custom": "https://images.unsplash.com/photo-1542282811-943ef5a99893?w=900&q=80",
    "piadina": "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=900&q=80",
    "pasta": "https://images.unsplash.com/photo-1498579150354-977475b7ea0b?w=900&q=80",
    "ravioli": "https://images.unsplash.com/photo-1587740908075-9e245070dfaa?w=900&q=80",
    "lasagne": "https://images.unsplash.com/photo-1574894709920-11b28e7367e3?w=900&q=80",
    "soda": "https://images.unsplash.com/photo-1554866585-cd94860890b7?w=900&q=80",
    "water": "https://images.unsplash.com/photo-1523362628745-0c100150b504?w=900&q=80",
    "beer": "https://images.unsplash.com/photo-1608270586620-248524c67de9?w=900&q=80",
    "redwine": "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=900&q=80",
    "tiramisu": "https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=900&q=80",
    "profiteroles": "https://images.unsplash.com/photo-1587668178277-295251f900ce?w=900&q=80",
    "brownie": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=900&q=80",
    "cheesecake": "https://images.unsplash.com/photo-1524351199678-941a58a3df50?w=900&q=80",
    "icetea": "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=900&q=80",
}

ING_DE = {
    "tomate": "Tomaten", "mozzarella": "Mozzarella", "origan": "Oregano", "basilic frais": "frisches Basilikum",
    "anchois": "Sardellen", "câpres": "Kapern", "olives noires": "schwarze Oliven", "jambon": "Schinken",
    "champignons": "Champignons", "ananas": "Ananas", "olives": "Oliven", "oignons": "Zwiebeln",
    "salami piquant": "scharfe Salami", "lard": "Speck", "oeuf": "Ei", "gorgonzola": "Gorgonzola",
    "fromage": "Käse", "Grana Padano": "Grana Padano", "poivrons": "Peperoni", "merguez": "Merguez",
    "aubergines": "Auberginen", "courgettes": "Zucchetti", "thon": "Thunfisch", "ail": "Knoblauch",
    "fruits de mer": "Meeresfrüchte", "morilles": "Morcheln", "huile de truffe": "Trüffelöl", "rucola": "Rucola",
    "jambon de Parme": "Parmaschinken", "mozzarella di bufala": "Büffelmozzarella", "tomates cherry": "Cherrytomaten",
    "poulet": "Poulet", "curry": "Curry", "fromage de chèvre": "Ziegenkäse", "miel": "Honig", "saumon": "Lachs",
    "aneth": "Dill", "bresaola": "Bresaola", "crevettes": "Crevetten", "mascarpone": "Mascarpone",
}


def ing(fr_list):
    return [{"id": fr.lower().replace(" ", "_"), "fr": fr, "de": ING_DE.get(fr, fr)} for fr in fr_list]


CATEGORIES = [
    {"slug": "pizza", "name": {"fr": "Pizza", "de": "Pizza"}, "sort": 1, "image_url": IMG["pizza"]},
    {"slug": "pizza-sans-gluten", "name": {"fr": "Pizza sans gluten", "de": "Glutenfreie Pizza"}, "sort": 2, "image_url": IMG["pizza6"], "filter": "gluten_free"},
    {"slug": "creer-votre-pizza", "name": {"fr": "Créer votre pizza", "de": "Eigene Pizza kreieren"}, "sort": 3, "image_url": IMG["custom"]},
    {"slug": "piadina-pasta", "name": {"fr": "Piadina & Pasta", "de": "Piadina & Pasta"}, "sort": 4, "image_url": IMG["pasta"]},
    {"slug": "dessert", "name": {"fr": "Dessert", "de": "Dessert"}, "sort": 5, "image_url": IMG["tiramisu"]},
    {"slug": "boissons", "name": {"fr": "Boissons", "de": "Getränke"}, "sort": 6, "image_url": IMG["soda"]},
]

# key, fr, de, price, max_qty  (from "Créer votre pizza" on the current menu)
EXTRAS = [
    ("jambon_epaule", "Jambon d'épaule", "Schulterschinken", 2.0, 2),
    ("courgettes", "Courgettes", "Zucchetti", 2.0, 1),
    ("champignons", "Champignons", "Champignons", 2.0, 2),
    ("anchois", "Anchois", "Sardellen", 2.0, 1),
    ("ail", "Ail", "Knoblauch", 2.0, 1),
    ("salami_piquant", "Salami piquant", "Scharfe Salami", 2.0, 2),
    ("salami_milano", "Salami Milano", "Salami Milano", 2.0, 2),
    ("thon", "Thon", "Thunfisch", 2.0, 1),
    ("lard", "Lard", "Speck", 3.0, 2),
    ("merguez", "Merguez", "Merguez", 3.0, 2),
    ("oignons", "Oignons", "Zwiebeln", 2.0, 1),
    ("poivrons", "Poivrons", "Peperoni", 2.0, 1),
    ("olives_noires", "Olives noires", "Schwarze Oliven", 2.0, 1),
    ("ananas", "Ananas frais", "Frische Ananas", 2.0, 1),
    ("rucola", "Rucola", "Rucola", 2.0, 1),
    ("gorgonzola", "Gorgonzola", "Gorgonzola", 2.0, 1),
    ("basilic", "Basilic frais", "Frisches Basilikum", 2.0, 1),
    ("aubergines", "Aubergines", "Auberginen", 2.0, 1),
    ("bresaola", "Boeuf séché bresaola", "Bresaola (Trockenfleisch)", 6.0, 1),
    ("oeufs", "Oeufs", "Eier", 2.0, 2),
    ("capres", "Câpres", "Kapern", 2.0, 1),
    ("chevre", "Fromage de chèvre", "Ziegenkäse", 3.0, 1),
    ("parme", "Jambon de Parme", "Parmaschinken", 4.0, 1),
    ("saumon", "Saumon", "Lachs", 7.0, 1),
    ("crevettes", "Crevettes", "Crevetten", 5.0, 1),
    ("mozzarella_extra", "Mozzarella extra", "Extra Mozzarella", 2.0, 2),
    ("bufala", "Mozzarella di bufala", "Büffelmozzarella", 4.0, 1),
    ("burrata", "Burrata", "Burrata", 5.0, 1),
    ("grana", "Grana Padano", "Grana Padano", 2.0, 1),
]
ALL_EXTRA_IDS = [e[0] for e in EXTRAS]

SIZES = lambda p32, p40, p50: [  # noqa: E731
    {"key": "32", "label": "32cm", "price": p32},
    {"key": "40", "label": "40cm", "price": p40},
    {"key": "50", "label": "50cm", "price": p50},
]

DOUGH_OPTIONS = [
    {"key": "classic", "group": "dough", "name": {"fr": "Pâte classique", "de": "Klassischer Teig"}, "price": 0.0, "price_by_size": {}, "only_sizes": [], "default": True},
    {"key": "gluten_free", "group": "dough", "name": {"fr": "Pâte sans gluten", "de": "Glutenfreier Teig"}, "price": 4.0, "price_by_size": {}, "only_sizes": ["32"], "default": False},
]
LACTOSE_OPTION = {"key": "lactose_free", "group": "extra_option", "name": {"fr": "Sans lactose", "de": "Laktosefrei"}, "price": 4.0, "price_by_size": {"32": 4.0, "40": 7.0, "50": 10.0}, "only_sizes": [], "default": False}

BASE = ["tomate", "mozzarella", "origan"]


def pizza(name, extra_ings, sizes, img, desc_fr=None, desc_de=None, gluten_free=True, cat="pizza", base=True):
    ings = (BASE if base else []) + extra_ings
    ings_de = [ING_DE.get(i, i) for i in ings]
    options = ([o for o in DOUGH_OPTIONS if gluten_free or o["key"] == "classic"]) + [LACTOSE_OPTION]
    return {
        "category_slug": cat,
        "name": {"fr": name, "de": name},
        "description": {"fr": desc_fr or ", ".join(ings).capitalize(), "de": desc_de or ", ".join(ings_de)},
        "price": sizes[0]["price"] if sizes else 0,
        "sizes": sizes,
        "options": options,
        "image_url": img,
        "ingredients": ing(ings),
        "allowed_extra_ids": ALL_EXTRA_IDS,
        "customizable": True,
        "allergens": {"fr": "Contient: lait (lactose), gluten (blé)", "de": "Enthält: Milch (Laktose), Gluten (Weizen)"},
        "available": True,
        "is_alcohol": False,
    }


def simple(name_fr, name_de, desc_fr, desc_de, price, img, cat, is_alcohol=False, wine=None, allergens=None):
    return {
        "category_slug": cat,
        "name": {"fr": name_fr, "de": name_de},
        "description": {"fr": desc_fr, "de": desc_de},
        "price": price,
        "sizes": [],
        "options": [],
        "image_url": img,
        "ingredients": [],
        "allowed_extra_ids": [],
        "customizable": False,
        "allergens": allergens or {"fr": "Allergènes: sur demande", "de": "Allergene: auf Anfrage"},
        "available": True,
        "is_alcohol": is_alcohol,
        "wine": wine,
    }


PRODUCTS = [
    # ---- PIZZA (32 / 40 / 50 cm) ----
    pizza("Margherita", ["basilic frais"], SIZES(14, 22, 31), IMG["pizza"]),
    pizza("Napoletana", ["anchois", "câpres", "olives noires"], SIZES(16, 25, 35), IMG["pizza2"]),
    pizza("Prosciutto", ["jambon"], SIZES(17, 26, 36), IMG["pizza3"]),
    pizza("Prosciutto e Funghi", ["jambon", "champignons"], SIZES(18, 29, 40), IMG["pizza4"]),
    pizza("Hawaiana", ["jambon", "ananas"], SIZES(18, 29, 40), IMG["pizza5"]),
    pizza("Diavola", ["olives", "oignons", "salami piquant"], SIZES(18, 31, 40), IMG["pizza6"]),
    pizza("Calabrese", ["champignons", "lard", "oeuf"], SIZES(18, 29, 40), IMG["pizza7"]),
    pizza("Quattro Formaggi", ["gorgonzola", "fromage", "Grana Padano"], SIZES(18, 29, 40), IMG["pizza8"]),
    pizza("Quattro Stagioni", ["jambon", "olives", "champignons", "poivrons"], SIZES(18, 30, 41), IMG["pizza"]),
    pizza("Vulcano", ["merguez", "poivrons", "champignons", "oignons"], SIZES(18, 30, 41), IMG["pizza2"]),
    pizza("Fitness", ["aubergines", "courgettes", "poivrons"], SIZES(18, 30, 41), IMG["pizza3"]),
    pizza("Adriatica", ["thon", "olives", "oignons"], SIZES(18, 30, 41), IMG["pizza4"]),
    pizza("Atlantica", ["ail", "olives noires", "fruits de mer"], SIZES(20, 31, 41), IMG["pizza5"]),
    pizza("Forestière", ["champignons", "lard", "oignons", "oeuf"], SIZES(18, 32, 46), IMG["pizza6"]),
    pizza("Parma", ["jambon de Parme", "rucola", "Grana Padano"], SIZES(18, 32, 46), IMG["pizza7"]),
    pizza("Mediterranea", ["aubergines", "courgettes", "poivrons", "olives", "ail", "rucola"], SIZES(20, 33, 45), IMG["pizza8"]),
    pizza("Tropicale", ["poulet", "curry", "ananas", "poivrons"], SIZES(20, 34, 47), IMG["pizza"]),
    pizza("Bergère", ["fromage de chèvre", "miel", "tomates cherry", "basilic frais"], SIZES(20, 34, 47), IMG["pizza2"]),
    pizza("La Cabriolle", ["fromage de chèvre", "lard", "oignons", "miel"], SIZES(22, 35, 48), IMG["pizza3"]),
    pizza("Mélina", ["morilles", "fromage", "Grana Padano", "huile de truffe", "rucola"], SIZES(23, 36, 50), IMG["pizza4"],
          "Notre création premium: morilles, fromage, Grana Padano, huile de truffe et rucola",
          "Unsere Premium-Kreation: Morcheln, Käse, Grana Padano, Trüffelöl und Rucola"),
    pizza("Nina Ricci", ["jambon de Parme", "mozzarella di bufala", "rucola", "tomates cherry", "Grana Padano", "huile de truffe"], SIZES(23, 36, 50), IMG["pizza5"],
          "Jambon de Parme, mozzarella di bufala, rucola, tomates cherry, Grana Padano et huile de truffe",
          "Parmaschinken, Büffelmozzarella, Rucola, Cherrytomaten, Grana Padano und Trüffelöl"),
    pizza("Gianni Versace", ["bresaola", "rucola", "Grana Padano", "tomates cherry"], SIZES(23, 36, 50), IMG["pizza6"]),
    pizza("Salmone", ["saumon", "aneth", "oignons", "câpres", "tomates cherry"], SIZES(24, 40, 55), IMG["pizza7"]),
    pizza("Pizza de saison", ["mozzarella di bufala", "jambon de Parme", "rucola", "tomates cherry"], SIZES(23, 36, 50), IMG["pizza8"],
          "La création du moment de notre pizzaiolo – demandez-nous!", "Die aktuelle Kreation unseres Pizzaiolo – fragen Sie uns!"),
    pizza("Calzone", ["oeuf", "champignons", "jambon"], [], IMG["calzone"],
          "Pizza fermée – tomate, mozzarella, origan, oeuf, champignons, jambon",
          "Gefaltete Pizza – Tomaten, Mozzarella, Oregano, Ei, Champignons, Schinken", gluten_free=False) | {"price": 18.0},
    pizza("Mickey – pizza pour enfant", ["jambon"], [{"key": "26", "label": "26cm", "price": 10.0}], IMG["pizza"],
          "Petite pizza pour les enfants: tomate, mozzarella, jambon", "Kleine Pizza für Kinder: Tomaten, Mozzarella, Schinken"),
    # ---- CRÉER VOTRE PIZZA ----
    pizza("Créer votre pizza", [], SIZES(14, 27, 33), IMG["custom"],
          "Base tomate, mozzarella, origan. Composez votre pizza avec les ingrédients de votre choix.",
          "Basis Tomaten, Mozzarella, Oregano. Stellen Sie Ihre Pizza mit Ihren Lieblingszutaten zusammen.", cat="creer-votre-pizza"),
    # ---- PIADINA & PASTA ----
    simple("Piadina Bresaola", "Piadina Bresaola", "Bresaola, rucola, Grana Padano, tomates", "Bresaola, Rucola, Grana Padano, Tomaten", 15, IMG["piadina"], "piadina-pasta"),
    simple("Piadina Parma", "Piadina Parma", "Jambon de Parme, mozzarella, rucola, tomates", "Parmaschinken, Mozzarella, Rucola, Tomaten", 15, IMG["piadina"], "piadina-pasta"),
    simple("Piadina Thona", "Piadina Thona", "Thon, mozzarella, oignons, salade", "Thunfisch, Mozzarella, Zwiebeln, Salat", 15, IMG["piadina"], "piadina-pasta"),
    simple("Piadina végétarienne", "Piadina vegetarisch", "Légumes grillés, mozzarella, rucola", "Grilliertes Gemüse, Mozzarella, Rucola", 14, IMG["piadina"], "piadina-pasta"),
    simple("Lasagne", "Lasagne", "Lasagne traditionnelle à la bolognaise", "Traditionelle Lasagne mit Bolognese", 18, IMG["lasagne"], "piadina-pasta"),
    simple("Lasagne aux légumes", "Gemüse-Lasagne", "Lasagne gratinée aux légumes du marché", "Überbackene Lasagne mit Marktgemüse", 19, IMG["lasagne"], "piadina-pasta"),
    simple("Ravioli tomate datterino & basilic", "Ravioli Datteltomaten & Basilikum", "Ravioli à la tomate datterino et au basilic", "Ravioli mit Datteltomaten und Basilikum", 19, IMG["ravioli"], "piadina-pasta"),
    simple("Gratin d'aubergines parmigiana", "Auberginen-Parmigiana", "Gratin d'aubergines, tomate, mozzarella, parmesan", "Auberginen-Gratin mit Tomaten, Mozzarella, Parmesan", 18, IMG["pasta"], "piadina-pasta"),
    # ---- DESSERT ----
    simple("Tiramisu", "Tiramisu", "Le classique italien fait maison", "Der hausgemachte italienische Klassiker", 8.0, IMG["tiramisu"], "dessert"),
    simple("Profiteroles", "Profiteroles", "Choux garnis de crème, sauce chocolat", "Windbeutel mit Rahm und Schokoladensauce", 8.5, IMG["profiteroles"], "dessert"),
    simple("Cheesecake caramel", "Cheesecake Caramel", "Cheesecake onctueux au caramel", "Cremiger Cheesecake mit Caramel", 8.0, IMG["cheesecake"], "dessert"),
    simple("Mousse café sur brownie sans gluten", "Kaffeemousse auf glutenfreiem Brownie", "Mousse au café sur brownie sans gluten", "Kaffeemousse auf glutenfreiem Brownie", 9.0, IMG["brownie"], "dessert",
           allergens={"fr": "Sans gluten. Contient: oeuf, lait", "de": "Glutenfrei. Enthält: Ei, Milch"}),
    # ---- BOISSONS ----
    simple("Coca-Cola", "Coca-Cola", "PET 50cl", "PET 50cl", 3.5, IMG["soda"], "boissons"),
    simple("Coca-Cola Zero", "Coca-Cola Zero", "PET 50cl", "PET 50cl", 3.5, IMG["soda"], "boissons"),
    simple("Fanta", "Fanta", "PET 50cl", "PET 50cl", 3.5, IMG["soda"], "boissons"),
    simple("Sprite", "Sprite", "PET 50cl", "PET 50cl", 3.5, IMG["soda"], "boissons"),
    simple("Rivella bleu", "Rivella blau", "PET 50cl", "PET 50cl", 3.5, IMG["soda"], "boissons"),
    simple("Rivella rouge", "Rivella rot", "PET 50cl", "PET 50cl", 3.5, IMG["soda"], "boissons"),
    simple("Thé froid citron", "Eistee Zitrone", "PET 50cl", "PET 50cl", 3.5, IMG["icetea"], "boissons"),
    simple("Thé froid pêche", "Eistee Pfirsich", "PET 50cl", "PET 50cl", 3.5, IMG["icetea"], "boissons"),
    simple("Eau gazeuse", "Mineralwasser mit Kohlensäure", "PET 50cl", "PET 50cl", 3.5, IMG["water"], "boissons"),
    simple("Eau non gazeuse", "Mineralwasser ohne Kohlensäure", "PET 50cl", "PET 50cl", 3.5, IMG["water"], "boissons"),
    simple("Red Bull", "Red Bull", "Canette 25cl", "Dose 25cl", 4.5, IMG["soda"], "boissons"),
    simple("Bière Heineken", "Bier Heineken", "Bouteille 33cl", "Flasche 33cl", 3.5, IMG["beer"], "boissons", True),
    simple("Bière Moretti", "Bier Moretti", "Bouteille 33cl", "Flasche 33cl", 3.5, IMG["beer"], "boissons", True),
    simple("Nero d'Avola", "Nero d'Avola", "Vin rouge – Sicile", "Rotwein – Sizilien", 18, IMG["redwine"], "boissons", True,
           {"type": "rouge", "origin": "Sicile, Italie", "bottle_size": "75cl"}),
    simple("Primitivo del Salento", "Primitivo del Salento", "Vin rouge – Puglia", "Rotwein – Apulien", 18, IMG["redwine"], "boissons", True,
           {"type": "rouge", "origin": "Puglia, Italie", "bottle_size": "75cl"}),
]

# Delivery zones + minimum order per zone (from the current public website)
ZONES = [
    (25, [("1723", "Marly")]),
    (30, [("1700", "Fribourg"), ("1724", "Le Mouret"), ("1731", "Épendes")]),
    (35, [("1732", "Arconciel"), ("1734", "Giffers / Tentlingen"), ("1735", "Giffers")]),
    (40, [("1725", "Posieux"), ("1727", "Corpataux"), ("1736", "St. Silvester"), ("1722", "Bourguillon")]),
    (45, [("1717", "St. Ursen"), ("1718", "St. Ursen")]),
    (50, [("1730", "Ecuvillens"), ("1753", "Matran")]),
    (55, [("1733", "Treyvaux")]),
    (60, [("1634", "La Roche"), ("1752", "Villars-sur-Glâne")]),
    (65, [("1728", "Rossens"), ("1737", "Plasselb")]),
    (70, [("1726", "Farvagny")]),
]

DEFAULT_SETTINGS = {
    "restaurant_name": "Hallo Magic Pizza",
    "business_name": "Hallo Magic Pizza",
    "street": "Route de Chésalles 19",
    "postal_code": "1723",
    "city": "Marly",
    "vat_number": "CHE-156.631.035 TVA",
    "vat_rate_standard": 2.6,
    "vat_rate_alcohol": 8.1,
    "delivery_fee_vat_rate": 2.6,
    "phone": "026 430 00 96",
    "address": "Route de Chésalles 19, 1723 Marly",
    "opening_hours": {  # "" = closed; last delivery order 15 min before each closing (delivery_cutoff_minutes)
        "mon": "", "tue": "17:00-22:00", "wed": "11:00-14:00, 17:00-22:00", "thu": "11:00-14:00, 17:00-22:00",
        "fri": "11:00-14:00, 17:00-22:00", "sat": "11:00-14:00, 17:00-22:00", "sun": "11:00-14:00, 17:00-22:00",
    },
    "delivery_cutoff_minutes": 15,
    "first_delivery": {"lunch": "", "evening": ""},
    "temporarily_closed": False,
    "closed_message": {"fr": "Nous sommes temporairement fermés.", "de": "Wir sind vorübergehend geschlossen."},
    "delivery_enabled": True,
    "pickup_enabled": True,
    "minimum_order": 25.0,
    "delivery_fee": 0.0,
    "free_delivery_from": None,
    "delivery_zones": [{"npa": npa, "city": city, "minimum_order": float(m)} for m, zs in ZONES for npa, city in zs],
}
