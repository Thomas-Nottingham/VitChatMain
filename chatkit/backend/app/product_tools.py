from agents import function_tool, RunContextWrapper
from chatkit.agents import AgentContext

# IMPORTANT: Import the knowledge dictionary from your server file 

from .product_widget import build_product_widget, product_widget_copy_text
 
from . import kb_index



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
    product = kb_index.PRODUCT_KNOWLEDGE.get(product_id)
    print(f"🔍 show_product_card called with: {product_id}")
    print(f"🔍 product found: {product is not None}")

    if not product:
        return {"error": f"No product found with id '{product_id}'"}

    try:
        widget = build_product_widget(product)
        await ctx.context.stream_widget(
            widget,
            copy_text=product_widget_copy_text(product),
        )
        print(f"✅ Widget streamed successfully for {product_id}")
        return {"status": "success", "id": product_id}
    except Exception as e:
        print(f"❌ Widget error for {product_id}: {e}")
        return {"error": str(e)}
    
    
# from agents import function_tool, RunContextWrapper
# from chatkit.agents import AgentContext
# from .product_widget import build_product_widget, product_widget_copy_text
# from . import kb_index


# @function_tool(
#     description_override=(
#         "Show a product card for a specific product.\n"
#         "- `product_id`: ID or key of the product to display (e.g., home001).\n"
#         "Returns a marker string like {{CARD:home001}} — paste it verbatim into your response "
#         "immediately after the product name. Do NOT write the marker yourself; always call this tool."
#     )
# )
# async def show_product_card(
#     ctx: RunContextWrapper[AgentContext],
#     product_id: str,
# ) -> str:
#     product = kb_index.PRODUCT_KNOWLEDGE.get(product_id)
#     print(f"🔍 show_product_card called with: {product_id}")
#     print(f"🔍 product found: {product is not None}")

#     if not product:
#         print(f"❌ No product found for {product_id}")
#         return ""

#     marker = "{{" + f"CARD:{product_id}" + "}}"
#     print(f"✅ Returning marker: {marker}")
#     return marker


# async def render_card_event(product_id: str, agent_context: AgentContext):
#     """
#     Called by _stream_with_inline_cards in server.py when it encounters a
#     {{CARD:product_id}} marker in the agent's text stream.
#     Builds and streams the actual widget event at that position.
#     """
#     if not product_id:
#         print("❌ render_card_event: empty product_id, skipping")
#         return None

#     product = kb_index.PRODUCT_KNOWLEDGE.get(product_id)
#     if not product:
#         print(f"❌ render_card_event: no product found for '{product_id}'")
#         return None

#     try:
#         widget = build_product_widget(product)
#         event = await agent_context.stream_widget(
#             widget,
#             copy_text=product_widget_copy_text(product),
#         )
#         print(f"✅ Card event rendered for {product_id}")
#         return event
#     except Exception as e:
#         print(f"❌ render_card_event error for {product_id}: {e}")
#         return None