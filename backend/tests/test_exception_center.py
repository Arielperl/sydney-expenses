from datetime import datetime
from decimal import Decimal

from app.models.sale import DocumentStatus, Sale, SaleStatus
from app.services.exception_center import build_exception_center


def _add_sale(db_session, **overrides):
    defaults = dict(
        customer_name="Demo Customer",
        customer_contact="demo@example.com",
        service_name="Consulting",
        gross_amount=Decimal("100.00"),
        net_amount=Decimal("100.00"),
        currency="ILS",
        occurred_at=datetime(2026, 3, 15, 10, 0, 0),
        status=SaleStatus.SUCCEEDED,
        document_status=DocumentStatus.NOT_REQUIRED,
    )
    defaults.update(overrides)
    sale = Sale(**defaults)
    db_session.add(sale)
    db_session.commit()
    return sale


def test_pending_documents_only_includes_succeeded_sales(db_session):
    pending = _add_sale(db_session, document_status=DocumentStatus.PENDING)
    _add_sale(db_session, document_status=DocumentStatus.PENDING, status=SaleStatus.PENDING)
    _add_sale(db_session, document_status=DocumentStatus.ISSUED)

    center = build_exception_center(db_session)

    assert [s.id for s in center.pending_documents] == [pending.id]


def test_document_failures(db_session):
    failed = _add_sale(db_session, document_status=DocumentStatus.FAILED)
    _add_sale(db_session, document_status=DocumentStatus.ISSUED)

    center = build_exception_center(db_session)

    assert [s.id for s in center.document_failures] == [failed.id]


def test_refunds_needing_attention(db_session):
    refunded = _add_sale(db_session, status=SaleStatus.REFUNDED, refunded_amount=Decimal("100.00"))
    partially_refunded = _add_sale(db_session, status=SaleStatus.PARTIALLY_REFUNDED, refunded_amount=Decimal("40.00"))
    _add_sale(db_session, status=SaleStatus.SUCCEEDED)

    center = build_exception_center(db_session)

    ids = {s.id for s in center.refunds_needing_attention}
    assert ids == {refunded.id, partially_refunded.id}


def test_incomplete_details_flags_missing_customer_contact(db_session):
    incomplete = _add_sale(db_session, customer_contact=None)
    _add_sale(db_session, customer_contact="demo@example.com")

    center = build_exception_center(db_session)

    assert [s.id for s in center.incomplete_details] == [incomplete.id]


def test_exception_center_route(client):
    client.post(
        "/api/sales",
        json={
            "customer_name": "No Contact",
            "service_name": "Consulting",
            "gross_amount": "50.00",
            "currency": "ILS",
            "occurred_at": "2026-03-15T10:00:00",
        },
    )

    response = client.get("/api/exceptions")

    assert response.status_code == 200
    body = response.json()
    assert len(body["incomplete_details"]) == 1
    assert body["incomplete_details"][0]["customer_name"] == "No Contact"
