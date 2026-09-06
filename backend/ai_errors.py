"""Stable business errors for AI provider and output validation failures."""


class AIServiceError(RuntimeError):
    """An AI request failed in a way the API layer can classify safely."""

    def __init__(self, message: str, *, code: str = "AI_PROVIDER_UNAVAILABLE", retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
