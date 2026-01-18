from openai import OpenAI
import numpy as np
from .support_knowledge import SUPPORT_KNOWLEDGE
from .general_knowledge import GENERAL_KNOWLEDGE
from .product_tools import PRODUCT_KNOWLEDGE

client = OpenAI(api_key="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")

def embed_text(text: str):
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return np.array(response["data"][0]["embedding"])

# --------------------------------------------------
# Precompute embeddings for KBs at startup
# --------------------------------------------------
for kb in [GENERAL_KNOWLEDGE, SUPPORT_KNOWLEDGE]:
    for entry in kb:
        if entry.get("embedding") is None:
            entry["embedding"] = embed_text(entry["text"])

# Precompute embeddings for all car products
for product_id, product in PRODUCT_KNOWLEDGE.items():
    if product.get("embedding") is None:
        text_to_embed = f"{product['title']} {product['description']} {' '.join(product.get('labels', []))}"
        product["embedding"] = embed_text(text_to_embed)
