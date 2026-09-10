import io

from tests.conftest import VALID_PNG_BYTES


def _create_sale(client) -> str:
    response = client.post(
        "/api/sales",
        json={
            "customer_name": "Demo Customer",
            "service_name": "Consulting",
            "gross_amount": "60.00",
            "currency": "ILS",
            "occurred_at": "2026-01-01T10:00:00",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_import_historical_document_attaches_it_to_the_named_sale(client):
    sale_id = _create_sale(client)

    response = client.post(
        "/api/documents/import",
        params={"sale_id": sale_id},
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sale_id"] == sale_id
    assert body["extraction_succeeded"] is True
    assert body["document_status"] == "issued"
    assert body["document_url"].startswith("/uploads/")

    sale = client.get(f"/api/sales/{sale_id}").json()
    assert sale["document_status"] == "issued"
    assert sale["document_url"] == body["document_url"]


def test_import_document_for_unknown_sale_returns_404(client):
    response = client.post(
        "/api/documents/import",
        params={"sale_id": "does-not-exist"},
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    assert response.status_code == 404


def test_import_document_never_creates_a_new_sale(client):
    sale_id = _create_sale(client)

    client.post(
        "/api/documents/import",
        params={"sale_id": sale_id},
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )

    all_sales = client.get("/api/sales").json()
    assert [s["id"] for s in all_sales] == [sale_id]


def test_import_document_rejects_invalid_image(client):
    sale_id = _create_sale(client)

    response = client.post(
        "/api/documents/import",
        params={"sale_id": sale_id},
        files={"file": ("receipt.png", io.BytesIO(b"not an image"), "image/png")},
    )

    assert response.status_code == 422
