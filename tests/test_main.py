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


def test_order_replays_same_idempotency_key_without_second_stock_change(
    client: TestClient,
) -> None:
    headers = {**AUTH, "Idempotency-Key": "shop-order-1001"}
    body = {"lines": [{"sku": "ZK-BROEK-002", "quantity": 2}]}

    first = client.post("/orders", headers=headers, json=body)
    stock_after_first = client.get("/inventory/ZK-BROEK-002", headers=AUTH).json()["quantity"]
    replay = client.post("/orders", headers=headers, json=body)

    assert first.status_code == replay.status_code == 201
    assert replay.json() == first.json()
    assert "Idempotent-Replayed" not in first.headers
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert client.get("/inventory/ZK-BROEK-002", headers=AUTH).json()["quantity"] == stock_after_first


def test_order_rejects_idempotency_key_reused_with_different_body(client: TestClient) -> None:
    headers = {**AUTH, "Idempotency-Key": "shop-order-1002"}
    first = client.post(
        "/orders", headers=headers, json={"lines": [{"sku": "ZK-JAS-001", "quantity": 1}]}
    )
    conflict = client.post(
        "/orders", headers=headers, json={"lines": [{"sku": "ZK-JAS-001", "quantity": 2}]}
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert "different request body" in conflict.json()["detail"]
    assert client.get("/inventory/ZK-JAS-001", headers=AUTH).json()["quantity"] == 41


def test_idempotency_key_survives_application_restart() -> None:
    headers = {**AUTH, "Idempotency-Key": "shop-order-persistent"}
    body = {"lines": [{"sku": "ZK-TRUI-001", "quantity": 1}]}
    with TestClient(app) as first_client:
        first = first_client.post("/orders", headers=headers, json=body)

    with TestClient(app) as restarted_client:
        replay = restarted_client.post("/orders", headers=headers, json=body)
        stock = restarted_client.get("/inventory/ZK-TRUI-001", headers=AUTH)

    assert replay.json() == first.json()
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert stock.json()["quantity"] == 19


def test_orders_without_idempotency_key_keep_creating_orders(client: TestClient) -> None:
    body = {"lines": [{"sku": "ZK-TAS-001", "quantity": 1}]}
    first = client.post("/orders", headers=AUTH, json=body)
    second = client.post("/orders", headers=AUTH, json=body)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert client.get("/inventory/ZK-TAS-001", headers=AUTH).json()["quantity"] == 30


def test_concurrent_retries_with_same_key_create_one_order(client: TestClient) -> None:
    headers = {**AUTH, "Idempotency-Key": "shop-order-concurrent"}
    body = {"lines": [{"sku": "ZK-LAARS-001", "quantity": 2}]}

    def place_order(_request_number: int):
        return client.post("/orders", headers=headers, json=body)

    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(place_order, range(8)))

    assert {response.status_code for response in responses} == {201}
    assert len({response.json()["id"] for response in responses}) == 1
    assert sum(response.headers.get("Idempotent-Replayed") == "true" for response in responses) == 7
    assert client.get("/inventory/ZK-LAARS-001", headers=AUTH).json()["quantity"] == 8
    with database() as connection:
        assert connection.execute("SELECT COUNT(*) AS count FROM orders").fetchone()["count"] == 1


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
        headers={**AUTH, "Idempotency-Key": "order-before-reset"},
        json={"lines": [{"sku": "ZK-JAS-001", "quantity": 2}]},
    )
    result = client.post("/admin/seed", headers=AUTH)
    assert result.json() == {"products": 24, "orders": 0}
    assert client.get("/inventory/ZK-JAS-001", headers=AUTH).json()["quantity"] == 42
    assert client.get("/orders/1/status", headers=AUTH).status_code == 404
    after_reset = client.post(
        "/orders",
        headers={**AUTH, "Idempotency-Key": "order-before-reset"},
        json={"lines": [{"sku": "ZK-JAS-001", "quantity": 2}]},
    )
    assert after_reset.status_code == 201
    assert "Idempotent-Replayed" not in after_reset.headers
    assert client.get("/inventory/ZK-JAS-001", headers=AUTH).json()["quantity"] == 40


def test_generated_openapi_is_valid_and_documents_all_domains(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    validate(spec)
    for path in ("/articles", "/inventory", "/prices", "/orders/{order_id}/status"):
        assert path in spec["paths"]
    assert "APIKeyHeader" in spec["components"]["securitySchemes"]
    create_order = spec["paths"]["/orders"]["post"]
    idempotency_header = next(
        parameter for parameter in create_order["parameters"] if parameter["name"] == "Idempotency-Key"
    )
    assert idempotency_header["in"] == "header"
    assert "201" in create_order["responses"]
    assert "Idempotent-Replayed" in create_order["responses"]["201"]["headers"]
    assert "409" in create_order["responses"]
