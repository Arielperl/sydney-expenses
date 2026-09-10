from datetime import date, datetime


def _sale_payload(**overrides) -> dict:
    payload = {
        "customer_name": "Demo Customer",
        "service_name": "Consulting session",
        "gross_amount": "100.00",
        "currency": "ILS",
        "occurred_at": datetime.combine(date.today(), datetime.min.time()).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_manual_sale_creation_records_creation_and_payment_events(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    events = client.get(f"/api/sales/{created['id']}/events").json()
    event_types = [e["event_type"] for e in events]

    assert "sale_created_manually" in event_types
    assert "payment_succeeded" in event_types
    assert "document_issuance_attempted" in event_types
    assert "document_issued" in event_types
    assert all(e["sale_id"] == created["id"] for e in events)


def test_events_are_returned_in_chronological_order(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    events = client.get(f"/api/sales/{created['id']}/events").json()
    timestamps = [e["created_at"] for e in events]

    assert timestamps == sorted(timestamps)


def test_full_refund_records_a_refund_full_event(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    client.post(f"/api/sales/{created['id']}/refund", json={})

    events = client.get(f"/api/sales/{created['id']}/events").json()
    refund_events = [e for e in events if e["event_type"] == "refund_full"]
    assert len(refund_events) == 1
    assert refund_events[0]["event_metadata"]["currency"] == "ILS"


def test_partial_refund_records_a_refund_partial_event(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    client.post(f"/api/sales/{created['id']}/refund", json={"amount": "10.00"})

    events = client.get(f"/api/sales/{created['id']}/events").json()
    refund_events = [e for e in events if e["event_type"] == "refund_partial"]
    assert len(refund_events) == 1
    assert refund_events[0]["event_metadata"]["amount"] == "10.00"


def test_refunding_an_already_fully_refunded_sale_does_not_duplicate_events(client):
    created = client.post("/api/sales", json=_sale_payload()).json()
    client.post(f"/api/sales/{created['id']}/refund", json={})

    client.post(f"/api/sales/{created['id']}/refund", json={})  # idempotent no-op

    events = client.get(f"/api/sales/{created['id']}/events").json()
    refund_events = [e for e in events if e["event_type"] == "refund_full"]
    assert len(refund_events) == 1


def test_editing_sale_details_records_an_edit_event_with_field_names_only(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    client.put(f"/api/sales/{created['id']}", json={"customer_name": "New Name"})

    events = client.get(f"/api/sales/{created['id']}/events").json()
    edit_events = [e for e in events if e["event_type"] == "sale_details_edited"]
    assert len(edit_events) == 1
    assert edit_events[0]["event_metadata"]["fields"] == ["customer_name"]
    assert "New Name" not in str(edit_events[0]["event_metadata"])


def test_unknown_sale_events_returns_404(client):
    response = client.get("/api/sales/does-not-exist/events")
    assert response.status_code == 404


def test_csv_import_records_import_and_payment_events(client):
    import io

    csv_text = "date,customer,service,amount,currency\n2026-01-05,Demo Customer,Consulting,50.00,ILS\n"
    preview = client.post(
        "/api/imports/csv/preview",
        files={"file": ("statement.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")},
    ).json()
    client.post(
        "/api/imports/csv/confirm",
        json={"file_hash": preview["file_hash"], "filename": "statement.csv", "valid_rows": preview["valid_rows"]},
    )

    sales = client.get("/api/sales").json()
    sale = next(s for s in sales if s["source"] == "csv")

    events = client.get(f"/api/sales/{sale['id']}/events").json()
    event_types = [e["event_type"] for e in events]
    assert "sale_imported_from_csv" in event_types
    assert "payment_succeeded" in event_types
