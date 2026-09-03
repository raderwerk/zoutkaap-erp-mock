"""Runnable Zoutkaap ERP simulation with generated OpenAPI documentation."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

API_KEY = os.getenv("ZOUTKAAP_API_KEY", "zoutkaap-local-demo-key")
DATABASE_PATH = Path(os.getenv("ZOUTKAAP_DATABASE", "instance/zoutkaap.sqlite3"))

PRODUCTS = (
    ("ZK-JAS-001", "Zoutkaap Stormjas Noord", 18900, 42),
    ("ZK-JAS-002", "Zoutkaap Stormjas Zuid", 19900, 18),
    ("ZK-JAS-003", "Zoutkaap Regenjas Duin", 15900, 25),
    ("ZK-JAS-004", "Zoutkaap Regenjas Haven", 16900, 11),
    ("ZK-BROEK-001", "Zoutkaap Waterbroek Noord", 14900, 17),
    ("ZK-BROEK-002", "Zoutkaap Waterbroek Zuid", 14900, 23),
    ("ZK-BROEK-003", "Zoutkaap Regenbroek Duin", 11900, 30),
    ("ZK-BROEK-004", "Zoutkaap Regenbroek Haven", 12900, 9),
    ("ZK-TRUI-001", "Zoutkaap Zeetrui Blauw", 8900, 20),
    ("ZK-TRUI-002", "Zoutkaap Zeetrui Zand", 8900, 16),
    ("ZK-TRUI-003", "Zoutkaap Fleece Eb", 7900, 14),
    ("ZK-TRUI-004", "Zoutkaap Fleece Vloed", 7900, 12),
    ("ZK-MUTS-001", "Zoutkaap Muts Noord", 2900, 36),
    ("ZK-MUTS-002", "Zoutkaap Muts Zuid", 2900, 28),
    ("ZK-MUTS-003", "Zoutkaap Muts Duin", 2900, 0),
    ("ZK-MUTS-004", "Zoutkaap Muts Haven", 2900, 41),
    ("ZK-LAARS-001", "Zoutkaap Laarzen Eb", 9900, 10),
    ("ZK-LAARS-002", "Zoutkaap Laarzen Vloed", 9900, 8),
    ("ZK-LAARS-003", "Zoutkaap Laarzen Wad", 10900, 6),
    ("ZK-LAARS-004", "Zoutkaap Laarzen Kaap", 10900, 4),
    ("ZK-TAS-001", "Zoutkaap Droogtas 10L", 3900, 32),
    ("ZK-TAS-002", "Zoutkaap Droogtas 20L", 4900, 24),
    ("ZK-TAS-003", "Zoutkaap Weekender", 6900, 13),
    ("ZK-TAS-004", "Zoutkaap Rugtas", 7900, 15),
)


class Product(BaseModel):
    """An ERP article."""

    sku: str
    name: str


class Stock(BaseModel):
    """Current inventory for an article."""

    sku: str
    quantity: int = Field(ge=0)


class Price(BaseModel):
    """Current consumer price, represented without floating-point rounding."""

    sku: str
    amount_cents: int = Field(ge=0)
    currency: Literal["EUR"] = "EUR"


class OrderLine(BaseModel):
    sku: str
    quantity: int = Field(gt=0)


class OrderRequest(BaseModel):
    lines: list[OrderLine] = Field(min_length=1)


class Order(BaseModel):
    id: int
    lines: list[OrderLine]
    status: Literal["received"] = "received"


class OrderStatus(BaseModel):
    order_id: int
    status: Literal["received"]


class SeedResult(BaseModel):
    products: int
    orders: int


def set_database_path(path: Path) -> None:
    """Override the database location (used by isolated test runs)."""
    global DATABASE_PATH
    DATABASE_PATH = path


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()


def seed_database() -> SeedResult:
    """Restore all demo data and remove orders in one transaction."""
    with database() as connection:
        connection.executescript(
            """
            DROP TABLE IF EXISTS order_lines;
            DROP TABLE IF EXISTS idempotency_keys;
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS products;
            CREATE TABLE products (
                sku TEXT PRIMARY KEY, name TEXT NOT NULL,
                price_cents INTEGER NOT NULL, stock INTEGER NOT NULL
            );
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT, status TEXT NOT NULL
            );
            CREATE TABLE order_lines (
                order_id INTEGER NOT NULL, sku TEXT NOT NULL, quantity INTEGER NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id)
            );
            CREATE TABLE idempotency_keys (
                key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, response_json TEXT NOT NULL
            );
            """
        )
        connection.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", PRODUCTS)
    return SeedResult(products=len(PRODUCTS), orders=0)


def initialize_database() -> None:
    with database() as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'products'"
        ).fetchone()
        if exists is not None:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    key TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL
                )
                """
            )
    if exists is None:
        seed_database()


api_key_header = APIKeyHeader(
    name="X-API-Key",
    description="Development API key documented in the project README.",
    auto_error=False,
)


def require_api_key(key: Annotated[str | None, Security(api_key_header)]) -> None:
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def inject_test_error(
    test_status: Annotated[
        Literal["404", "429", "500"] | None,
        Header(alias="X-Test-Status", description="Force a 404, 429, or 500 test response."),
    ] = None,
) -> None:
    if test_status is None:
        return
    status_code = int(test_status)
    headers = {"Retry-After": "2"} if status_code == 429 else None
    raise HTTPException(status_code=status_code, detail="Forced test response", headers=headers)


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


app = FastAPI(
    title="Zoutkaap ERP simulation",
    description="Fictitious REST ERP for articles, inventory, prices, and order status.",
    version="1.0.0",
    lifespan=lifespan,
)
router = APIRouter(
    dependencies=[Depends(require_api_key), Depends(inject_test_error)],
    responses={401: {"description": "Invalid or missing API key"}},
)


@app.get("/health", tags=["system"], summary="Service health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/articles", response_model=list[Product], tags=["articles"])
def list_articles() -> list[Product]:
    """List all 24 ERP articles."""
    with database() as connection:
        rows = connection.execute("SELECT sku, name FROM products ORDER BY sku").fetchall()
    return [Product(**dict(row)) for row in rows]


@router.get("/articles/{sku}", response_model=Product, tags=["articles"])
def get_article(sku: str) -> Product:
    with database() as connection:
        row = connection.execute("SELECT sku, name FROM products WHERE sku = ?", (sku,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Article {sku} not found")
    return Product(**dict(row))


@router.get("/inventory", response_model=list[Stock], tags=["inventory"])
def list_inventory() -> list[Stock]:
    with database() as connection:
        rows = connection.execute(
            "SELECT sku, stock AS quantity FROM products ORDER BY sku"
        ).fetchall()
    return [Stock(**dict(row)) for row in rows]


@router.get("/inventory/{sku}", response_model=Stock, tags=["inventory"])
def get_inventory(sku: str) -> Stock:
    with database() as connection:
        row = connection.execute(
            "SELECT sku, stock AS quantity FROM products WHERE sku = ?", (sku,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Article {sku} not found")
    return Stock(**dict(row))


@router.get("/prices", response_model=list[Price], tags=["prices"])
def list_prices() -> list[Price]:
    with database() as connection:
        rows = connection.execute(
            "SELECT sku, price_cents AS amount_cents FROM products ORDER BY sku"
        ).fetchall()
    return [Price(**dict(row)) for row in rows]


@router.get("/prices/{sku}", response_model=Price, tags=["prices"])
def get_price(sku: str) -> Price:
    with database() as connection:
        row = connection.execute(
            "SELECT sku, price_cents AS amount_cents FROM products WHERE sku = ?", (sku,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Article {sku} not found")
    return Price(**dict(row))


@router.post(
    "/orders",
    response_model=Order,
    status_code=201,
    tags=["orders"],
    responses={
        201: {
            "description": "Order created, or the original response replayed.",
            "headers": {
                "Idempotent-Replayed": {
                    "description": "True when this is a replay of an earlier request.",
                    "schema": {"type": "boolean"},
                }
            },
        },
        409: {
            "description": "Insufficient stock, or an idempotency key used with another body."
        },
    },
)
def create_order(
    request: OrderRequest,
    response: Response,
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Retry key. Reusing it with the same body replays the original response.",
        ),
    ] = None,
) -> Order:
    request_json = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(request_json.encode()).hexdigest()

    with database() as connection:
        # Reserve the SQLite write lock before checking the key, so concurrent retries
        # cannot both observe an absent key and create separate orders.
        connection.execute("BEGIN IMMEDIATE")
        if idempotency_key is not None:
            stored = connection.execute(
                "SELECT request_hash, response_json FROM idempotency_keys WHERE key = ?",
                (idempotency_key,),
            ).fetchone()
            if stored is not None:
                if stored["request_hash"] != request_hash:
                    raise HTTPException(
                        status_code=409,
                        detail="Idempotency-Key was already used with a different request body",
                    )
                response.headers["Idempotent-Replayed"] = "true"
                return Order.model_validate_json(stored["response_json"])

        quantities: dict[str, int] = {}
        for line in request.lines:
            quantities[line.sku] = quantities.get(line.sku, 0) + line.quantity
        for sku, quantity in quantities.items():
            cursor = connection.execute(
                """
                UPDATE products
                SET stock = stock - ?
                WHERE sku = ? AND stock >= ?
                """,
                (quantity, sku, quantity),
            )
            if cursor.rowcount == 0:
                exists = connection.execute(
                    "SELECT 1 FROM products WHERE sku = ?", (sku,)
                ).fetchone()
                if exists is None:
                    raise HTTPException(status_code=404, detail=f"Article {sku} not found")
                raise HTTPException(status_code=409, detail=f"Insufficient stock for {sku}")
        cursor = connection.execute("INSERT INTO orders(status) VALUES ('received')")
        order_id = cursor.lastrowid
        assert order_id is not None
        for line in request.lines:
            connection.execute(
                "INSERT INTO order_lines VALUES (?, ?, ?)", (order_id, line.sku, line.quantity)
            )
        order = Order(id=order_id, lines=request.lines)
        if idempotency_key is not None:
            connection.execute(
                "INSERT INTO idempotency_keys VALUES (?, ?, ?)",
                (idempotency_key, request_hash, order.model_dump_json()),
            )
    return order


@router.get("/orders/{order_id}/status", response_model=OrderStatus, tags=["orders"])
def get_order_status(order_id: int) -> OrderStatus:
    with database() as connection:
        row = connection.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return OrderStatus(order_id=order_id, status=row["status"])


@router.post("/admin/seed", response_model=SeedResult, tags=["system"])
def reset_seed_data() -> SeedResult:
    """Restore the exact initial dataset and delete every order."""
    return seed_database()


app.include_router(router)
