"""OpenAI Images API adapter; no SDK or automatic billable retries."""
from __future__ import annotations

import base64
import binascii
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .providers import GeneratedImage


class OpenAIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class OpenAIImageClient:
    def __init__(self, api_key: str, api_base: str = "https://api.openai.com/v1", *,
                 size: str = "1024x1536", quality: str = "high", timeout: int = 300):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")
        self.api_key, self.api_base = api_key, api_base.rstrip("/")
        self.size, self.quality, self.timeout = size, quality, timeout

    def generate(self, prompt: str, model: str) -> GeneratedImage:
        request = Request(
            f"{self.api_base}/images/generations",
            data=json.dumps({"model": model, "prompt": prompt, "n": 1,
                             "size": self.size, "quality": self.quality,
                             "output_format": "png", "background": "opaque"}).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(70_000_001)
        except HTTPError as exc:
            # Response bodies can echo prompts or credentials. Never log them.
            raise OpenAIError(f"OpenAI image request failed (HTTP {exc.code}); check model access and billing", exc.code) from None
        except (OSError, URLError):
            raise RuntimeError("OpenAI image request failed; check network access (no automatic retry)") from None
        if len(raw) > 70_000_000:
            raise RuntimeError("OpenAI image response exceeded the size limit")
        try:
            data = json.loads(raw)["data"][0]["b64_json"]
            return GeneratedImage(base64.b64decode(data, validate=True))
        except (ValueError, KeyError, IndexError, TypeError, binascii.Error):
            raise RuntimeError("OpenAI returned no valid base64 image") from None
