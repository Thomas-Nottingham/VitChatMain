
"""
Choosing Keeping ChatKit server — tool-based product retrieval
"""

import os
import re
import numpy as np
from dotenv import load_dotenv
from agents import Runner, Agent, function_tool, RunContextWrapper
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
# Deterministic intent classification — no LLM call needed
# --------------------------------------------------
def classify_intent(message: str, is_shopping_already: bool) -> dict:
    msg = message.lower().strip()

    # Short messages are almost always followups
    is_followup = (
        len(message.split()) <= 4 or
        any(msg.startswith(p) for p in [
            "yes", "yeah", "sure", "ok", "that one", "tell me more",
            "how many", "in stock", "can i", "and that", "what about",
            "show me", "yes please", "sounds good", "perfect", "nice"
        ])
    )

    # Once shopping is active keep it active unless clearly off-topic
    non_shopping = [
        "return", "refund", "email", "contact", "address",
        "location", "where are you", "opening", "hours", "closed",
        "policy", "shipping", "delivery", "how do i"
    ]
    is_clearly_support = any(phrase in msg for phrase in non_shopping)

    shopping_active = is_shopping_already or (not is_clearly_support)

    out_of_stock_ok = "out of stock" in msg or "unavailable" in msg or "don't have" in msg

    return {
        "shopping_active": shopping_active,
        "is_followup": is_followup,
        "out_of_stock_ok": out_of_stock_ok,
    }


# --------------------------------------------------
# Knowledge retrieval — single unified search
# --------------------------------------------------
def retrieve_relevant_kb(query: str, top_k: int = 8, min_similarity: float = 0.25) -> list[str]:
    """Search all knowledge entries — general and support combined."""
    all_knowledge = kb_index.KNOWLEDGE_INDEX
    if not all_knowledge:
        return []

    query_vec = embed_text(query)
    scored = []
    for entry in all_knowledge:
        sim = cosine_similarity(query_vec, entry["embedding"])
        if sim >= min_similarity:
            scored.append((sim, entry["text"]))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [text for _, text in scored[:top_k]]


# --------------------------------------------------
# Product search — hybrid keyword + semantic
# --------------------------------------------------
def search_products(query: str, include_out_of_stock: bool = False, limit: int = 5) -> list[dict]:
    """
    Hybrid search: exact SKU/title match first, then semantic.
    Returns list of product dicts.
    """
    query_lower = query.lower().strip()
    results = []
    seen_ids = set()

    # 1. Exact SKU match
    if query_lower in kb_index.PRODUCT_KNOWLEDGE:
        p = kb_index.PRODUCT_KNOWLEDGE[query_lower]
        results.append(p)
        seen_ids.add(query_lower)

    # 2. Exact or partial title match
    for pid, product in kb_index.PRODUCT_KNOWLEDGE.items():
        if pid in seen_ids:
            continue
        title_lower = product["title"].lower()
        if query_lower in title_lower or title_lower in query_lower:
            if include_out_of_stock or product.get("quantity", 1) > 0:
                results.append(product)
                seen_ids.add(pid)

    # 3. Label/category match
    query_words = set(query_lower.split())
    for pid, product in kb_index.PRODUCT_KNOWLEDGE.items():
        if pid in seen_ids:
            continue
        product_labels = {l.lower() for l in product.get("labels", [])}
        if query_words & product_labels:  # intersection
            if include_out_of_stock or product.get("quantity", 1) > 0:
                results.append(product)
                seen_ids.add(pid)

    # 4. Semantic search for the rest
    if len(results) < limit:
        query_vec = embed_text(query)
        scored = []
        for pid, product in kb_index.PRODUCT_KNOWLEDGE.items():
            if pid in seen_ids:
                continue
            if not include_out_of_stock and product.get("quantity", 1) == 0:
                continue
            sim = cosine_similarity(query_vec, product["embedding"])
            scored.append((sim, pid, product))

        scored.sort(reverse=True, key=lambda x: x[0])
        for sim, pid, product in scored:
            if sim < 0.3:
                break
            results.append(product)
            seen_ids.add(pid)
            if len(results) >= limit * 3:  # fetch generous pool
                break

    return results


def format_product_for_agent(p: dict) -> dict:
    """Return clean product dict for agent consumption."""
    quantity = p.get("quantity", 0)
    if quantity == 0:
        stock = "OUT OF STOCK"
    elif quantity <= 3:
        stock = f"VERY LOW — only {quantity} left"
    elif quantity <= 10:
        stock = f"LOW — {quantity} remaining"
    else:
        stock = f"In stock ({quantity} available)"

    return {
        "product_id": p.get("product_id", ""),
        "title": p.get("title", ""),
        "price": f"£{p.get('price', 0)} {p.get('currency', 'GBP')}",
        "stock": stock,
        "description": p.get("description", ""),
        "labels": p.get("labels", []),
    }


# --------------------------------------------------
# Agent tools
# --------------------------------------------------
@function_tool(
    description_override=(
        "Search the product catalogue by name, category, SKU, or description. "
        "Use this whenever a customer asks about products, wants recommendations, "
        "asks what you stock, or mentions any product category. "
        "Examples: 'pens', 'something under £20', 'TEN001'."
    )
)
async def search_products_tool(
    ctx: RunContextWrapper[AgentContext],
    query: str,
) -> dict:
    """Search products and return results."""
    print(f"🔍 search_products_tool called: '{query}'")

    # Get thread state for out_of_stock preference
    server = ctx.context.request_context.get("server")
    thread_id = ctx.context.thread.id if ctx.context.thread else "anonymous"
    out_of_stock_ok = False
    if server:
        state = server._get_state(thread_id)
        out_of_stock_ok = state.get("out_of_stock_ok", False)

    results = search_products(query, include_out_of_stock=out_of_stock_ok, limit=MAX_PRODUCTS)

    if not results:
        return {
            "found": False,
            "message": f"No products found for '{query}'. Try a different search term or ask for something similar.",
            "products": []
        }

    formatted = [format_product_for_agent(p) for p in results[:MAX_PRODUCTS]]

    # Update thread state with shown products
    if server:
        state = server._get_state(thread_id)
        shown = [p.get("product_id") for p in results[:MAX_PRODUCTS]]
        state["last_discussed_products"] = shown
        state["all_shown_product_ids"].update(shown)
        state["is_shopping"] = True

    return {
        "found": True,
        "count": len(formatted),
        "products": formatted,
        "instruction": "Call show_product_card for each product you mention by name."
    }


@function_tool(
    description_override=(
        "Get full details for a specific product by its exact product ID or SKU. "
        "Use this when a customer asks about a specific product you already know the ID of, "
        "or when they mention a product name you need to confirm exists. "
        "Example product IDs: 'TEN001', 'FOD001', 'MUG003'."
    )
)
async def get_product_by_id(
    ctx: RunContextWrapper[AgentContext],
    product_id: str,
) -> dict:
    """Get a specific product by ID."""
    print(f"🔍 get_product_by_id called: '{product_id}'")

    # Try exact match first
    product = kb_index.PRODUCT_KNOWLEDGE.get(product_id)

    # Try case-insensitive
    if not product:
        for pid, p in kb_index.PRODUCT_KNOWLEDGE.items():
            if pid.lower() == product_id.lower():
                product = p
                break

    if not product:
        return {
            "found": False,
            "message": f"No product found with ID '{product_id}'. The ID may be incorrect."
        }

    return {
        "found": True,
        "product": format_product_for_agent(product)
    }


@function_tool(
    description_override=(
        "Search for products that are similar to or go well with a given product. "
        "Use when a customer asks for accessories, add-ons, or 'what goes with this'. "
        "Pass the product title or category as the query."
    )
)
async def find_similar_products(
    ctx: RunContextWrapper[AgentContext],
    query: str,
    exclude_product_id: str = "",
) -> dict:
    """Find products similar to a given product."""
    print(f"🔍 find_similar_products called: '{query}' excluding '{exclude_product_id}'")

    results = search_products(query, limit=MAX_PRODUCTS + 1)

    # Exclude the source product
    results = [p for p in results if p.get("product_id") != exclude_product_id][:MAX_PRODUCTS]

    if not results:
        return {"found": False, "products": []}

    return {
        "found": True,
        "products": [format_product_for_agent(p) for p in results]
    }


# --------------------------------------------------
# Agent prompt — behaviour only, no product data in prompt
# --------------------------------------------------
AGENT_INSTRUCTIONS = """
You are Anna — the in-store assistant for Choosing Keeping in London.

YOUR PERSONALITY:
- Thoughtful, design-savvy stationery specialist with a calm London boutique feel
- Deep knowledge of paper goods, pens, notebooks, inks, and desk objects
- Warm, observant, quietly witty — never loud or salesy
- Honest about practicality, durability, and writing experience
- Concise and natural — like a real conversation across the counter
- Subtle literary/shopkeeper charm with understated British humour

TONE EXAMPLES:
- "Beautiful paper stock on this one. Fountain pens behave very well with it."
- "Dangerous little item. People come in for one notebook and leave reorganising their lives."
- "Excellent choice if you actually write every day, not just admire stationery online."
- "The binding’s solid. It survives being carried around London far better than most."
- "Lovely gift. Sensible too, which is rarer."
- "This pen has opinions about cheap paper."

TOOLS YOU HAVE:
- search_products_tool: search the catalogue by any query — use this whenever the customer asks about products
- get_product_by_id: look up a specific product by its ID
- find_similar_products: find accessories or related products
- show_product_card: display a product card to the customer — ALWAYS call this for every product you mention

HOW TO USE YOUR TOOLS:
1. When a customer asks about ANY product or category → call search_products_tool first
2. Never say "I don't have that in stock" without calling search_products_tool first
3. If a customer names a specific product → call get_product_by_id to confirm it exists
4. Never insert show_product_card firt in the response, it always has to come after some text response otherwise the user wont understand.
5. After finding products → always call show_product_card for each one you mention
6. If search returns nothing → say you couldn't find it and ask for more details (SKU, spelling, etc)

STORE KNOWLEDGE:
{knowledge_context}

CONVERSATION CONTEXT:
{conversation_context}

Respond naturally as Anna. Use your tools proactively — don't guess what's in stock.
"""


# --------------------------------------------------
# Chat Server
# --------------------------------------------------
class StarterChatServer(ChatKitServer):
    def __init__(self):
        self.store = MemoryStore()
        super().__init__(self.store)
        self._thread_state = {}

    def _get_state(self, thread_id: str) -> dict:
        if thread_id not in self._thread_state:
            self._thread_state[thread_id] = {
                "is_shopping": False,
                "all_shown_product_ids": set(),
                "shown_this_turn": set(),
                "last_discussed_products": [],
                "out_of_stock_ok": False,
                "last_query": "",
            }
        return self._thread_state[thread_id]

    def _cleanup_old_threads(self, max_threads: int = 500):
        if len(self._thread_state) > max_threads:
            oldest = list(self._thread_state.keys())[:-max_threads]
            for tid in oldest:
                del self._thread_state[tid]

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

        # Thread-scoped state
        thread_id = thread.id if thread else "anonymous"
        state = self._get_state(thread_id)
        self._cleanup_old_threads()

        # Pass server reference into request context so tools can update state
        if hasattr(agent_context, 'request_context') and isinstance(agent_context.request_context, dict):
            agent_context.request_context["server"] = self

        # Get last message
        last_message = ""
        if agent_input:
            last_msg_obj = agent_input[-1]
            if isinstance(last_msg_obj, dict) and "content" in last_msg_obj:
                last_message = str(last_msg_obj["content"])
            else:
                last_message = str(last_msg_obj)

        # -----------------------------
        # 1. Fast deterministic intent classification
        # -----------------------------
        intent = classify_intent(last_message, state["is_shopping"])
        state["is_shopping"] = intent["shopping_active"]
        state["out_of_stock_ok"] = intent["out_of_stock_ok"]

        # -----------------------------
        # 2. Knowledge retrieval — always runs, unified search
        # -----------------------------
        knowledge_blocks = retrieve_relevant_kb(last_message, top_k=8, min_similarity=0.25)
        knowledge_context = "\n\n---\n\n".join(knowledge_blocks) if knowledge_blocks else "No specific store information found for this query."

        # -----------------------------
        # 3. Conversation context summary
        # -----------------------------
        conversation_context = ""
        if state["last_discussed_products"]:
            conversation_context = f"Products discussed so far: {', '.join(state['last_discussed_products'])}."
        if state["last_query"]:
            conversation_context += f" Last search: '{state['last_query']}'."
        if not conversation_context:
            conversation_context = "This is the start of the conversation."

        # Update last query
        if not intent["is_followup"] and len(last_message.split()) > 2:
            state["last_query"] = last_message

        # -----------------------------
        # 4. Build agent with tools
        # -----------------------------
        agent = Agent(
            model=MODEL,
            name="Choosing Keeping Shopping Assistant",
            instructions=AGENT_INSTRUCTIONS.format(
                knowledge_context=knowledge_context,
                conversation_context=conversation_context,
            ),
            tools=[
                search_products_tool,
                get_product_by_id,
                find_similar_products,
                show_product_card,
            ]
        )

        print(f"🏪 Anna | thread={thread_id} | shopping={state['is_shopping']} | followup={intent['is_followup']}")

        # -----------------------------
        # 5. Stream response
        # -----------------------------
        result = Runner.run_streamed(agent, agent_input, context=agent_context)
        async for event in stream_agent_response(agent_context, result):
            yield event
