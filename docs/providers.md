# Image providers

The pipeline owns selection, prompts, image conversion, OCR, caching and publication. A provider implements one method:

```python
from highlight_art.providers import GeneratedImage

class MyProvider:
    def generate(self, prompt: str, model: str) -> GeneratedImage:
        # Call your service and return encoded image bytes.
        return GeneratedImage(payload=image_bytes)
```

Add the adapter to `create_provider` in `src/highlight_art/providers.py` and the supported-provider validation in `config.py`. A model name alone cannot translate another provider's API; non-compatible APIs need adapters. Tests and embedding applications can pass a provider through `latest_run(..., client=provider)` without changing the pipeline.

## OpenAI

```toml
[generation]
provider = "openai"
model = "gpt-image-2"
api_base = "https://api.openai.com/v1"
api_key_env = "OPENAI_API_KEY"
size = "1024x1536"
quality = "high"
```

Set your own key in the environment or local `.env`. The adapter uses the Images API and expects base64 output. Models supporting that request shape can be selected in configuration. Account access, billing and supported sizes depend on the model. See the [OpenAI image generation documentation](https://developers.openai.com/api/docs/guides/image-generation).

## xAI / Grok

```toml
[generation]
provider = "xai"
model = "grok-imagine-image-quality"
api_base = "https://api.x.ai/v1"
api_key_env = "XAI_API_KEY"
```

The xAI adapter requests portrait 3:4, 2K output and downloads the returned image. The shared pipeline converts it to the configured device size. OpenAI's `size` and `quality` settings do not affect xAI. A past xAI generation succeeded, but its quotation did not pass exact-text validation.

Only configure endpoints you trust: the selected API key and quotation are sent there. Prompt text is never sent to the other provider automatically. There is no automatic fallback or automatic retry of a billable request.
