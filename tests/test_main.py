from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openapi_spec_validator import validate

from app.main import API_KEY, app, database, seed_database, set_database_path

AUTH = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def isolated_database(tmp_path: Path) -> None:
    set_database_path(tmp_path / "erp.sqlite3")
    seed_database()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_business_endpoint_requires_api_key(client: TestClient) -> None:
    assert client.get("/articles").status_code == 401
    assert client.get("/articles", headers={"X-API-Key": "wrong"}).status_code == 401


def test_seed_contains_24_articles_inventory_and_prices(client: TestClient) -> None:
    articles = client.get("/articles", headers=AUTH)
    inventory = client.get("/inventory", headers=AUTH)
    prices = client.get("/prices", headers=AUTH)
    assert articles.status_code == inventory.status_code == prices.status_code == 200
    assert len(articles.json()) == len(inventory.json()) == len(prices.json()) == 24
    assert prices.json()[0]["currency"] == "EUR"


def test_article_not_found(client: TestClient) -> None:
    response = client.get("/articles/DOES-NOT-EXIST", headers=AUTH)
    assert response.status_code == 404


def test_order_status_and_inventory_change(client: TestClient) -> None:
    before = client.get("/inventory/ZK-BROEK-002", headers=AUTH).json()["quantity"]
    created = client.post(
        "/orders",
        headers=AUTH,
        json={"lines": [{"sku": "ZK-BROEK-002", "quantity": 2}]},
    )
    assert created.status_code == 201
    order_id = created.json()["id"]
    status = client.get(f"/orders/{order_id}/status", headers=AUTH)
    assert status.json() == {"order_id": order_id, "status": "received"}
    after = client.get("/inventory/ZK-BROEK-002", headers=AUTH).json()["quantity"]
    assert after == before - 2


def test_order_rejects_insufficient_stock(client: TestClient) -> None:
    response = client.post(
        "/orders", headers=AUTH, json={"lines": [{"sku": "ZK-MUTS-003", "quantity": 1}]}
    )
    assert response.status_code == 409


def test_order_combines_duplicate_lines_before_stock_check(client: TestClient) -> None:
    response = client.post(
        "/orders",
        headers=AUTH,
        json={
            "lines": [
                {"sku": "ZK-LAARS-004", "quantity": 3},
                {"sku": "ZK-LAARS-004", "quantity": 3},
            ]
        },
    )
    assert response.status_code == 409
    assert client.get("/inventory/ZK-LAARS-004", headers=AUTH).json()["quantity"] == 4


def test_concurrent_orders_cannot_make_inventory_negative(client: TestClient) -> None:
    sku = "ZK-LAARS-004"

    def place_order(_request_number: int) -> int:
        return client.post(
            "/orders", headers=AUTH, json={"lines": [{"sku": sku, "quantity": 1}]}
        ).status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(place_order, range(12)))

    assert statuses.count(201) == 4
    assert statuses.count(409) == 8
    inventory = client.get(f"/inventory/{sku}", headers=AUTH)
    assert inventory.status_code == 200
    assert inventory.json()["quantity"] == 0

    with database() as connection:
        stored_stock = connection.execute(
            "SELECT stock FROM products WHERE sku = ?", (sku,)
        ).fetchone()["stock"]
    assert stored_stock == 0


@pytest.mark.parametrize("status", [404, 429, 500])
def test_forced_errors(client: TestClient, status: int) -> None:
    response = client.get("/articles", headers={**AUTH, "X-Test-Status": str(status)})
    assert response.status_code == status
    if status == 429:
        assert response.headers["Retry-After"] == "2"


def test_seed_restores_state(client: TestClient) -> None:
    client.post(
        "/orders",
        headers=AUTH,
        json={"lines": [{"sku": "ZK-JAS-001", "quantity": 2}]},
    )
    result = client.post("/admin/seed", headers=AUTH)
    assert result.json() == {"products": 24, "orders": 0}
    assert client.get("/inventory/ZK-JAS-001", headers=AUTH).json()["quantity"] == 42
    assert client.get("/orders/1/status", headers=AUTH).status_code == 404


def test_generated_openapi_is_valid_and_documents_all_domains(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    validate(spec)
    for path in ("/articles", "/inventory", "/prices", "/orders/{order_id}/status"):
        assert path in spec["paths"]
    assert "APIKeyHeader" in spec["components"]["securitySchemes"]
