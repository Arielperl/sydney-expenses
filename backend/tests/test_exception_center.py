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


def test_document_states_never_create_attention_tasks(db_session):
    _add_sale(db_session, document_status=DocumentStatus.PENDING)
    _add_sale(db_session, document_status=DocumentStatus.FAILED)
    _add_sale(db_session, document_status=DocumentStatus.WAITING_AUTOMATIC)

    center = build_exception_center(db_session)

    assert center.attention_count == 0
    assert center.pending_documents_count == 0
    assert center.document_failures_count == 0
    assert center.pending_documents == []
    assert center.document_failures == []


def test_recorded_refunds_do_not_create_permanent_tasks(db_session):
    refunded = _add_sale(db_session, status=SaleStatus.REFUNDED, refunded_amount=Decimal("100.00"))
    partially_refunded = _add_sale(db_session, status=SaleStatus.PARTIALLY_REFUNDED, refunded_amount=Decimal("40.00"))
    _add_sale(db_session, status=SaleStatus.SUCCEEDED)

    center = build_exception_center(db_session)

    assert center.refunds_needing_attention == []
    assert center.refunds_needing_attention_count == 0
    assert center.attention_count == 0
    assert refunded.status == SaleStatus.REFUNDED
    assert partially_refunded.status == SaleStatus.PARTIALLY_REFUNDED


def test_only_ambiguous_legacy_tax_needs_details_review(db_session):
    _add_sale(db_session, customer_contact=None)
    incomplete = _add_sale(db_session, tax_treatment_needs_review=True)

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
    assert body["attention_count"] == 0
    assert body["pending_documents_count"] == 0
    assert body["incomplete_details_count"] == 0
    assert body["incomplete_details"] == []


def test_attention_count_is_not_limited(db_session):
    incomplete = _add_sale(
        db_session,
        tax_treatment_needs_review=True,
        document_status=DocumentStatus.PENDING,
    )
    for index in range(25):
        _add_sale(
            db_session,
            customer_name=f"Customer {index}",
            tax_treatment_needs_review=True,
        )

    center = build_exception_center(db_session, limit=20)

    assert center.pending_documents == []
    assert len(center.incomplete_details) == 20
    assert incomplete.id in {sale.id for sale in center.incomplete_details}
    assert center.attention_count == 26
    assert center.pending_documents_count == 0
    assert center.incomplete_details_count == 26
