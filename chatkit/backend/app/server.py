

"""
Enhanced Vitreon ChatKit server with unified agent + semantic retrieval
"""

import json
import os
import re
import numpy as np
from dotenv import load_dotenv
from agents import Runner, Agent
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer
import openai

from .memory_store import MemoryStore
from .product_tools import show_product_card

from . import kb_index

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
MAX_PRODUCTS = 5  # Maximum products to show at once

# --------------------------------------------------
# Embedding helpers
# --------------------------------------------------
def embed_text(text) -> np.ndarray:
    if not isinstance(text, str) or not text.strip():
        text = " "
    response = openai.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return np.array(response.data[0].embedding)


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    denom = (np.linalg.norm(vec1) * np.linalg.norm(vec2))
    if denom == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / denom)



# --------------------------------------------------
# Multi-intent + Shopping State Classifier
# --------------------------------------------------
multi_intent_classifier = Agent(
    model=MODEL,
    name="Shopping State Classifier",
    instructions=(
        """
Return ONLY valid JSON. No commentary. No markdown.

Analyze the conversation and decide:

{
  "shopping_active": true | false,
  "needs_support": true | false,
  "needs_general": true | false
}

Rules:
- shopping_active = true if the user is browsing, asking about, comparing,
  filtering, or requesting products.
- shopping_active remains true across follow-ups unless the user clearly changes topic.
- If unsure, set shopping_active to true.
"""
    ),
)

# --------------------------------------------------
# Precompute embeddings for product knowledge
# --------------------------------------------------
for product_id, product in kb_index.PRODUCT_KNOWLEDGE.items():
    if "embedding" not in product or product["embedding"] is None:
        text_to_embed = f"{product['title']} {product['description']} {' '.join(product.get('labels', []))}"
        product["embedding"] = embed_text(text_to_embed)

# --------------------------------------------------
# Semantic retrieval helpers
# --------------------------------------------------
def retrieve_relevant_kb(query: str, kb_entries, top_k=5, min_similarity=0.0):
    query_vec = embed_text(query)
    similarities = [cosine_similarity(query_vec, entry["embedding"]) for entry in kb_entries]
    top_indices = np.argsort(similarities)[::-1][:top_k]
    return [kb_entries[i]["text"] for i in top_indices if similarities[i] >= min_similarity]


def find_matching_products_semantic(query: str, top_k=MAX_PRODUCTS):
    if not query or not query.strip():
        query = "product"

    query_vec = embed_text(query)
    similarities = []

    for product_id, product in kb_index.PRODUCT_KNOWLEDGE.items():
        sim = cosine_similarity(query_vec, product["embedding"])
        similarities.append((sim, product_id, product))

    similarities.sort(reverse=True, key=lambda x: x[0])
    return [(pid, p) for sim, pid, p in similarities[:top_k]]


def build_reference_context(blocks, title):
    if not blocks:
        return ""
    return f"\n\n=== {title} ===\n" + "\n\n---\n\n".join(blocks)


def build_product_context(products):
    if not products:
        return "\n\nAvailable Products:\n[No matching products found.]"

    context = "\n\nAvailable Products:\n"
    for product_id, p in products:
        quantity = p.get("quantity", 0)
        if quantity == 0:
            stock_status = "OUT OF STOCK"
        elif quantity <= 5:
            stock_status = f"LOW STOCK — only {quantity} left"
        else:
            stock_status = f"In stock ({quantity} available)"

        context += (
            f"- product_id: {product_id}\n"
            f"  title: {p['title']}\n"
            f"  price: {p['price']} {p['currency']}\n"
            f"  stock: {stock_status}\n"
            f"  description: {p['description']}\n"
            f"  image: {p['image_url']}\n"
            f"  link: {p['product_url']}\n"
            "  ---\n"
        )
    return context


# --------------------------------------------------
# Extract requested product count from user message
# --------------------------------------------------
def extract_requested_count(text: str) -> int | None:
    if not text:
        return None
    match = re.search(r"\b(\d+)\b", text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


# --------------------------------------------------
# Unified agent template
# --------------------------------------------------
UNIFIED_AGENT_TEMPLATE = """
You are a customer support assistant for Inspitalfields,
an independent sustainable gift shop.

You MUST use the provided product data when shopping is active.
When mentioning a product to the user, ALWAYS call the tool
`show_product_card` with the correct product_id so the product card appears.

ONLY use the information below.
If it is not present, say:
"I’m sorry, I don’t have that information at the moment."

Context:
{context}

Customer question:
{question}

Answer clearly, warmly, and concisely:
"""


# --------------------------------------------------
# Chat Server
# --------------------------------------------------
class StarterChatServer(ChatKitServer):
    def __init__(self):
        self.store = MemoryStore()
        self.support_label_extractor = Agent(model=MODEL, name="Support Label Extractor", instructions="...")
        super().__init__(self.store)

        # Persistent shopping state
        self.is_shopping = False
        self.all_shown_product_ids = set()  # All products ever shown
        self.shown_this_turn = set()        # Products shown this turn

    async def respond(self, thread, item, context):
        # Load recent conversation
        if thread:
            items_page = await self.store.load_thread_items(
                thread.id,
                after=None,
                limit=MAX_RECENT_ITEMS,
                order="desc",
                context=context
            )
            items = list(reversed(items_page.data))
            agent_input = await simple_to_agent_input(items)
            if not isinstance(agent_input, list):
                agent_input = []
        else:
            agent_input = []

        agent_context = AgentContext(thread=thread, store=self.store, request_context=context)

        # Get last message
        last_message = ""
        if agent_input:
            last_msg_obj = agent_input[-1]
            if isinstance(last_msg_obj, dict) and "content" in last_msg_obj:
                last_message = str(last_msg_obj["content"])
            else:
                last_message = str(last_msg_obj)

        # -----------------------------
        # 1. Intent + Shopping State Classification
        # -----------------------------
        intent_result = await Runner.run(
            multi_intent_classifier,
            agent_input,
            context=agent_context
        )

        try:
            intent_flags = json.loads(intent_result.final_output.strip())
        except Exception as e:
            print("⚠️ Intent parse failed:", intent_result.final_output, e)
            intent_flags = {
                "shopping_active": True,
                "needs_support": False,
                "needs_general": False,
            }

        shopping_active = bool(intent_flags.get("shopping_active", False))
        if shopping_active:
            self.is_shopping = True
        elif intent_flags.get("shopping_active") is False:
            self.is_shopping = False

        # -----------------------------
        # 2. Build Dynamic Context
        # -----------------------------
        dynamic_context = ""
        tools = []

        if intent_flags.get("needs_support"):
            support_blocks = retrieve_relevant_kb(last_message, kb_index.SUPPORT_KNOWLEDGE)
            dynamic_context += build_reference_context(support_blocks, "CUSTOMER SUPPORT INFORMATION")

        if intent_flags.get("needs_general"):
            general_blocks = retrieve_relevant_kb(last_message, kb_index.GENERAL_KNOWLEDGE)
            dynamic_context += build_reference_context(general_blocks, "GENERAL KNOWLEDGE")

        # -----------------------------
        # 3. Shopping Flow Product Retrieval
        # -----------------------------
        if self.is_shopping:
            requested_count = extract_requested_count(last_message) or MAX_PRODUCTS
            query = last_message.lower()

            # 1️⃣ Detect explicit product mentions
            explicit_match_ids = [
                pid for pid, product in kb_index.PRODUCT_KNOWLEDGE.items()
                if product['title'].lower() in query
            ]

            # 2️⃣ Detect "different" or "other" requests
            user_wants_different = bool(re.search(r"\b(different|other|another)\b", query))

            # 3️⃣ Gather semantic matches
            all_products = find_matching_products_semantic(query, top_k=len(kb_index.PRODUCT_KNOWLEDGE))

            # 4️⃣ Select products to show
            products_to_show = []

            # Add explicit requests first
            for pid in explicit_match_ids:
                product = kb_index.PRODUCT_KNOWLEDGE.get(pid)
                if product:
                    products_to_show.append((pid, product))

            # Then add new/different products if needed
            exclude_ids = self.all_shown_product_ids if user_wants_different else set()
            exclude_ids |= {pid for pid, _ in products_to_show}

            for pid, product in all_products:
                if pid not in exclude_ids:
                    products_to_show.append((pid, product))
                if len(products_to_show) >= MAX_PRODUCTS:
                    break

            # 5️⃣ Track shown products
            self.shown_this_turn = {pid for pid, _ in products_to_show}
            self.all_shown_product_ids.update(self.shown_this_turn)

            # 6️⃣ Inform assistant if requested more than MAX_PRODUCTS
            if requested_count > MAX_PRODUCTS:
                dynamic_context += (
                    f"\n\nNote to assistant:\n"
                    f"The user requested {requested_count} products, "
                    f"but you can only show up to {MAX_PRODUCTS} products at a time. "
                    f"Politely explain this to the user."
                )

            # 7️⃣ Build context for assistant
            dynamic_context += build_product_context(products_to_show)
            tools.append(show_product_card)

            # Debug
            print("🛍️ Shopping active | Products this turn:", [pid for pid, _ in products_to_show])

        # -----------------------------
        # 4. Unified Agent
        # -----------------------------
        agent_prompt = UNIFIED_AGENT_TEMPLATE.format(
            context=dynamic_context,
            question=last_message
        )

        agent = Agent(
            model=MODEL,
            name="Inspitalfields Shopping Assistant",
            instructions=agent_prompt,
            tools=tools
        )

        # -----------------------------
        # 5. Stream Response
        # -----------------------------
        result = Runner.run_streamed(agent, agent_input, context=agent_context)
        async for event in stream_agent_response(agent_context, result):
            yield event
