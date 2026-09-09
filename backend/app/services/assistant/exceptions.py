class AssistantError(Exception):
    """Base class for AI-assistant chat errors."""


class AssistantConfigError(AssistantError):
    """Raised when required assistant configuration (e.g. OPENAI_API_KEY) is missing."""


class AssistantProviderError(AssistantError):
    """Raised when the OpenAI call itself fails (timeout, connection, rate limit, auth, etc.)."""
