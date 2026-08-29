class ReceiptExtractionError(Exception):
    """Base class for all receipt-extraction failures."""


class ReceiptExtractionConfigError(ReceiptExtractionError):
    """The selected provider is missing required configuration (e.g. an API key)."""


class ReceiptExtractionTimeoutError(ReceiptExtractionError):
    """The provider did not respond within the configured timeout, after retries."""


class ReceiptExtractionProviderError(ReceiptExtractionError):
    """The provider returned an error (transient, after exhausting retries, or non-transient)."""


class ReceiptExtractionParsingError(ReceiptExtractionError):
    """The provider's response could not be parsed into the expected structured format."""


class ReceiptExtractionValidationError(ReceiptExtractionError):
    """The parsed data failed our own business-rule validation."""
