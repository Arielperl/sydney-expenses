import io
from decimal import Decimal

from app.models.sale import Sale
from app.services.ingestion.csv_import import parse_csv

VALID_CSV = (
    "date,customer,service,amount,currency\n"
    "2026-09-01,Demo Customer A,Consulting session,184.90,ILS\n"
    "2026-09-02,Demo Customer B,Web design,45.50,ILS\n"
)


class TestParseCsv:
    def test_valid_csv_parses_all_rows(self):
        raw = VALID_CSV.encode("utf-8")
        rows, errors = parse_csv(raw, "hash123", max_rows=100)

        assert len(rows) == 2
        assert errors == []
        assert rows[0].customer == "Demo Customer A"
        assert str(rows[0].amount) == "184.90"
        assert rows[0].currency == "ILS"
        assert rows[0].external_id == "csv:hash123:1"

    def test_utf8_bom_parses_identically_to_plain_utf8(self):
        bom_bytes = b"\xef\xbb\xbf" + VALID_CSV.encode("utf-8")

        rows, errors = parse_csv(bom_bytes, "hash123", max_rows=100)

        assert len(rows) == 2
        assert errors == []
        assert rows[0].customer == "Demo Customer A"

    def test_malformed_row_is_reported_as_error_others_still_valid(self):
        csv_text = (
            "date,customer,service,amount,currency\n"
            "2026-09-01,Demo Customer A,Consulting session,184.90,ILS\n"
            "not-a-date,Bad row,Consulting,10.00,ILS\n"
            "2026-09-02,Demo Customer B,Web design,45.50,ILS\n"
        )

        rows, errors = parse_csv(csv_text.encode("utf-8"), "hash123", max_rows=100)

        assert len(rows) == 2
        assert len(errors) == 1
        assert errors[0].row_number == 2

    def test_row_count_over_limit_reported_as_error(self):
        lines = ["date,customer,service,amount,currency"]
        for i in range(5):
            lines.append(f"2026-09-0{i + 1},Customer,Service,10.00,ILS")
        csv_text = "\n".join(lines) + "\n"

        rows, errors = parse_csv(csv_text.encode("utf-8"), "hash123", max_rows=2)

        assert len(rows) == 2
        assert len(errors) == 1

    def test_wrong_header_raises(self):
        bad_csv = "wrong,header,columns\n1,2,3\n".encode("utf-8")

        try:
            parse_csv(bad_csv, "hash123", max_rows=100)
            assert False, "expected ValueError"
        except ValueError:
            pass


class TestCsvImportRoutes:
    def test_preview_returns_parsed_rows(self, client):
        response = client.post(
            "/api/imports/csv/preview",
            files={"file": ("statement.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")},
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["valid_rows"]) == 2
        assert body["errors"] == []
        assert body["is_repeat_file"] is False

    def test_confirm_creates_sales(self, client, db_session):
        preview = client.post(
            "/api/imports/csv/preview",
            files={"file": ("statement.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")},
        ).json()

        response = client.post(
            "/api/imports/csv/confirm",
            json={"file_hash": preview["file_hash"], "filename": "statement.csv", "valid_rows": preview["valid_rows"]},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["created_count"] == 2
        assert body["duplicate_count"] == 0

        count = db_session.query(Sale).filter(Sale.source_provider == "csv").count()
        assert count == 2

    def test_confirming_same_file_twice_reports_duplicates_not_new_rows(self, client, db_session):
        preview = client.post(
            "/api/imports/csv/preview",
            files={"file": ("statement.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")},
        ).json()
        confirm_payload = {
            "file_hash": preview["file_hash"],
            "filename": "statement.csv",
            "valid_rows": preview["valid_rows"],
        }

        first = client.post("/api/imports/csv/confirm", json=confirm_payload)
        second = client.post("/api/imports/csv/confirm", json=confirm_payload)

        assert first.json()["created_count"] == 2
        assert second.json()["created_count"] == 0
        assert second.json()["duplicate_count"] == 2

        count = db_session.query(Sale).filter(Sale.source_provider == "csv").count()
        assert count == 2

    def test_oversized_file_is_rejected(self, client, monkeypatch):
        from app.core.config import get_settings

        monkeypatch.setenv("CSV_MAX_FILE_SIZE_BYTES", "10")
        get_settings.cache_clear()
        try:
            response = client.post(
                "/api/imports/csv/preview",
                files={"file": ("statement.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")},
            )
            assert response.status_code == 413
        finally:
            get_settings.cache_clear()

    def test_repeat_file_is_flagged_but_not_blocked(self, client):
        first_preview = client.post(
            "/api/imports/csv/preview",
            files={"file": ("statement.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")},
        ).json()
        client.post(
            "/api/imports/csv/confirm",
            json={
                "file_hash": first_preview["file_hash"],
                "filename": "statement.csv",
                "valid_rows": first_preview["valid_rows"],
            },
        )

        second_preview = client.post(
            "/api/imports/csv/preview",
            files={"file": ("statement.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")},
        )

        assert second_preview.status_code == 200
        assert second_preview.json()["is_repeat_file"] is True

    def test_csv_imported_sales_get_a_document_attempted(self, client, db_session):
        preview = client.post(
            "/api/imports/csv/preview",
            files={"file": ("statement.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")},
        ).json()
        client.post(
            "/api/imports/csv/confirm",
            json={"file_hash": preview["file_hash"], "filename": "statement.csv", "valid_rows": preview["valid_rows"]},
        )

        sales = db_session.query(Sale).filter(Sale.source_provider == "csv").all()
        assert all(sale.document_status.value == "issued" for sale in sales)
        assert all(sale.document_number and sale.document_number.startswith("DEMO-") for sale in sales)

    def test_csv_imported_sales_get_standard_vat_computed(self, client, db_session):
        """The documented CSV format has no VAT column (v1) — each row's
        amount is treated as an ordinary standard-VAT-inclusive sale under
        the Israeli demo tax configuration, same as a manual entry with no
        treatment chosen."""
        preview = client.post(
            "/api/imports/csv/preview",
            files={"file": ("statement.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")},
        ).json()
        client.post(
            "/api/imports/csv/confirm",
            json={"file_hash": preview["file_hash"], "filename": "statement.csv", "valid_rows": preview["valid_rows"]},
        )

        sale = db_session.query(Sale).filter(Sale.source_provider == "csv", Sale.gross_amount == Decimal("184.90")).one()
        assert sale.tax_treatment.value == "standard"
        assert sale.vat_amount == Decimal("28.21")
        assert sale.vat_rate == Decimal("0.18")
        assert sale.net_amount == Decimal("156.69")
