"""A demo-only stand-in for a real invoicing/receipt provider.

Deliberately never produces a PDF, image, or any artifact that could be
mistaken for a real, legally valid tax receipt — it only assigns a
clearly-marked synthetic reference number (`DEMO-XXXXXXXX`) and leaves
`document_url` unset. The frontend must label this as a demo integration
wherever it's shown, not present it as a real issued document.
"""

import uuid

from app.models.sale import Sale
from app.services.documents.base import DocumentGenerationResult, DocumentProvider

DEMO_DOCUMENT_PREFIX = "DEMO-"


class MockDocumentProvider(DocumentProvider):
    def generate_document(self, sale: Sale) -> DocumentGenerationResult:
        document_number = f"{DEMO_DOCUMENT_PREFIX}{uuid.uuid4().hex[:8].upper()}"
        return DocumentGenerationResult(succeeded=True, document_number=document_number, document_url=None)


def get_document_provider() -> DocumentProvider:
    """The only provider available today. A real deployment would read a
    setting here (mirroring `receipt_extractor_provider`/`storage_provider`)
    and select among registered real providers — none exist yet."""
    return MockDocumentProvider()
