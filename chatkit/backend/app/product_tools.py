from agents import function_tool, RunContextWrapper
from chatkit.agents import AgentContext

# IMPORTANT: Import the knowledge dictionary from your server file 

from .product_widget import build_product_widget, product_widget_copy_text
 



PRODUCT_KNOWLEDGE = {
    "home001": {
        "labels": ["home", "decor", "winter", "christmas", "wreath", "Twig Circle", "Fruit Twig Circle 25cm"],
        "title": "Fruit Twig Circle 25cm",
        "description": (
            "A decorative circular twig wreath adorned with fragrant dried fruits, cinnamon sticks, "
            "pine cones, and scented with Christmas in a Bottle oil. "
            "Designed as a seasonal home decoration for the winter and festive period."
        ),
        "price": 24.97,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/Untitleddesign-2023-12-01T160422.432.png?v=1701446872&width=1780",
        "product_url": "https://www.inspitalfields.co.uk/collections/christmas-sale/products/fruit-twig-circle-25cm"
    },
    "home002": {
        "labels": ["home", "decor", "christmas", "fragrance", "gift", "Fruit Organza Bag","cheap"],
        "title": "Fruit Organza Bag",
        "description": (
            "A decorative organza bag filled with dried fruits and scented with Christmas in the Bottle oil. "
            "Designed to gently fragrance your home when hung near heat sources, creating a warm festive aroma. "
            "Do not hang directly on a heater due to fire risk."
        ),
        "price": 3.32,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/products/organzabag.jpg?v=1634829465&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/christmas-sale/products/fruit-organza-bag-1"
    },
    "home003": {
        "labels": ["home", "fragrance", "christmas", "oil", "bottle", "Christmas in A Bottle Oil 10ml"],
        "title": "Christmas in A Bottle Oil 10ml",
        "description": (
            "A festive fragrance oil blending cinnamon, orange, cloves, and seasonal spices to create the scent of Christmas. "
            "Ideal for adding a warm holiday aroma to your home or enhancing Christmas decorations."
        ),
        "price": 3.32,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/Untitleddesign-2023-12-01T155600.570.png?v=1701446247&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/christmas-sale/products/christmas-in-a-bottle-oil-10ml"
    },
    "home004": {
        "labels": ["home", "decor", "christmas", "eco", "sustainable", "Trees", "Beach Clean Eco Large Christmas Trees"],
        "title": "Beach Clean Eco Large Christmas Trees",
        "description": (
            "Eco-conscious decorative Christmas trees made from Beach Clean material, a mix of cork and recycled EVA plastics. "
            "Each piece is soft to the touch, flexible, and uniquely colored, celebrating sustainable design."
        ),
        "price": 15.30,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/Untitleddesign-2023-10-30T122026.917.png?v=1698668661&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/christmas-sale/products/beach-clean-eco-large-2-christmas-trees"
    },
    "home005": {
        "labels": ["home", "christmas", "decor", "craft", "eco", "Paper Christmas Tree"],
        "title": "Paper Christmas Tree",
        "description": (
            "A mess-free Paper Christmas Tree kit designed for easy folding and assembly with no glue or scissors required. "
            "Made from FSC-certified paper with soy ink printing and plastic-free packaging. "
            "Includes star, ornaments, and miniature presents for festive decorating."
        ),
        "price": 6.12,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/Paper_Christmas_Tree_Kit.png?v=1765541202&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/christmas-sale/products/paper-christmas-tree"
    },
    "home006": {
        "labels": ["home", "lighting", "lamp", "glass", "statement", "Pink Calacatta Pebble Glass Lamp 20cm"],
        "title": "Pink Calacatta Pebble Glass Lamp 20cm",
        "description": (
            "A handcrafted and mouth-blown glass table lamp inspired by pink Calacatta marble patterns. "
            "Its organic design and radiant glow create a striking focal point in any room. "
            "Fitted with a UK three pin plug and designed for a cool white E14 bulb. "
            "Click and collect only due to fragile nature."
        ),
        "price": 163.17,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/PINKPEBBLE4.jpg?v=1745316372&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/furniture-lighting/products/pink-calacatta-pebble-glass-lamp-20cm"
    },
    "home007": {
        "labels": ["home", "vase", "ceramic", "hand-painted", "Odina Hand-Painted Stoneware Green Vase"],
        "title": "Odina Hand-Painted Stoneware Green Vase",
        "description": (
            "A hand-painted stoneware vase with a cream base and green floral detailing. "
            "Each piece is unique and works beautifully as a standalone decorative object or with flowers."
        ),
        "price": 30.58,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/Untitleddesign-2025-02-11T155732.581.png?v=1739289490&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/vases/products/odina-vase-green"
    },
    "home008": {
        "labels": ["home", "photo frame", "decor", "coastal", "Helio Ferretti Menorca Photo Frame"],
        "title": "Helio Ferretti Menorca Photo Frame",
        "description": (
            "A bold and decorative photo frame inspired by Mediterranean style, featuring blue and white pinstripes with red details. "
            "Perfect for displaying treasured memories or gifting."
        ),
        "price": 15.30,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/Helio_Ferretti_Menorca_Photo_Frame.png?v=1765275066&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/photo-frames/products/helio-ferretti-menorca-photo-frame"
    },
    "home009": {
        "labels": ["home", "throw", "textile", "eco", "art", "Moretti Throw", "Moretti Throw"],
        "title": "Moretti Throw",
        "description": (
            "An artist-designed cotton throw by Imogen Sinclair for Slowdown Studio. "
            "Woven in the USA using 100 percent cotton with recycled fibers, offering comfort, sustainability, and versatility. "
            "Suitable as a blanket, wall tapestry, or picnic rug."
        ),
        "price": 249.61,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/Moretti6.jpg?v=1760101710&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/throws-and-rugs/products/moretti-throw"
    },
    "home010": {
        "labels": ["home", "blanket", "kids", "eco", "textile", "Big Cats Mini Blanket"],
        "title": "Big Cats Mini Blanket",
        "description": (
            "A soft and durable mini blanket designed by artist James Daw, featuring a playful big cats illustration. "
            "Made in the USA from a recycled cotton blend, ideal for nurseries, stroller rides, and cozy moments."
        ),
        "price": 152.93,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/BigCats3_108a8fe1-5d1c-402f-99c6-1b8aeec0d107.jpg?v=1760100918&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/throws-and-rugs/products/big-cats-mini-blanket"
    },
    "home011": {
        "labels": ["home", "dining", "plate", "ceramic", "coastal", "Blue Ombre Turbot Plate" "Ocean Dining Collection"],
        "title": "Blue Ombre Turbot Plate",
        "description": (
            "A fish-shaped serving plate finished with a blue ombre glaze inspired by ocean tones. "
            "Suitable for serving seafood, appetizers, or as a decorative dining accent."
        ),
        "price": 25.51,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/Blue_Ombre_Turbot_Plat.png?v=1762875066&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/ocean-dining-collection/products/blue-ombre-turbot-plate"
    },
    "home012": {
        "labels": ["home", "vase", "ceramic", "coastal", "Tace Vase Multi Fish Blue Stoneware Vase", "Ocean Dining Collection"],
        "title": "Tace Vase Multi Fish Blue Stoneware Vase",
        "description": (
            "A blue stoneware vase featuring decorative fish details and a reactive glaze finish. "
            "Each vase is unique, suitable for fresh or dried flowers or as a standalone decorative piece. "
            "Click and collect only due to fragile nature."
        ),
        "price": 35.68,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/Multi_Fish_Vase.jpg?v=1764755737&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/ocean-dining-collection/products/tace-vase-multi-fish-blue-stoneware-vase"
    },
    "home013": {
        "labels": ["home", "glassware", "tumbler", "dining", "Niko Tumbler Tall Set of 2"],
        "title": "Niko Tumbler Tall Set of 2",
        "description": (
            "A set of two tall tumblers crafted from premium borosilicate glass with a refined two-toned footed design. "
            "Dishwasher safe and ideal for enjoying beverages with elegance."
        ),
        "price": 46.88,
        "currency": "GBP",
        "image_url": "https://www.inspitalfields.co.uk/cdn/shop/files/Untitled_design_1_d029839f-b4a2-4e2c-881f-1f349ee8817f.png?v=1745849420&width=3000",
        "product_url": "https://www.inspitalfields.co.uk/collections/glasses/products/niko-tumbler-tall-set-of-2"
    }
}

@function_tool(
    description_override=(
        "Show a product card for a specific product.\n"
        "- `product_id`: ID or key of the product to display (e.g., home001)."
    )
)
async def show_product_card(
    ctx: RunContextWrapper[AgentContext],
    product_id: str,
):
    # Use PRODUCT_KNOWLEDGE here
    product = PRODUCT_KNOWLEDGE.get(product_id)

    if not product:
        return {"error": f"No product found with id '{product_id}'"}

    # Build and stream the widget
    widget = build_product_widget(product)
    
    await ctx.context.stream_widget(
        widget,
        copy_text=product_widget_copy_text(product),
    )

    return {"status": "success", "id": product_id}