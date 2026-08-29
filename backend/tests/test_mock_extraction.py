from decimal import Decimal
from pathlib import Path

from app.services.extraction.mock import MockReceiptExtractor


def test_extraction_is_deterministic_for_same_file(tmp_path: Path):
    image_path = tmp_path / "receipt.png"
    image_path.write_bytes(b"fake-image-bytes-1")

    extractor = MockReceiptExtractor()
    first = extractor.extract(str(image_path))
    second = extractor.extract(str(image_path))

    assert first == second


def test_extraction_differs_for_different_files(tmp_path: Path):
    path_a = tmp_path / "a.png"
    path_b = tmp_path / "b.png"
    path_a.write_bytes(b"content-a")
    path_b.write_bytes(b"content-b")

    extractor = MockReceiptExtractor()
    result_a = extractor.extract(str(path_a))
    result_b = extractor.extract(str(path_b))

    assert (result_a.business_name, result_a.total) != (result_b.business_name, result_b.total)


def test_extraction_confidence_within_bounds(tmp_path: Path):
    image_path = tmp_path / "receipt.png"
    image_path.write_bytes(b"some-bytes")

    result = MockReceiptExtractor().extract(str(image_path))
    assert 0 <= result.confidence <= 1


def test_extraction_amounts_are_non_negative(tmp_path: Path):
    image_path = tmp_path / "receipt.png"
    image_path.write_bytes(b"some-other-bytes")

    result = MockReceiptExtractor().extract(str(image_path))
    assert result.total is None or result.total >= 0
    assert result.vat is None or result.vat >= 0


def test_extraction_flags_missing_fields_with_warnings_instead_of_guessing(tmp_path: Path):
    found_missing_receipt_number = False
    found_missing_vat = False
    extractor = MockReceiptExtractor()

    for i in range(20):
        image_path = tmp_path / f"receipt_{i}.png"
        image_path.write_bytes(f"bytes-{i}".encode())
        result = extractor.extract(str(image_path))
        if result.receipt_number is None:
            found_missing_receipt_number = True
            assert "receipt_number_not_confident" in result.warnings
        if result.vat is None:
            found_missing_vat = True
            assert "vat_amount_not_confident" in result.warnings

    assert found_missing_receipt_number
    assert found_missing_vat


def test_extraction_does_not_error_on_nonexistent_path():
    result = MockReceiptExtractor().extract("/nonexistent/path/receipt.png")
    assert result.confidence >= 0


def test_extraction_amounts_use_decimal_with_two_decimal_places(tmp_path: Path):
    image_path = tmp_path / "receipt.png"
    image_path.write_bytes(b"decimal-precision-check")

    result = MockReceiptExtractor().extract(str(image_path))

    assert isinstance(result.total, Decimal)
    assert result.total == result.total.quantize(Decimal("0.01"))
    if result.vat is not None:
        assert isinstance(result.vat, Decimal)
        assert result.vat == result.vat.quantize(Decimal("0.01"))
        assert result.vat <= result.total


def test_extraction_never_yields_vat_greater_than_total(tmp_path: Path):
    extractor = MockReceiptExtractor()
    for i in range(30):
        image_path = tmp_path / f"receipt_{i}.png"
        image_path.write_bytes(f"vat-check-{i}".encode())
        result = extractor.extract(str(image_path))
        if result.vat is not None and result.total is not None:
            assert result.vat <= result.total
