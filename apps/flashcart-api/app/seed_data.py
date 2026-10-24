"""Deterministic demo catalog + original SVG product illustrations (no third-party images or brands).

`python -m app.seed --write-svgs ../flashcart-web/public/products` regenerates the artwork.
"""

import random
import re

PALETTE = {
    "black": "#1f2328", "white": "#e9ecef", "red": "#d64545", "blue": "#2f6fdb",
    "orange": "#e8833a", "green": "#2e9e6b", "grey": "#8a94a3",
}
LOCATIONS = ["Bengaluru", "Chennai", "Mumbai", "Delhi", "Hyderabad", "Pune", "Kochi", "Jaipur", "Kolkata"]

# (name, brand, category, kind, price_rupees, colors)
CATALOG: list[tuple[str, str, str, str, int, list[str]]] = [
    ("Mechanical Keyboard K75", "Keystone", "Electronics", "keyboard", 7499, ["black", "grey"]),
    ("Low-Profile Keyboard Air", "Keystone", "Electronics", "keyboard", 5299, ["white", "grey"]),
    ("Ultra-Light Gaming Mouse", "Swiftpoint", "Electronics", "mouse", 2699, ["black", "white"]),
    ("Ergonomic Vertical Mouse", "Swiftpoint", "Electronics", "mouse", 3499, ["black"]),
    ("Wireless Over-Ear Headphones", "Auralis", "Electronics", "headphones", 8999, ["black", "grey"]),
    ("Studio Monitor Headphones", "Auralis", "Electronics", "headphones", 6499, ["black"]),
    ("Kids Safe Headphones", "Auralis", "Electronics", "headphones", 1499, ["blue", "red"]),
    ("Multi-Platform Game Controller", "Pixelforge", "Electronics", "controller", 3999, ["black", "white"]),
    ("Retro Pad Controller", "Pixelforge", "Electronics", "controller", 1799, ["red", "grey"]),
    ("Premium Coiled USB-C Cable", "Linkwell", "Electronics", "cable", 1299, ["black", "orange"]),
    ("Braided Charging Cable 2m", "Linkwell", "Electronics", "cable", 599, ["blue", "black"]),
    ("Compact USB-C Adapter", "Linkwell", "Electronics", "usb", 899, ["black", "grey"]),
    ("64GB USB Flash Drive", "Linkwell", "Electronics", "usb", 749, ["grey", "blue"]),
    ("Protective Travel Case", "Carrylab", "Electronics", "case", 1199, ["black", "grey"]),
    ("Hard Shell Gadget Case", "Carrylab", "Electronics", "case", 1599, ["blue", "black"]),
    ("Smart Fitness Watch", "Pulse", "Electronics", "watch", 4999, ["black", "white", "orange"]),
    ("Classic Analog Watch", "Pulse", "Electronics", "watch", 3299, ["grey", "black"]),
    ("True Wireless Earbuds", "Auralis", "Electronics", "earbuds", 2999, ["white", "black"]),
    ("Sport Earbuds Pro", "Auralis", "Electronics", "earbuds", 3999, ["black", "green"]),
    ("Portable Bluetooth Speaker", "Boomwave", "Electronics", "speaker", 2499, ["blue", "red", "black"]),
    ("Home Smart Speaker", "Boomwave", "Electronics", "speaker", 4499, ["grey", "white"]),
    ("Cotton Crew T-Shirt", "Threadly", "Fashion", "tshirt", 599, ["white", "black", "blue"]),
    ("Oversized Graphic Tee", "Threadly", "Fashion", "tshirt", 799, ["orange", "green"]),
    ("Running Sneakers", "Stride", "Fashion", "sneaker", 3499, ["white", "red"]),
    ("Everyday Canvas Shoes", "Stride", "Fashion", "sneaker", 1899, ["blue", "black"]),
    ("Commuter Backpack 25L", "Carrylab", "Fashion", "backpack", 2299, ["black", "grey"]),
    ("Trekking Backpack 40L", "Carrylab", "Fashion", "backpack", 3999, ["green", "orange"]),
    ("Water-Resistant Jacket", "Northtrail", "Fashion", "jacket", 3799, ["blue", "black"]),
    ("Light Puffer Jacket", "Northtrail", "Fashion", "jacket", 4599, ["red", "grey"]),
    ("Baseball Cap", "Threadly", "Fashion", "cap", 499, ["black", "red", "blue"]),
    ("Wool Beanie", "Northtrail", "Fashion", "cap", 699, ["grey", "orange"]),
    ("Leather Belt", "Threadly", "Fashion", "belt", 899, ["black"]),
    ("Aviator Sunglasses", "Solis", "Fashion", "sunglasses", 1299, ["black", "orange"]),
    ("Round Sunglasses", "Solis", "Fashion", "sunglasses", 1099, ["grey"]),
    ("Single-Origin Coffee Beans 500g", "Hillbrew", "Foods", "coffee", 649, ["orange"]),
    ("Filter Coffee Powder 250g", "Hillbrew", "Foods", "coffee", 299, ["red"]),
    ("Assam Black Tea 250g", "Leafline", "Foods", "tea", 249, ["green"]),
    ("Masala Chai Blend 200g", "Leafline", "Foods", "tea", 279, ["orange"]),
    ("Dark Chocolate 70% Bar", "Cocoa Co", "Foods", "chocolate", 199, ["black"]),
    ("Almond Milk Chocolate Bar", "Cocoa Co", "Foods", "chocolate", 179, ["orange"]),
    ("Wild Forest Honey 500g", "Beehive", "Foods", "honey", 449, ["orange"]),
    ("Raw Multiflora Honey 250g", "Beehive", "Foods", "honey", 259, ["orange"]),
    ("Roasted Almonds 500g", "Nutfield", "Foods", "jar", 699, ["orange"]),
    ("Mixed Dry Fruits 1kg", "Nutfield", "Foods", "jar", 1199, ["red"]),
    ("Cold-Pressed Coconut Oil 1L", "Kerala Gold", "Foods", "bottle", 399, ["green"]),
    ("Extra Virgin Olive Oil 500ml", "Oliva", "Foods", "bottle", 749, ["green"]),
    ("Ergonomic Office Chair", "Sitwell", "Furniture", "chair", 12999, ["black", "grey"]),
    ("Mesh Task Chair", "Sitwell", "Furniture", "chair", 7999, ["blue", "black"]),
    ("Standing Desk 120cm", "Worknest", "Furniture", "desk", 21999, ["white", "black"]),
    ("Compact Study Desk", "Worknest", "Furniture", "desk", 6999, ["grey"]),
    ("LED Desk Lamp", "Lumen", "Furniture", "lamp", 1899, ["white", "black"]),
    ("Arc Floor Lamp", "Lumen", "Furniture", "lamp", 4599, ["orange", "black"]),
    ("5-Tier Bookshelf", "Worknest", "Furniture", "shelf", 5499, ["white", "grey"]),
    ("Wall Floating Shelf Set", "Worknest", "Furniture", "shelf", 1799, ["black"]),
    ("Two-Seater Sofa", "Cozyhome", "Furniture", "sofa", 24999, ["grey", "blue"]),
    ("Accent Lounge Chair", "Cozyhome", "Furniture", "sofa", 11999, ["green", "orange"]),
    ("Bedside Table", "Cozyhome", "Furniture", "table", 3299, ["white"]),
    ("Round Coffee Table", "Cozyhome", "Furniture", "table", 5999, ["black"]),
    ("Cordless Drill 18V", "Forgeline", "Tools", "drill", 5999, ["orange", "black"]),
    ("Compact Impact Driver", "Forgeline", "Tools", "drill", 7499, ["blue"]),
    ("Claw Hammer 16oz", "Forgeline", "Tools", "hammer", 699, ["red", "black"]),
    ("Rubber Mallet", "Forgeline", "Tools", "hammer", 449, ["black"]),
    ("Combination Wrench Set", "Torq", "Tools", "wrench", 1899, ["grey"]),
    ("Adjustable Wrench 10in", "Torq", "Tools", "wrench", 799, ["grey", "red"]),
    ("Precision Screwdriver Kit", "Torq", "Tools", "screwdriver", 999, ["orange", "black"]),
    ("Insulated Screwdriver Set", "Torq", "Tools", "screwdriver", 1299, ["red"]),
    ("Measuring Tape 5m", "Measurely", "Tools", "tape", 349, ["orange"]),
    ("Laser Distance Meter", "Measurely", "Tools", "tape", 2799, ["green"]),
    ("Tool Box 19in", "Forgeline", "Tools", "toolbox", 1699, ["red", "black"]),
    ("Rolling Tool Chest", "Forgeline", "Tools", "toolbox", 8999, ["red"]),
    ("Safety Gloves Pack", "Guardwell", "Tools", "gloves", 399, ["orange", "grey"]),
    ("Cut-Resistant Gloves", "Guardwell", "Tools", "gloves", 599, ["grey"]),
    ("Gaming Headset with Mic", "Pixelforge", "Electronics", "headphones", 3499, ["black", "red"]),
    ("Wireless Charging Pad", "Linkwell", "Electronics", "usb", 1499, ["white", "black"]),
    ("Noise-Cancelling Earbuds", "Auralis", "Electronics", "earbuds", 6999, ["black", "white"]),
    ("Linen Casual Shirt", "Threadly", "Fashion", "tshirt", 1499, ["white", "blue"]),
    ("Trail Running Shoes", "Stride", "Fashion", "sneaker", 4299, ["orange", "grey"]),
    ("Herbal Green Tea 100 bags", "Leafline", "Foods", "tea", 399, ["green"]),
    ("Kids Study Chair", "Sitwell", "Furniture", "chair", 2999, ["blue", "red"]),
    ("Digital Multimeter", "Measurely", "Tools", "tape", 1499, ["orange", "black"]),
]

SHIPPING_SETS = [["regular", "economic"], ["regular", "next_day"], ["regular", "economic", "instant"], ["regular"]]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build_products(seed: int = 42) -> list[dict]:
    # Deterministic demo data, not security-sensitive, so a non-cryptographic PRNG is correct here.
    rng = random.Random(seed)  # noqa: S311  # nosec B311
    products = []
    for i, (name, brand, category, kind, rupees, colors) in enumerate(CATALOG, start=1):
        sku = f"FC-{category[:3].upper()}-{i:04d}"
        image = f"/products/{kind}-{colors[0]}.svg"
        products.append({
            "sku": sku,
            "slug": f"{slugify(name)}-{sku.lower()}",
            "name": name,
            "brand": brand,
            "category": category,
            "kind": kind,
            "description": f"{name} by {brand}. A dependable {kind} chosen for everyday use, "
                           f"backed by a 7-day return policy and FlashCart quality checks.",
            "price_paise": rupees * 100,
            "images": [image] + [f"/products/{kind}-{c}.svg" for c in colors[1:2]],
            "colors": colors,
            "shipping": rng.choice(SHIPPING_SETS),
            "rating": round(rng.uniform(3.2, 5.0), 1),
            "review_count": rng.choice([1, 3, 9, 10, 37, 131, 150, 412, 1024]),
            "sold_count": rng.randint(0, 1500),
            "stock": rng.choice([0, 3, 8, 25, 60, 120, 250]),
            "location": rng.choice(LOCATIONS),
            "active": True,
            "version": 1,
        })
    return products


# ---------------- SVG illustrations ----------------
def _shade(hex_color: str, factor: float) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    clamp = lambda v: max(0, min(255, int(v)))  # noqa: E731
    return f"#{clamp(r * factor):02x}{clamp(g * factor):02x}{clamp(b * factor):02x}"


def _shapes(kind: str, c: str, d: str, l: str) -> str:  # noqa: E741 - c=color d=dark l=light
    s = {
        "keyboard": f'<rect x="60" y="105" width="280" height="95" rx="12" fill="{d}"/>'
                    + "".join(f'<rect x="{74 + col * 26}" y="{117 + row * 22}" width="20" height="16" rx="3" fill="{l}"/>'
                              for row in range(3) for col in range(10))
                    + f'<rect x="120" y="183" width="160" height="10" rx="3" fill="{l}"/>',
        "mouse": f'<ellipse cx="200" cy="155" rx="62" ry="92" fill="{c}"/><line x1="200" y1="70" x2="200" y2="135" '
                 f'stroke="{d}" stroke-width="4"/><rect x="194" y="92" width="12" height="26" rx="6" fill="{l}"/>',
        "headphones": f'<path d="M110 175 Q110 70 200 70 Q290 70 290 175" fill="none" stroke="{c}" stroke-width="16"/>'
                      f'<rect x="88" y="160" width="46" height="72" rx="18" fill="{d}"/>'
                      f'<rect x="266" y="160" width="46" height="72" rx="18" fill="{d}"/>',
        "controller": f'<path d="M95 130 Q110 95 160 100 L240 100 Q290 95 305 130 L325 205 Q330 235 300 232 '
                      f'L265 195 L135 195 L100 232 Q70 235 75 205 Z" fill="{c}"/>'
                      f'<rect x="125" y="135" width="36" height="10" rx="3" fill="{l}"/><rect x="138" y="122" width="10" '
                      f'height="36" rx="3" fill="{l}"/><circle cx="255" cy="130" r="7" fill="{l}"/><circle cx="272" '
                      f'cy="147" r="7" fill="{l}"/><circle cx="238" cy="147" r="7" fill="{l}"/>',
        "cable": f'<path d="M120 70 L120 120" stroke="{d}" stroke-width="10"/><path d="M120 120 '
                 + " ".join(f"Q{150 + (k % 2) * 40} {130 + k * 12} 120 {136 + k * 12}" for k in range(6))
                 + f'" fill="none" stroke="{c}" stroke-width="8"/><rect x="108" y="52" width="24" height="26" rx="4" '
                 f'fill="{l}"/><path d="M120 208 Q220 250 280 200 L280 120" fill="none" stroke="{c}" stroke-width="8"/>'
                 f'<rect x="268" y="96" width="24" height="28" rx="4" fill="{l}"/>',
        "usb": f'<rect x="170" y="60" width="60" height="70" rx="6" fill="{l}"/><rect x="183" y="80" width="12" height="12" '
               f'fill="{d}"/><rect x="205" y="80" width="12" height="12" fill="{d}"/><rect x="160" y="125" width="80" '
               f'height="120" rx="14" fill="{c}"/>',
        "case": f'<rect x="80" y="90" width="240" height="140" rx="40" fill="{c}"/>'
                + "".join(f'<circle cx="{110 + col * 30}" cy="{120 + row * 28}" r="9" fill="{d}"/>'
                          for row in range(4) for col in range(7)),
        "watch": f'<rect x="170" y="40" width="60" height="220" rx="14" fill="{c}"/><circle cx="200" cy="150" r="60" '
                 f'fill="{d}"/><circle cx="200" cy="150" r="48" fill="{l}"/><line x1="200" y1="150" x2="200" y2="115" '
                 f'stroke="{d}" stroke-width="5"/><line x1="200" y1="150" x2="226" y2="160" stroke="{d}" stroke-width="4"/>',
        "earbuds": f'<rect x="125" y="160" width="150" height="80" rx="34" fill="{l}"/><circle cx="165" cy="120" r="30" '
                   f'fill="{c}"/><rect x="158" y="130" width="14" height="50" rx="7" fill="{c}"/><circle cx="235" cy="120" '
                   f'r="30" fill="{c}"/><rect x="228" y="130" width="14" height="50" rx="7" fill="{c}"/>',
        "speaker": f'<rect x="110" y="75" width="180" height="160" rx="40" fill="{c}"/><circle cx="200" cy="155" r="50" '
                   f'fill="{d}"/><circle cx="200" cy="155" r="20" fill="{l}"/>',
        "tshirt": f'<path d="M140 70 L170 60 Q200 85 230 60 L260 70 L310 115 L280 145 L260 128 L260 245 L140 245 L140 128 '
                  f'L120 145 L90 115 Z" fill="{c}"/><path d="M170 60 Q200 85 230 60" fill="none" stroke="{d}" stroke-width="5"/>',
        "sneaker": f'<path d="M80 200 L90 130 Q130 125 170 150 L220 160 Q300 165 320 200 Z" fill="{c}"/><rect x="78" '
                   f'y="198" width="246" height="22" rx="10" fill="{l}"/>'
                   + "".join(f'<line x1="{150 + k * 16}" y1="{142 + k * 4}" x2="{162 + k * 16}" y2="{155 + k * 4}" '
                             f'stroke="{l}" stroke-width="4"/>' for k in range(3)),
        "backpack": f'<rect x="130" y="70" width="140" height="180" rx="40" fill="{c}"/><rect x="152" y="165" width="96" '
                    f'height="60" rx="14" fill="{d}"/><path d="M170 72 Q200 40 230 72" fill="none" stroke="{d}" stroke-width="8"/>',
        "jacket": f'<path d="M150 60 L250 60 L320 120 L295 150 L270 130 L270 250 L130 250 L130 130 L105 150 L80 120 Z" '
                  f'fill="{c}"/><line x1="200" y1="62" x2="200" y2="250" stroke="{d}" stroke-width="5"/>'
                  f'<path d="M175 60 L200 95 L225 60" fill="{d}"/>',
        "cap": f'<path d="M110 180 Q110 85 200 85 Q290 85 290 180 Z" fill="{c}"/><path d="M110 180 L330 180 Q330 205 '
               f'280 205 L110 195 Z" fill="{d}"/><circle cx="200" cy="88" r="8" fill="{d}"/>',
        "belt": f'<rect x="60" y="135" width="280" height="34" rx="6" fill="{c}"/><rect x="260" y="122" width="56" height="60" '
                f'rx="6" fill="none" stroke="#c9a227" stroke-width="7"/>',
        "sunglasses": f'<ellipse cx="145" cy="155" rx="55" ry="42" fill="{c}"/><ellipse cx="255" cy="155" rx="55" ry="42" '
                      f'fill="{c}"/><path d="M195 145 Q200 132 205 145" fill="none" stroke="{d}" stroke-width="7"/>',
        "coffee": f'<path d="M140 70 L260 70 L270 250 L130 250 Z" fill="{c}"/><rect x="150" y="120" width="100" height="70" '
                  f'rx="6" fill="{l}"/><ellipse cx="200" cy="155" rx="16" ry="24" fill="{d}"/>',
        "tea": f'<rect x="135" y="70" width="130" height="180" rx="10" fill="{c}"/><path d="M200 110 Q160 150 200 200 Q240 150 '
               f'200 110" fill="{l}"/>',
        "chocolate": f'<rect x="110" y="70" width="180" height="180" rx="8" fill="{c}"/>'
                     + "".join(f'<rect x="{122 + col * 56}" y="{82 + row * 56}" width="44" height="44" rx="4" fill="{d}"/>'
                               for row in range(3) for col in range(3)),
        "honey": f'<rect x="135" y="95" width="130" height="155" rx="30" fill="{c}"/><rect x="150" y="65" width="100" '
                 f'height="34" rx="6" fill="{d}"/><path d="M175 150 l25 -14 l25 14 v28 l-25 14 l-25 -14 z" fill="{l}"/>',
        "jar": f'<rect x="135" y="95" width="130" height="155" rx="22" fill="{l}"/><rect x="145" y="65" width="110" height="34" '
               f'rx="6" fill="{d}"/>' + "".join(f'<ellipse cx="{165 + (k % 4) * 24}" cy="{140 + (k // 4) * 30}" rx="11" ry="8" '
                                                f'fill="{c}"/>' for k in range(12)),
        "bottle": f'<rect x="178" y="45" width="44" height="40" rx="6" fill="{d}"/><path d="M178 85 L150 130 L150 250 L250 250 '
                  f'L250 130 L222 85 Z" fill="{c}"/><rect x="160" y="160" width="80" height="50" rx="6" fill="{l}"/>',
        "chair": f'<rect x="140" y="50" width="120" height="110" rx="20" fill="{c}"/><rect x="125" y="160" width="150" '
                 f'height="30" rx="12" fill="{d}"/><rect x="195" y="190" width="10" height="45" fill="{d}"/><path d="M140 '
                 f'250 L200 232 L260 250" fill="none" stroke="{d}" stroke-width="8"/>',
        "desk": f'<rect x="70" y="110" width="260" height="22" rx="5" fill="{c}"/><rect x="95" y="132" width="14" height="120" '
                f'fill="{d}"/><rect x="291" y="132" width="14" height="120" fill="{d}"/><rect x="230" y="132" width="60" '
                f'height="55" fill="{d}"/>',
        "lamp": f'<path d="M150 70 L250 70 L275 130 L125 130 Z" fill="{c}"/><rect x="194" y="130" width="12" height="100" '
                f'fill="{d}"/><ellipse cx="200" cy="240" rx="55" ry="12" fill="{d}"/>',
        "shelf": f'<rect x="120" y="45" width="160" height="210" fill="none" stroke="{c}" stroke-width="10"/>'
                 + "".join(f'<rect x="120" y="{88 + k * 42}" width="160" height="8" fill="{c}"/>' for k in range(4))
                 + "".join(f'<rect x="{135 + k * 18}" y="{58 + (k % 3) * 2}" width="12" height="{28 - (k % 3) * 2}" '
                           f'fill="{d}"/>' for k in range(5)),
        "sofa": f'<rect x="80" y="110" width="240" height="80" rx="20" fill="{c}"/><rect x="60" y="140" width="50" height="80" '
                f'rx="16" fill="{d}"/><rect x="290" y="140" width="50" height="80" rx="16" fill="{d}"/><rect x="105" y="170" '
                f'width="190" height="40" rx="10" fill="{l}"/>',
        "table": f'<ellipse cx="200" cy="120" rx="120" ry="28" fill="{c}"/><rect x="140" y="130" width="10" height="110" '
                 f'fill="{d}"/><rect x="250" y="130" width="10" height="110" fill="{d}"/>',
        "drill": f'<rect x="110" y="95" width="170" height="60" rx="24" fill="{c}"/><rect x="280" y="113" width="60" height="22" '
                 f'rx="4" fill="#8a94a3"/><path d="M160 150 L200 150 L210 230 L150 230 Z" fill="{d}"/><rect x="140" y="228" '
                 f'width="80" height="24" rx="6" fill="{d}"/>',
        "hammer": f'<rect x="190" y="105" width="22" height="150" rx="8" fill="{c}"/><path d="M120 75 L280 75 L280 115 L150 115 '
                  f'Q120 115 120 95 Z" fill="#6b7280"/>',
        "wrench": f'<rect x="185" y="95" width="30" height="140" rx="10" fill="{c}" transform="rotate(35 200 160)"/>'
                  f'<circle cx="155" cy="95" r="34" fill="{c}"/><circle cx="145" cy="85" r="16" fill="#f3f4f6"/>',
        "screwdriver": f'<rect x="170" y="55" width="60" height="110" rx="22" fill="{c}"/><rect x="192" y="165" width="16" '
                       f'height="80" fill="#8a94a3"/><path d="M192 245 L208 245 L204 262 L196 262 Z" fill="#6b7280"/>',
        "tape": f'<rect x="120" y="85" width="150" height="150" rx="30" fill="{c}"/><circle cx="195" cy="160" r="38" fill="{d}"/>'
                f'<rect x="268" y="205" width="70" height="20" fill="#e5c84a"/>',
        "toolbox": f'<rect x="90" y="120" width="220" height="120" rx="10" fill="{c}"/><rect x="90" y="120" width="220" '
                   f'height="30" fill="{d}"/><path d="M160 120 L160 95 L240 95 L240 120" fill="none" stroke="{d}" '
                   f'stroke-width="10"/><rect x="185" y="140" width="30" height="20" rx="3" fill="{l}"/>',
        "gloves": f'<path d="M140 250 L140 140 Q140 120 155 120 L155 80 Q165 70 175 80 L175 120 L180 70 Q190 60 200 70 L198 '
                  f'120 L210 78 Q220 70 228 80 L222 130 L240 110 Q255 105 255 125 L225 200 L225 250 Z" fill="{c}"/>'
                  f'<rect x="138" y="225" width="90" height="25" fill="{d}"/>',
    }
    return s[kind]


def render_svg(kind: str, color: str) -> str:
    c = PALETTE[color]
    body = _shapes(kind, c, _shade(c, 0.72), _shade(c, 1.45) if color != "white" else "#ffffff")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" role="img" '
        f'aria-label="{kind} illustration"><rect width="400" height="300" fill="#f1f3f4"/>{body}</svg>'
    )


def all_svgs() -> dict[str, str]:
    out = {}
    for *_, kind, _, colors in CATALOG:
        for color in colors:
            out[f"{kind}-{color}.svg"] = render_svg(kind, color)
    return out
