
import mysql.connector
from typing import Optional, Dict
from pprint import pprint  # nicer printing

def fetch_products_from_db(category_filter: Optional[str] = None) -> Dict[str, dict]:
    """
    Fetch products from MySQL optionally filtered by category.
    Returns a dictionary suitable for ChatKit agent consumption.
    """
    # Connect to MySQL
    db = mysql.connector.connect(
        host="localhost",
        port=3306,
        user="chatbotuser",  # your MySQL username
        password="StrongPassword123!",  # your MySQL password
        database="ecommerce_poc"
    )

    cursor = db.cursor(dictionary=True)

    # Base SQL query
    sql = """
        SELECT sku, title, description, price, currency, image_url, product_url
        FROM products
        WHERE is_active = 1
    """
    params = ()

    # Optional category filter
    if category_filter:
        sql += " AND title LIKE %s"
        params = (f"%{category_filter}%",)

    # Execute query
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    cursor.close()
    db.close()

    # Convert to dictionary format for ChatKit
    product_dict = {}
    
    for i, row in enumerate(rows):
        # Make key unique by appending the row index
        key = f"{row['sku'].lower().replace(' ', '_').replace('-', '_')}_{i}"
        product_dict[key] = {
            "labels": ["product"] + row["title"].lower().split()[:3],
            "title": row["title"],
            "description": row["description"],
            "price": float(row["price"]),
            "currency": row["currency"],
            "image_url": row["image_url"],
            "product_url": row["product_url"],
        }

    # Print all products nicely
    print("All products fetched from DB:")
    print(product_dict)

    return product_dict


def product_label_context():
    """Generate context string listing all product labels for ChatKit agent."""
    products = fetch_products_from_db()
    labels = set()
    for product in products.values():
        labels.update(product["labels"])
    label_list = ", ".join(sorted(labels))
    context = f"The available product labels are: {label_list}."
    print("Product label context:")
    print(context)
    return context