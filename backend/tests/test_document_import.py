import io
import uuid
from datetime import datetime
from decimal import Decimal

from PIL import Image

from app.database import SessionLocal
from app.models.sale import DocumentStatus, Sale, SaleSource, SaleStatus
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


def test_manual_attachment_overrides_a_sale_waiting_on_an_automatic_document(client):
    """Manual historical attachment stays available as a fallback even for
    a sale currently in the automatic waiting_automatic state (e.g. a
    Grow/Cardcom sale whose provider document hasn't arrived, or never
    will for this particular transaction)."""
    with SessionLocal() as db:
        sale = Sale(
            id=str(uuid.uuid4()),
            source_provider="grow:conn-1",
            source=SaleSource.WEBHOOK,
            status=SaleStatus.SUCCEEDED,
            occurred_at=datetime(2026, 1, 1, 10, 0, 0),
            customer_name="Grow Customer",
            service_name="Grow sale",
            gross_amount=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            currency="ILS",
            document_status=DocumentStatus.WAITING_AUTOMATIC,
        )
        db.add(sale)
        db.commit()
        sale_id = sale.id

    response = client.post(
        "/api/documents/import",
        params={"sale_id": sale_id},
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["document_status"] == "issued"

    sale = client.get(f"/api/sales/{sale_id}").json()
    assert sale["document_status"] == "issued"
    assert sale["document_url"] is not None


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


def test_import_document_rejects_decompression_bomb_dimensions(client, monkeypatch):
    sale_id = _create_sale(client)
    image_bytes = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(image_bytes, format="PNG")

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_pixels", 100)
    response = client.post(
        "/api/documents/import",
        params={"sale_id": sale_id},
        files={"file": ("receipt.png", io.BytesIO(image_bytes.getvalue()), "image/png")},
    )

    assert response.status_code == 422
