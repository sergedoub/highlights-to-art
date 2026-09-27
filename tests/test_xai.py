import json

from highlight_art.xai import XAIImageClient


def test_client_uses_current_imagine_request_shape(monkeypatch):
    client = XAIImageClient("secret", "https://api.x.ai/v1")
    requests = []

    def fake_open(request, **kwargs):
        requests.append(request)
        if request.full_url.endswith("/images/generations"):
            body = json.loads(request.data)
            assert body == {
                "model": "grok-imagine-image-quality",
                "prompt": "exact prompt",
                "aspect_ratio": "3:4",
                "resolution": "2k",
                "response_format": "url",
            }
            return json.dumps({"data": [{"url": "https://example.test/image.jpeg"}]}).encode()
        assert request.get_header("User-agent").startswith("Mozilla/5.0")
        assert "image/png" in request.get_header("Accept")
        return b"image-bytes"

    monkeypatch.setattr(client, "_open", fake_open)
    result = client.generate("exact prompt", "grok-imagine-image-quality")
    assert result.payload == b"image-bytes"
    assert len(requests) == 2
