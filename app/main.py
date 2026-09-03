"""Zoutkaap ERP-nabootsing.

Minimale, echte REST-service die de drie kerndomeinen van het Zoutkaap-ERP
naspeelt: producten, voorraad en orders. De OpenAPI-beschrijving wordt door
FastAPI automatisch gegenereerd op `/openapi.json` (interactief op `/docs`).

Dit is bewust een skelet. De echte omvang (foutscenario's, paginering,
authenticatie) komt uit de bijbehorende Linear-issues (zie AGENTS.md), niet
uit dit bootstrap-bestand.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Zoutkaap ERP-nabootsing",
    description=(
        "Demonstratiebedrijf van Raderwerk. Dit bedrijf bestaat niet. "
        "Nagebouwde ERP-koppeling voor producten, voorraad en orders."
    ),
    version="0.1.0",
)


class Product(BaseModel):
    sku: str
    name: str
    price_cents: int = Field(ge=0)
    stock: int = Field(ge=0)


class OrderLine(BaseModel):
    sku: str
    quantity: int = Field(gt=0)


class OrderRequest(BaseModel):
    lines: list[OrderLine]


class Order(BaseModel):
    id: int
    lines: list[OrderLine]
    status: str


class Stock(BaseModel):
    sku: str
    stock: int = Field(ge=0)


# In-memory seeddata. Geen database in dit skelet; de echte voorraadsync en
# opwekbare foutscenario's zijn separaat werk (zie AGENTS.md).
_PRODUCTS: dict[str, Product] = {
    "ZK-JAS-001": Product(sku="ZK-JAS-001", name="Zoutkaap regenjas", price_cents=18900, stock=42),
    "ZK-BROEK-002": Product(sku="ZK-BROEK-002", name="Zoutkaap waterbroek", price_cents=14900, stock=17),
    "ZK-MUTS-003": Product(sku="ZK-MUTS-003", name="Zoutkaap muts", price_cents=2900, stock=0),
}
_ORDERS: dict[int, Order] = {}
_next_order_id = 1


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/products", response_model=list[Product])
def list_products() -> list[Product]:
    return list(_PRODUCTS.values())


@app.get("/products/{sku}", response_model=Product)
def get_product(sku: str) -> Product:
    product = _PRODUCTS.get(sku)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {sku} niet gevonden")
    return product


@app.get("/stock/{sku}", response_model=Stock)
def get_stock(sku: str) -> Stock:
    product = _PRODUCTS.get(sku)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {sku} niet gevonden")
    return Stock(sku=sku, stock=product.stock)


@app.post("/orders", response_model=Order, status_code=201)
def create_order(order_request: OrderRequest) -> Order:
    global _next_order_id

    if not order_request.lines:
        raise HTTPException(status_code=400, detail="Order moet minimaal één regel bevatten")

    for line in order_request.lines:
        product = _PRODUCTS.get(line.sku)
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product {line.sku} niet gevonden")
        if product.stock < line.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Onvoldoende voorraad voor {line.sku}: {product.stock} beschikbaar",
            )

    for line in order_request.lines:
        _PRODUCTS[line.sku].stock -= line.quantity

    order = Order(id=_next_order_id, lines=order_request.lines, status="ontvangen")
    _ORDERS[order.id] = order
    _next_order_id += 1
    return order


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: int) -> Order:
    order = _ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} niet gevonden")
    return order
