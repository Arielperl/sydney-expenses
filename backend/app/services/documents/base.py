"""Adapter boundary for issuing a receipt/tax document to a customer.

This is the extension point for a real invoicing provider (e.g. an
Israeli-compliant e-invoicing service, or a PSP's own receipt API) later:
adding one means writing one more `DocumentProvider` implementation and
selecting it via configuration — the call site (`app/services/sale_ingest.py`)
never changes. Only `MockDocumentProvider` exists today, and it never
produces anything that could be mistaken for a real, officially valid tax
receipt — see its own docstring.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.sale import Sale


@dataclass
class DocumentGenerationResult:
    succeeded: bool
    document_number: str | None = None
    document_url: str | None = None
    error_message: str | None = None


class DocumentProvider(ABC):
    @abstractmethod
    def generate_document(self, sale: Sale) -> DocumentGenerationResult: ...
