# Contributing

Use Python 3.11 or newer on macOS or Linux. Clone the repository, install Tesseract and language data, then run:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

Keep fixtures synthetic. Do not submit API keys, real clippings, private prompts, generated personal images, or device backups. Put local work in `var/` and keep credentials in `.env` or environment variables.

Provider changes should test request serialization, response parsing and failures without paid calls. Selection changes should cover dates, duplicate highlights and incomplete metadata. Validation changes must keep wrong, missing or added quotation text out of the published pool. A passing OCR result is not a literary-quality review.

Prompt changes should evaluate mood, readability, exact wording and visual composition across contrasting passages. See the prompt design guide. For screenshots or examples, include source attribution and confirm that they were intentionally selected for public release.

The current command-line workflow is supported on macOS and Linux; its process lock uses `fcntl`. Other platforms need a lock implementation and tests before support is claimed.
