
# """
# Inspitalfields ChatKit server — improved shopping assistant
# """

# import json
# import os
# import re
# import numpy as np
# from dotenv import load_dotenv
# from agents import Runner, Agent
# from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
# from chatkit.server import ChatKitServer
# import openai

# from .memory_store import MemoryStore
# from .product_tools import show_product_card
# from . import kb_index

# # --------------------------------------------------
# # Load environment variables
# # --------------------------------------------------
# load_dotenv()
# OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# if not OPENAI_API_KEY:
#     raise ValueError("OPENAI_API_KEY not set in environment")

# openai.api_key = OPENAI_API_KEY

# # --------------------------------------------------
# # Config
# # --------------------------------------------------
# MAX_RECENT_ITEMS = 30
# MODEL = "gpt-4.1-mini"
# MAX_PRODUCTS = 5

# # --------------------------------------------------
# # Embedding helpers
# # --------------------------------------------------
# def embed_text(text) -> np.ndarray:
#     if not isinstance(text, str) or not text.strip():
#         text = " "
#     response = openai.embeddings.create(
#         model="text-embedding-ada-002",
#         input=text
#     )
#     return np.array(response.data[0].embedding)


# def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
#     denom = np.linalg.norm(vec1) * np.linalg.norm(vec2)
#     if denom == 0:
#         return 0.0
#     return float(np.dot(vec1, vec2) / denom)


# # --------------------------------------------------
# # Intent classifier — improved with clearer rules
# # --------------------------------------------------
# multi_intent_classifier = Agent(
#     model=MODEL,
#     name="Intent Classifier",
#     instructions="""
# You are an intent classifier for a shopping assistant chatbot.

# Analyse the FULL conversation history and the latest message, then return ONLY valid JSON — no commentary, no markdown.

# {
#   "shopping_active": true | false,
#   "needs_support": true | false,
#   "needs_general": true | false,
#   "is_followup": true | false,
#   "out_of_stock_ok": true | false
# }

# Rules:
# - shopping_active = true when the user is browsing, asking about products, requesting recommendations, asking about price, stock, availability, or wanting to buy something. Once true, keep it true unless the user explicitly changes topic entirely.
# - needs_support = true when asking about returns, refunds, delivery, shipping, complaints, or policies.
# - needs_general = true when asking about the company, founders, values, sustainability, or what the shop does.
# - is_followup = true when the latest message refers to a product already discussed (e.g. "how many left", "tell me more", "can I buy it", "yes please", "what about the price").
# - out_of_stock_ok = true when the user explicitly says they want to see all products regardless of stock, or asks about out-of-stock items specifically.

# Be generous — if in doubt, set shopping_active to true.
# """
# )


# # --------------------------------------------------
# # Semantic retrieval
# # --------------------------------------------------
# def retrieve_relevant_kb(query: str, kb_entries, top_k=5, min_similarity=0.0):
#     if not kb_entries:
#         return []
#     query_vec = embed_text(query)
#     similarities = [cosine_similarity(query_vec, entry["embedding"]) for entry in kb_entries]
#     top_indices = np.argsort(similarities)[::-1][:top_k]
#     return [kb_entries[i]["text"] for i in top_indices if similarities[i] >= min_similarity]


# def find_matching_products_semantic(query: str, top_k=MAX_PRODUCTS, include_out_of_stock=False):
#     if not query or not query.strip():
#         query = "product"

#     query_vec = embed_text(query)
#     similarities = []

#     for product_id, product in kb_index.PRODUCT_KNOWLEDGE.items():
#         # Skip out of stock unless explicitly requested
#         if not include_out_of_stock and product.get("quantity", 1) == 0:
#             continue
#         sim = cosine_similarity(query_vec, product["embedding"])
#         similarities.append((sim, product_id, product))

#     similarities.sort(reverse=True, key=lambda x: x[0])
#     return [(pid, p) for sim, pid, p in similarities[:top_k]]


# def build_reference_context(blocks, title):
#     if not blocks:
#         return ""
#     return f"\n\n=== {title} ===\n" + "\n\n---\n\n".join(blocks)


# def build_product_context(products):
#     if not products:
#         return "\n\nAvailable Products:\n[No matching products found in our current catalogue.]"

#     context = "\n\nAvailable Products (use this data to answer all product questions):\n"
#     for product_id, p in products:
#         quantity = p.get("quantity", 0)
#         if quantity == 0:
#             stock_status = "❌ OUT OF STOCK — do not recommend for immediate purchase"
#         elif quantity <= 3:
#             stock_status = f"🔴 VERY LOW STOCK — only {quantity} left, create urgency"
#         elif quantity <= 10:
#             stock_status = f"🟡 LOW STOCK — {quantity} remaining"
#         else:
#             stock_status = f"✅ In stock — {quantity} available"

#         context += (
#             f"\n- product_id: {product_id}\n"
#             f"  title: {p['title']}\n"
#             f"  price: £{p['price']} {p.get('currency', 'GBP')}\n"
#             f"  stock: {stock_status}\n"
#             f"  description: {p['description']}\n"
#             f"  labels: {', '.join(p.get('labels', []))}\n"
#             f"  image: {p.get('image_url', '')}\n"
#             f"  link: {p.get('product_url', '')}\n"
#             "  ---"
#         )
#     return context


# # --------------------------------------------------
# # Extract requested product count
# # --------------------------------------------------
# def extract_requested_count(text: str) -> int | None:
#     if not text:
#         return None
#     match = re.search(r"\b(\d+)\b", text)
#     if match:
#         try:
#             return int(match.group(1))
#         except ValueError:
#             return None
#     return None


# # --------------------------------------------------
# # Agent prompt template — improved
# # --------------------------------------------------
# UNIFIED_AGENT_TEMPLATE = """
# You are a warm, knowledgeable shopping assistant for Inspitalfields — an independent sustainable gift shop in Old Spitalfields Market, East London.

# YOUR PERSONALITY:
# - Friendly, helpful, and enthusiastic about the products
# - You genuinely love sustainable and independent brands
# - You give concise, useful answers — not walls of text
# - You use natural language, not bullet point lists

# CRITICAL RULES — follow these exactly:
# 1. ALWAYS call show_product_card for every product you mention by name — without exception
# 2. ALWAYS tell the customer the stock level when discussing a specific product
# 3. If a product is OUT OF STOCK, say so clearly but offer alternatives
# 4. If stock is LOW (3 or fewer), create natural urgency — e.g. "only 2 left so worth grabbing soon"
# 5. NEVER make up stock numbers — only use the exact figures provided below
# 6. NEVER recommend a product if it shows OUT OF STOCK unless the customer specifically asks about it
# 7. If asked about a product not in the data below, say you don't currently carry it and offer the closest alternative
# 8. When the customer says "yes please", "tell me more", or similar — they are following up on the last product discussed, so provide more detail about it

# PRODUCT DATA (use this as your single source of truth):
# {context}

# CUSTOMER MESSAGE:
# {question}

# Respond naturally and helpfully:
# """


# # --------------------------------------------------
# # Chat Server
# # --------------------------------------------------
# class StarterChatServer(ChatKitServer):
#     def __init__(self):
#         self.store = MemoryStore()
#         super().__init__(self.store)

#         # Per-session shopping state
#         self.is_shopping = False
#         self.all_shown_product_ids = set()
#         self.shown_this_turn = set()
#         self.last_discussed_products = []  # Track last products for follow-ups

#     async def respond(self, thread, item, context):
#         # Load recent conversation
#         if thread:
#             items_page = await self.store.load_thread_items(
#                 thread.id,
#                 after=None,
#                 limit=MAX_RECENT_ITEMS,
#                 order="desc",
#                 context=context
#             )
#             items = list(reversed(items_page.data))
#             agent_input = await simple_to_agent_input(items)
#             if not isinstance(agent_input, list):
#                 agent_input = []
#         else:
#             agent_input = []

#         agent_context = AgentContext(thread=thread, store=self.store, request_context=context)

#         # Get last message
#         last_message = ""
#         if agent_input:
#             last_msg_obj = agent_input[-1]
#             if isinstance(last_msg_obj, dict) and "content" in last_msg_obj:
#                 last_message = str(last_msg_obj["content"])
#             else:
#                 last_message = str(last_msg_obj)

#         # -----------------------------
#         # 1. Intent Classification
#         # -----------------------------
#         intent_result = await Runner.run(
#             multi_intent_classifier,
#             agent_input,
#             context=agent_context
#         )

#         try:
#             intent_flags = json.loads(intent_result.final_output.strip())
#         except Exception as e:
#             print("⚠️ Intent parse failed:", intent_result.final_output, e)
#             intent_flags = {
#                 "shopping_active": True,
#                 "needs_support": False,
#                 "needs_general": False,
#                 "is_followup": False,
#                 "out_of_stock_ok": False,
#             }

#         shopping_active = bool(intent_flags.get("shopping_active", False))
#         is_followup = bool(intent_flags.get("is_followup", False))
#         out_of_stock_ok = bool(intent_flags.get("out_of_stock_ok", False))

#         if shopping_active:
#             self.is_shopping = True
#         elif intent_flags.get("shopping_active") is False:
#             self.is_shopping = False

#         # -----------------------------
#         # 2. Build Dynamic Context
#         # -----------------------------
#         dynamic_context = ""
#         tools = []

#         if intent_flags.get("needs_support"):
#             support_blocks = retrieve_relevant_kb(last_message, kb_index.SUPPORT_KNOWLEDGE)
#             dynamic_context += build_reference_context(support_blocks, "CUSTOMER SUPPORT INFORMATION")

#         if intent_flags.get("needs_general"):
#             general_blocks = retrieve_relevant_kb(last_message, kb_index.GENERAL_KNOWLEDGE)
#             dynamic_context += build_reference_context(general_blocks, "GENERAL KNOWLEDGE")

#         # -----------------------------
#         # 3. Shopping Flow
#         # -----------------------------
#         if self.is_shopping:
#             requested_count = extract_requested_count(last_message) or MAX_PRODUCTS
#             query = last_message.lower()

#             user_wants_different = bool(re.search(r"\b(different|other|another|else|more options)\b", query))

#             products_to_show = []

#             if is_followup and self.last_discussed_products:
#                 # Follow-up message — re-use the products from last turn
#                 products_to_show = [
#                     (pid, kb_index.PRODUCT_KNOWLEDGE[pid])
#                     for pid in self.last_discussed_products
#                     if pid in kb_index.PRODUCT_KNOWLEDGE
#                 ]
#                 print(f"🔁 Follow-up detected — reusing {len(products_to_show)} products from last turn")

#             else:
#                 # Fresh search — detect explicit product name mentions first
#                 explicit_match_ids = [
#                     pid for pid, product in kb_index.PRODUCT_KNOWLEDGE.items()
#                     if product['title'].lower() in query
#                 ]

#                 for pid in explicit_match_ids:
#                     product = kb_index.PRODUCT_KNOWLEDGE.get(pid)
#                     if product:
#                         products_to_show.append((pid, product))

#                 # Semantic search for the rest
#                 exclude_ids = self.all_shown_product_ids if user_wants_different else set()
#                 exclude_ids |= {pid for pid, _ in products_to_show}

#                 semantic_results = find_matching_products_semantic(
#                     query,
#                     top_k=len(kb_index.PRODUCT_KNOWLEDGE),
#                     include_out_of_stock=out_of_stock_ok
#                 )

#                 for pid, product in semantic_results:
#                     if pid not in exclude_ids:
#                         products_to_show.append((pid, product))
#                     if len(products_to_show) >= MAX_PRODUCTS:
#                         break

#             # Track shown products
#             self.shown_this_turn = {pid for pid, _ in products_to_show}
#             self.all_shown_product_ids.update(self.shown_this_turn)
#             self.last_discussed_products = list(self.shown_this_turn)

#             # Warn if user requested more than MAX_PRODUCTS
#             if requested_count > MAX_PRODUCTS:
#                 dynamic_context += (
#                     f"\n\nNote: The user requested {requested_count} products "
#                     f"but you can show a maximum of {MAX_PRODUCTS} at a time. "
#                     f"Politely explain this and offer to show more on request."
#                 )

#             dynamic_context += build_product_context(products_to_show)
#             tools.append(show_product_card)

#             print(f"🛍️ Shopping | follow-up={is_followup} | products: {[pid for pid, _ in products_to_show]}")

#         # -----------------------------
#         # 4. Build and run agent
#         # -----------------------------
#         agent_prompt = UNIFIED_AGENT_TEMPLATE.format(
#             context=dynamic_context or "No specific product context available.",
#             question=last_message
#         )

#         agent = Agent(
#             model=MODEL,
#             name="Inspitalfields Shopping Assistant",
#             instructions=agent_prompt,
#             tools=tools
#         )

#         result = Runner.run_streamed(agent, agent_input, context=agent_context)
#         async for event in stream_agent_response(agent_context, result):
#             yield event


"""
Orc's Nest ChatKit server — improved shopping assistant
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
MODEL = "gpt-5.4-mini"
MAX_PRODUCTS = 5

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
    denom = np.linalg.norm(vec1) * np.linalg.norm(vec2)
    if denom == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / denom)


# --------------------------------------------------
# Intent classifier — improved with clearer rules
# --------------------------------------------------
multi_intent_classifier = Agent(
    model=MODEL,
    name="Intent Classifier",
    instructions="""
You are an intent classifier for a shopping assistant chatbot.

Analyse the FULL conversation history and the latest message, then return ONLY valid JSON — no commentary, no markdown.

{
  "shopping_active": true | false,
  "needs_support": true | false,
  "needs_general": true | false,
  "is_followup": true | false,
  "out_of_stock_ok": true | false
}

Rules:
- shopping_active = true when the user is browsing, asking about products, requesting recommendations, asking about price, stock, availability, or wanting to buy something. Once true, keep it true unless the user explicitly changes topic entirely.
- needs_support = true when asking about returns, refunds, delivery, shipping, complaints, or policies.
- needs_general = true when asking about the company, founders, values, sustainability, or what the shop does.
- is_followup = true when the latest message refers to a product already discussed (e.g. "how many left", "tell me more", "can I buy it", "yes please", "what about the price").
- out_of_stock_ok = true when the user explicitly says they want to see all products regardless of stock, or asks about out-of-stock items specifically.

Be generous — if in doubt, set shopping_active to true.
"""
)


# --------------------------------------------------
# Semantic retrieval
# --------------------------------------------------
def retrieve_relevant_kb(query: str, kb_entries, top_k=5, min_similarity=0.0):
    if not kb_entries:
        return []
    query_vec = embed_text(query)
    similarities = [cosine_similarity(query_vec, entry["embedding"]) for entry in kb_entries]
    top_indices = np.argsort(similarities)[::-1][:top_k]
    return [kb_entries[i]["text"] for i in top_indices if similarities[i] >= min_similarity]


def find_matching_products_semantic(query: str, top_k=MAX_PRODUCTS, include_out_of_stock=False):
    if not query or not query.strip():
        query = "product"

    query_vec = embed_text(query)
    similarities = []

    for product_id, product in kb_index.PRODUCT_KNOWLEDGE.items():
        # Skip out of stock unless explicitly requested
        if not include_out_of_stock and product.get("quantity", 1) == 0:
            continue
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
        return "\n\nAvailable Products:\n[No matching products found in our current catalogue.]"

    context = "\n\nAvailable Products (use this data to answer all product questions):\n"
    for product_id, p in products:
        quantity = p.get("quantity", 0)
        if quantity == 0:
            stock_status = "❌ OUT OF STOCK — do not recommend for immediate purchase"
        elif quantity <= 3:
            stock_status = f"🔴 VERY LOW STOCK — only {quantity} left, create urgency"
        elif quantity <= 10:
            stock_status = f"🟡 LOW STOCK — {quantity} remaining"
        else:
            stock_status = f"✅ In stock — {quantity} available"

        context += (
            f"\n- product_id: {product_id}\n"
            f"  title: {p['title']}\n"
            f"  price: £{p['price']} {p.get('currency', 'GBP')}\n"
            f"  stock: {stock_status}\n"
            f"  description: {p['description']}\n"
            f"  labels: {', '.join(p.get('labels', []))}\n"
            f"  image: {p.get('image_url', '')}\n"
            f"  link: {p.get('product_url', '')}\n"
            "  ---"
        )
    return context


# --------------------------------------------------
# Extract requested product count
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
# Agent prompt template — improved
# --------------------------------------------------
UNIFIED_AGENT_TEMPLATE = """
You are Orc — the in-store assistant for the Orc's Nest in London, an independent board games shop.

YOUR PERSONALITY:
- You sound like a veteran game shop employee with dry humour and strong knowledge of the hobby
- Your personality comes through mostly in introductions, transitions, and occasional side comments — never constant roleplay
- You are enthusiastic about great games but honest about weak ones
- You have genuine opinions and help customers find the right fit for their group
- Your humour is subtle, understated, and occasional — one dry comment is enough
- You speak naturally and concisely, never like a corporate FAQ page
- You can use light fantasy/shopkeeper flavour tied to the name "Orc", but keep it grounded and readable
- You never overwhelm the customer with lore, jokes, or long explanations

EXAMPLES OF YOUR TONE:
- "Orc here. Good choice asking before buying that one."
- "Dangerous game. People buy one expansion and suddenly it's a lifestyle."
- "Only 2 left. The weekend crowd tends to loot the shelves."
- "Brilliant if your group enjoys negotiation. Miserable if they don't."
- "Surprisingly clever for a game about birds."

CRITICAL RULES — follow these exactly:
1. Run show_product_card for products when relevant 
2. ONLY tell the customer the stock level when you think its necessary
3. Keep responses concise and conversational — avoid walls of text and bullet-point essays
4. Personality should enhance the shopping experience, not dominate it
5. Never insert the functions or tools you are calling to the chat remember you are speaking to a human so they need a normal human conversation
6. Dont lie




PRODUCT DATA (use this as your single source of truth):
{context}

CUSTOMER MESSAGE:
{question}

Respond naturally and helpfully as Orc:
"""


# --------------------------------------------------
# Chat Server
# --------------------------------------------------
class StarterChatServer(ChatKitServer):
    def __init__(self):
        self.store = MemoryStore()
        super().__init__(self.store)

        # Per-session shopping state
        self.is_shopping = False
        self.all_shown_product_ids = set()
        self.shown_this_turn = set()
        self.last_discussed_products = []  # Track last products for follow-ups

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
        # 1. Intent Classification
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
                "is_followup": False,
                "out_of_stock_ok": False,
            }

        shopping_active = bool(intent_flags.get("shopping_active", False))
        is_followup = bool(intent_flags.get("is_followup", False))
        out_of_stock_ok = bool(intent_flags.get("out_of_stock_ok", False))

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
        # 3. Shopping Flow
        # -----------------------------
        if self.is_shopping:
            requested_count = extract_requested_count(last_message) or MAX_PRODUCTS
            query = last_message.lower()

            user_wants_different = bool(re.search(r"\b(different|other|another|else|more options)\b", query))

            products_to_show = []

            if is_followup and self.last_discussed_products:
                # Follow-up message — re-use the products from last turn
                products_to_show = [
                    (pid, kb_index.PRODUCT_KNOWLEDGE[pid])
                    for pid in self.last_discussed_products
                    if pid in kb_index.PRODUCT_KNOWLEDGE
                ]
                print(f"🔁 Follow-up detected — reusing {len(products_to_show)} products from last turn")

            else:
                # Fresh search — detect explicit product name mentions first
                explicit_match_ids = [
                    pid for pid, product in kb_index.PRODUCT_KNOWLEDGE.items()
                    if product['title'].lower() in query
                ]

                for pid in explicit_match_ids:
                    product = kb_index.PRODUCT_KNOWLEDGE.get(pid)
                    if product:
                        products_to_show.append((pid, product))

                # Semantic search for the rest
                exclude_ids = self.all_shown_product_ids if user_wants_different else set()
                exclude_ids |= {pid for pid, _ in products_to_show}

                semantic_results = find_matching_products_semantic(
                    query,
                    top_k=len(kb_index.PRODUCT_KNOWLEDGE),
                    include_out_of_stock=out_of_stock_ok
                )

                for pid, product in semantic_results:
                    if pid not in exclude_ids:
                        products_to_show.append((pid, product))
                    if len(products_to_show) >= MAX_PRODUCTS:
                        break

            # Track shown products
            self.shown_this_turn = {pid for pid, _ in products_to_show}
            self.all_shown_product_ids.update(self.shown_this_turn)
            self.last_discussed_products = list(self.shown_this_turn)

            # Warn if user requested more than MAX_PRODUCTS
            if requested_count > MAX_PRODUCTS:
                dynamic_context += (
                    f"\n\nNote: The user requested {requested_count} products "
                    f"but you can show a maximum of {MAX_PRODUCTS} at a time. "
                    f"Politely explain this and offer to show more on request."
                )

            dynamic_context += build_product_context(products_to_show)
            tools.append(show_product_card)

            print(f"🛍️ Shopping | follow-up={is_followup} | products: {[pid for pid, _ in products_to_show]}")

        # -----------------------------
        # 4. Build and run agent
        # -----------------------------
        agent_prompt = UNIFIED_AGENT_TEMPLATE.format(
            context=dynamic_context or "No specific product context available.",
            question=last_message
        )

        agent = Agent(
            model=MODEL,
            name="Orcs Nest Shopping Assistant",
            instructions=agent_prompt,
            tools=tools
        )

        result = Runner.run_streamed(agent, agent_input, context=agent_context)
        async for event in stream_agent_response(agent_context, result):
            yield event