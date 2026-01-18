"""FastAPI entrypoint for the ChatKit starter backend."""

from __future__ import annotations

from chatkit.server import StreamingResult
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .server import StarterChatServer
from dotenv import load_dotenv
import os


from .db import fetch_products_from_db, product_label_context

from fastapi.staticfiles import StaticFiles

# This tells FastAPI that any request starting with "/static" 
# should look inside the "chatkit/backend/app/static" folder.


load_dotenv()  # loads .env file
print("OPENAI_API_KEY =", os.environ.get("OPENAI_API_KEY"))
app = FastAPI(title="ChatKit Starter API")

# Get the absolute path of the directory containing main.py
current_dir = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(current_dir, "static")

# Mount using the absolute path to prevent "Directory does not exist" errors
app.mount("/static", StaticFiles(directory=static_path), name="static")

origins = [
    "http://localhost:3000", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chatkit_server = StarterChatServer()


@app.post("/chatkit")
async def chatkit_endpoint(request: Request) -> Response:
    """Proxy the ChatKit web component payload to the server implementation."""
    payload = await request.body()
    result = await chatkit_server.process(payload, {"request": request})

    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if hasattr(result, "json"):
        return Response(content=result.json, media_type="application/json")
    return JSONResponse(result)

@app.get("/products")
async def get_products(category: str | None = None):
    products = fetch_products_from_db(category_filter=category)
    context = product_label_context()
    
    
    # Print to console (VS Code terminal) for debugging
    print("Products fetched from DB:")
    print(products)

     
    print(context)
    
    return products
