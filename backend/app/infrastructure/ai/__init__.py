"""AI provider package: pluggable LLM/embedding backends."""
from .base import AIError, AIProvider
from .gemini_provider import GeminiProvider

__all__ = ["AIProvider", "AIError", "GeminiProvider"]
