"""Minimal xAI Imagine client using the documented REST endpoint."""
from __future__ import annotations

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


from .providers import GeneratedImage


class XAIError(RuntimeError):
    pass


class XAIImageClient:
    def __init__(self, api_key: str, api_base: str = "https://api.x.ai/v1", *, timeout: int = 180) -> None:
        if not api_key:
            raise ValueError("XAI_API_KEY is required")
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

    def _open(self, request: Request, *, max_bytes: int = 50_000_000) -> bytes:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read(max_bytes + 1)
                if len(payload) > max_bytes:
                    raise XAIError(f"xAI response exceeded {max_bytes} bytes")
                return payload
        except HTTPError as exc:
            raise XAIError(f"xAI image request failed (HTTP {exc.code})") from None
        except (OSError, URLError) as exc:
            raise XAIError(f"xAI request failed: {exc}") from exc

    def generate(self, prompt: str, model: str) -> GeneratedImage:
        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "aspect_ratio": "3:4",
            "resolution": "2k",
            "response_format": "url",
        }).encode()
        request = Request(
            f"{self.api_base}/images/generations",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        response = json.loads(self._open(request, max_bytes=5_000_000))
        rows = response.get("data") or []
        if not rows or not isinstance(rows[0], dict):
            raise XAIError("xAI returned no image")
        row = rows[0]
        if row.get("b64_json"):
            return GeneratedImage(base64.b64decode(row["b64_json"]), "data:base64")
        url = str(row.get("url", ""))
        if not url.startswith("https://"):
            raise XAIError("xAI returned an invalid image URL")
        download = Request(
            url,
            method="GET",
            headers={
                "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) KindleHighlightArt/0.1",
            },
        )
        return GeneratedImage(self._open(download), url)
