"""The image-provider boundary. Adapters return bytes; the pipeline owns validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeneratedImage:
    payload: bytes
    source_url: str = ""


class ImageProvider(Protocol):
    def generate(self, prompt: str, model: str) -> GeneratedImage: ...


def create_provider(config) -> ImageProvider:
    # Imports are local so third-party adapters need only implement the protocol.
    if config.generation.provider == "xai":
        from .xai import XAIImageClient
        return XAIImageClient(config.api_key, config.generation.api_base)
    if config.generation.provider == "openai":
        from .openai import OpenAIImageClient
        return OpenAIImageClient(
            config.api_key, config.generation.api_base,
            size=config.generation.size, quality=config.generation.quality,
        )
    raise ValueError(f"Unsupported provider: {config.generation.provider}")
