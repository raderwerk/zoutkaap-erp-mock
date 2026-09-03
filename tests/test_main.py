from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_products() -> None:
    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 3
    assert {p["sku"] for p in products} == {"ZK-JAS-001", "ZK-BROEK-002", "ZK-MUTS-003"}


def test_get_product_not_found() -> None:
    response = client.get("/products/DOES-NOT-EXIST")
    assert response.status_code == 404


def test_get_stock() -> None:
    response = client.get("/stock/ZK-JAS-001")
    assert response.status_code == 200
    assert response.json()["stock"] == 42


def test_create_order_decrements_stock() -> None:
    before = client.get("/stock/ZK-BROEK-002").json()["stock"]
    response = client.post("/orders", json={"lines": [{"sku": "ZK-BROEK-002", "quantity": 2}]})
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "ontvangen"
    after = client.get("/stock/ZK-BROEK-002").json()["stock"]
    assert after == before - 2


def test_create_order_insufficient_stock() -> None:
    response = client.post("/orders", json={"lines": [{"sku": "ZK-MUTS-003", "quantity": 1}]})
    assert response.status_code == 409


def test_create_order_unknown_product() -> None:
    response = client.post("/orders", json={"lines": [{"sku": "NOPE", "quantity": 1}]})
    assert response.status_code == 404


def test_get_order_not_found() -> None:
    response = client.get("/orders/999999")
    assert response.status_code == 404


def test_openapi_spec_available() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "Zoutkaap ERP-nabootsing"
