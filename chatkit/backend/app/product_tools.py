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
# async def show_product_card(
#     ctx: RunContextWrapper[AgentContext],
#     product_id: str,
# ):
#     # Use PRODUCT_KNOWLEDGE here
#     product = kb_index.PRODUCT_KNOWLEDGE.get(product_id)

#     if not product:
#         return {"error": f"No product found with id '{product_id}'"}

#     # Build and stream the widget
#     widget = build_product_widget(product)
    
#     await ctx.context.stream_widget(
#         widget,
#         copy_text=product_widget_copy_text(product),
#     )

#     return {"status": "success", "id": product_id}
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

