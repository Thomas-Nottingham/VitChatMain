


"""
Enhanced Vitreon ChatKit server with unified agent + semantic retrieval
"""

import json
import os
import numpy as np
from dotenv import load_dotenv
from agents import Runner, Agent
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer
import openai

from .memory_store import MemoryStore
from .product_tools import show_product_card
from .support_knowledge import SUPPORT_KNOWLEDGE
from .general_knowledge import GENERAL_KNOWLEDGE
from .product_tools import PRODUCT_KNOWLEDGE
# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not set in environment")

openai.api_key = OPENAI_API_KEY

# --------------------------------------------------
# Config
# --------------------------------------------------
MAX_RECENT_ITEMS = 30
MODEL = "gpt-4.1-mini"

# --------------------------------------------------
# Embedding helpers
# --------------------------------------------------
def embed_text(text) -> np.ndarray:
    """Generate embeddings for a text string using OpenAI."""
    if not isinstance(text, str) or not text.strip():
        text = " "
    response = openai.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return np.array(response.data[0].embedding)


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))


def precompute_embeddings(kb):
    for entry in kb:
        if entry.get("embedding") is None:
            entry["embedding"] = embed_text(entry["text"])
    return kb


# Precompute embeddings for semantic search
GENERAL_KNOWLEDGE = precompute_embeddings(GENERAL_KNOWLEDGE)
SUPPORT_KNOWLEDGE = precompute_embeddings(SUPPORT_KNOWLEDGE)

# --------------------------------------------------
# Multi-intent classifier
# --------------------------------------------------
multi_intent_classifier = Agent(
    model=MODEL,
    name="Multi-Intent Classifier",
    instructions=(
        "Analyze the user's LATEST message and determine which information categories are needed.\n"
        "Return a JSON object with boolean flags.\n\n"
        "DEFINITIONS:\n"
        "- needs_support: Specific policy questions (Refunds, Privacy, Terms, Data Security, Contacting Support, Trade, work with us, values, sustainability).\n"
        "- needs_general: Company info (Founding date, Mission), Services, Features, Benefits, 'What do you do?'.\n"
        "- needs_products: Requests to see products, shopping, recommendations, pricing for specific items.\n\n"
        "JSON FORMAT:\n"
        "{\n"
        '  "needs_support": true/false,\n'
        '  "needs_general": true/false,\n'
        '  "needs_products": true/false\n'
        "}\n"
    ),
)

# Precompute embeddings for product knowledge at server startup
for product_id, product in PRODUCT_KNOWLEDGE.items():
    if "embedding" not in product or product["embedding"] is None:
        # Combine title, description, and labels for embedding
        text_to_embed = f"{product['title']} {product['description']} {' '.join(product.get('labels', []))}"
        product["embedding"] = embed_text(text_to_embed)

# --------------------------------------------------
# Semantic retrieval
# --------------------------------------------------
def retrieve_relevant_kb(query: str, kb_entries, top_k=5, min_similarity=0.0):
    """Return top-k relevant text blocks, optionally filtering by similarity."""
    query_vec = embed_text(query)
    similarities = [cosine_similarity(query_vec, entry["embedding"]) for entry in kb_entries]
    top_indices = np.argsort(similarities)[::-1][:top_k]
    return [kb_entries[i]["text"] for i in top_indices if similarities[i] >= min_similarity]

# --------------------------------------------------
# Unified agent template
# --------------------------------------------------
UNIFIED_AGENT_TEMPLATE = """

    You are a customer support assistant for Inspitalfields,
    an independent sustainable gift shop.

    ONLY use the information below.
    If it is not present, say:
    "I’m sorry, I don’t have that information at the moment."

    Context:
    {context}

    Customer question:
    {question}

    Answer clearly, warmly, and concisely:
"""




def find_matching_products_semantic(query: str, top_k=5):
    """Return top-k products that best match the query using embeddings."""
    query_vec = embed_text(query)
    similarities = []
    
    for product_id, product in PRODUCT_KNOWLEDGE.items():
        sim = cosine_similarity(query_vec, product["embedding"])
        similarities.append((sim, product_id, product))
    
    # Sort by similarity descending
    similarities.sort(reverse=True, key=lambda x: x[0])
    
    # Return top matches as (product_id, product dict)
    return [(pid, p) for sim, pid, p in similarities[:top_k]]



# --------------------------------------------------
# Product retrieval
# --------------------------------------------------
def find_matching_products(keywords_str):
    keywords = [k.strip().lower() for k in keywords_str.split(",")]
    if "all" in keywords or "products" in keywords:
        return list(PRODUCT_KNOWLEDGE.items())

    matches = []
    for product_id, product in PRODUCT_KNOWLEDGE.items():
        label_matches = sum(1 for k in keywords if k in [l.lower() for l in product.get("labels", [])])
        title_matches = sum(1 for k in keywords if k in product.get("title", "").lower())
        description_matches = sum(1 for k in keywords if k in product.get("description", "").lower())
        score = (label_matches * 3) + (title_matches * 2) + description_matches
        if score > 0:
            matches.append((score, product_id, product))
    matches.sort(reverse=True, key=lambda x: x[0])
    return [(pid, p) for _, pid, p in matches]


def build_reference_context(blocks, title):
    if not blocks:
        return ""
    return f"\n\n=== {title} ===\n" + "\n\n---\n\n".join(blocks)


def build_product_context(products):
    if not products:
        return "\n\nAvailable Products:\n[No matching products found. Ask the user for more details.]"
    context = "\n\nAvailable Products:\n"
    for product_id, p in products:
        context += (
            f"- product_id: {product_id}\n"
            f"  title: {p['title']}\n"
            f"  price: {p['price']} {p['currency']}\n"
            f"  description: {p['description']}\n"
            f"  image: {p['image_url']}\n"
            f"  link: {p['product_url']}\n"
            "  ---\n"
        )
    return context



# --------------------------------------------------
# Chat Server
# --------------------------------------------------
class StarterChatServer(ChatKitServer):
    def __init__(self):
        self.store = MemoryStore()
        self.support_label_extractor = Agent(model=MODEL, name="Support Label Extractor", instructions="...")
        self.product_keyword_extractor = Agent(model=MODEL, name="Product Keyword Extractor", instructions="...")
        super().__init__(self.store)

    async def respond(self, thread, item, context):
        # Convert thread items to agent_input safely
        if thread:
            items_page = await self.store.load_thread_items(thread.id, after=None, limit=MAX_RECENT_ITEMS, order="desc", context=context)
            items = list(reversed(items_page.data))
            agent_input = await simple_to_agent_input(items)
            if not isinstance(agent_input, list):
                agent_input = []
        else:
            agent_input = []

        agent_context = AgentContext(thread=thread, store=self.store, request_context=context)

        # Safely get last message
        last_message = ""
        if agent_input:
            last_msg_obj = agent_input[-1]
            if isinstance(last_msg_obj, dict) and "content" in last_msg_obj:
                last_message = str(last_msg_obj["content"])
            else:
                last_message = str(last_msg_obj)

        # -----------------------------
        # 1. Intent Classification
        # -----------------------------
        intent_result = await Runner.run(multi_intent_classifier, agent_input, context=agent_context)
        try:
            intent_flags = json.loads(intent_result.final_output.strip())
        except Exception:
            intent_flags = {"needs_support": False, "needs_general": True, "needs_products": False}

        # -----------------------------
        # 2. Build Dynamic Context
        # -----------------------------
        dynamic_context = ""
        tools = []

        if intent_flags.get("needs_support"):
            support_blocks = retrieve_relevant_kb(last_message, SUPPORT_KNOWLEDGE)
            dynamic_context += build_reference_context(support_blocks, "CUSTOMER SUPPORT INFORMATION")

        if intent_flags.get("needs_general"):
            general_blocks = retrieve_relevant_kb(last_message, GENERAL_KNOWLEDGE)
            dynamic_context += build_reference_context(general_blocks, "GENERAL KNOWLEDGE")

        if intent_flags.get("needs_products"):
            # Extract user query for product
            keyword_result = await Runner.run(self.product_keyword_extractor, agent_input, context=agent_context)
            query = str(getattr(keyword_result, "final_output", "")).lower()
            
            # Semantic search for products
            products = find_matching_products_semantic(query)
            
            # Build context for agent and add widget tool
            dynamic_context += build_product_context(products)
            tools.append(show_product_card)


        # -----------------------------
        # 3. Unified Agent
        # -----------------------------
        agent_prompt = UNIFIED_AGENT_TEMPLATE.format(
            context=dynamic_context,
            question=last_message
        )

        agent = Agent(
            model=MODEL,
            name="Car Customr Support Assistant",
            instructions=agent_prompt,
            tools=tools
        )

        # -----------------------------
        # 4. Stream Response
        # -----------------------------
        result = Runner.run_streamed(agent, agent_input, context=agent_context)
        async for event in stream_agent_response(agent_context, result):
            yield event

