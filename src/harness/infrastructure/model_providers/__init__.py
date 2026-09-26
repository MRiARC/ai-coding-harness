"""Model provider layer: unified `generate` over OpenAI-compatible, Anthropic,
Google, and offline Fake backends (foundation issue 1.5)."""

from harness.config import ModelConfig
from harness.infrastructure.model_providers.anthropic import AnthropicProvider
from harness.infrastructure.model_providers.base import (
    ModelAuthError,
    ModelProvider,
    ModelResponse,
    ToolCall,
)
from harness.infrastructure.model_providers.fake import FakeProvider
from harness.infrastructure.model_providers.google import GoogleProvider
from harness.infrastructure.model_providers.openai_compatible import (
    OpenAICompatibleProvider,
    OpenAIProvider,
)


def create_model_provider(config: ModelConfig) -> ModelProvider:
    """Build the provider selected by `ModelConfig.provider`."""
    providers: dict[str, type[ModelProvider]] = {
        "openai": OpenAIProvider,
        "openai-compatible": OpenAICompatibleProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
        "fake": FakeProvider,
    }
    if config.provider == "fake":
        return FakeProvider(config, responses=[])
    provider_cls = providers.get(config.provider)
    if provider_cls is None:  # pragma: no cover - Literal guards this
        msg = f"unknown model provider '{config.provider}'"
        raise ValueError(msg)
    return provider_cls(config)


__all__ = [
    "AnthropicProvider",
    "FakeProvider",
    "GoogleProvider",
    "ModelAuthError",
    "ModelProvider",
    "ModelResponse",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "ToolCall",
    "create_model_provider",
]
