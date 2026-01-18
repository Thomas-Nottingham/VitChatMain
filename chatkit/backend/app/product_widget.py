from chatkit.widgets import WidgetRoot, WidgetTemplate

# Load the widget template
product_widget_template = WidgetTemplate.from_file("product_container.widget")


def build_product_widget(product_data: dict) -> WidgetRoot:
    return product_widget_template.build(
        data={
            "productUrl": product_data.get("product_url", "https://example.com"),
            "imageUrl": product_data.get(
                "image_url",
                "https://upload.wikimedia.org/wikipedia/commons/f/f5/No-Image-Placeholder-landscape.svg"
            ),
            "alt": product_data.get("title", "Product image"),
            "buttonLabel": "View product"
        }
    )


def product_widget_copy_text(product_data: dict) -> str:
    title = product_data.get("title", "this product")
    url = product_data.get("product_url", "")
    return f"Check out {title} {url}".strip()

