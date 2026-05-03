

# kb_index.py
import os
import numpy as np
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

mongo = MongoClient("mongodb+srv://vitreongen_db_user:7I0TIyn3Ja21mFXN@vitreon-dashboard.rnn0q9b.mongodb.net/")
db = mongo["botbrain"]

def load_knowledge():
    entries = list(db.knowledge.find({"embedding": {"$exists": True}}))
    for e in entries:
        e["embedding"] = np.array(e["embedding"])
    return entries

def load_products():
    products = list(db.products.find({"embedding": {"$exists": True}}))
    result = {}
    for p in products:
        p["embedding"] = np.array(p["embedding"])
        result[p["product_id"]] = p
    return result

KNOWLEDGE_INDEX = load_knowledge()
PRODUCT_KNOWLEDGE = load_products()

import threading
import time

def _reload():
    global PRODUCT_KNOWLEDGE, KNOWLEDGE_INDEX, GENERAL_KNOWLEDGE, SUPPORT_KNOWLEDGE
    while True:
        time.sleep(300)
        PRODUCT_KNOWLEDGE = load_products()
        KNOWLEDGE_INDEX = load_knowledge()
        GENERAL_KNOWLEDGE = [e for e in KNOWLEDGE_INDEX if e.get("category") == "general"]
        SUPPORT_KNOWLEDGE = [e for e in KNOWLEDGE_INDEX if e.get("category") == "support"]
        print("🔄 Knowledge reloaded from MongoDB")

# Add at the bottom of kb_index.py, after KNOWLEDGE_INDEX is set
GENERAL_KNOWLEDGE = [e for e in KNOWLEDGE_INDEX if e.get("category") == "general"]
SUPPORT_KNOWLEDGE = [e for e in KNOWLEDGE_INDEX if e.get("category") == "support"]

# Start background reload thread
threading.Thread(target=_reload, daemon=True).start()