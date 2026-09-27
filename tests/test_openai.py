import base64
import io
import json
from urllib.error import HTTPError

import pytest
from highlight_art.openai import OpenAIImageClient


def test_openai_request_and_base64_response(monkeypatch):
    def fake_open(request, **kwargs):
        body = json.loads(request.data)
        assert body == {"model": "custom-image-model", "prompt": "exact prompt", "n": 1,
                        "size": "1024x1536", "quality": "high", "output_format": "png", "background": "opaque"}
        assert request.full_url == "https://api.openai.com/v1/images/generations"
        return io.BytesIO(json.dumps({"data": [{"b64_json": base64.b64encode(b"image").decode()}]}).encode())
    monkeypatch.setattr("highlight_art.openai.urlopen", fake_open)
    assert OpenAIImageClient("secret").generate("exact prompt", "custom-image-model").payload == b"image"


def test_openai_error_does_not_echo_provider_body(monkeypatch):
    def fail(*a, **k):
        raise HTTPError("https://api.openai.com", 401, "Unauthorized", {}, io.BytesIO(b"secret prompt"))
    monkeypatch.setattr("highlight_art.openai.urlopen", fail)
    with pytest.raises(RuntimeError, match="HTTP 401") as error:
        OpenAIImageClient("secret").generate("exact prompt", "model")
    assert "secret" not in str(error.value)
