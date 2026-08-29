from abc import ABC, abstractmethod

from app.schemas.receipt import ExtractedReceiptData


class ReceiptExtractor(ABC):
    """Provider-independent interface for turning a receipt image into structured data.

    Implementations must never invent values they are not reasonably confident about;
    unknown fields should be left as None with an explanatory entry in `warnings`.
    """

    @abstractmethod
    def extract(self, image_path: str) -> ExtractedReceiptData:
        raise NotImplementedError
