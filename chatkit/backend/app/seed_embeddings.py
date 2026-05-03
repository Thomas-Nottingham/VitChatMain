# scripts/seed_embeddings.py
from openai import OpenAI
from pymongo import MongoClient
import numpy as np

openai_client = OpenAI(api_key="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")

mongo = MongoClient("mongodb+srv://vitreongen_db_user:7I0TIyn3Ja21mFXN@vitreon-dashboard.rnn0q9b.mongodb.net/")
db = mongo["botbrain"]

def embed_text(text: str):
    response = openai_client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding  # list of floats, stores fine in Mongo

# Embed products
for product in db.products.find({"embedding": {"$exists": False}}):
    text = f"{product['title']} {product['description']} {' '.join(product.get('labels', []))}"
    embedding = embed_text(text)
    db.products.update_one({"_id": product["_id"]}, {"$set": {"embedding": embedding}})
    print(f"Embedded product: {product['product_id']}")

# Embed knowledge
for entry in db.knowledge.find({"embedding": {"$exists": False}}):
    embedding = embed_text(entry["text"])
    db.knowledge.update_one({"_id": entry["_id"]}, {"$set": {"embedding": embedding}})
    print(f"Embedded knowledge: {entry['key']}")

print("Done.")


