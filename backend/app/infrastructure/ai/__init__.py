"""AI provider package: pluggable LLM/embedding backends."""
from .base import AIError, AIProvider, QuotaExceededError
from .gemini_provider import GeminiProvider

__all__ = ["AIProvider", "AIError", "QuotaExceededError", "GeminiProvider"]
