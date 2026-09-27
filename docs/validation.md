# Validation evidence

Checked September 27, 2026 for the first experimental release.

## Pipeline

A physical Kindle's clippings file was read over USB. The workflow selected the five newest unique highlights by their parsed dates, then made five OpenAI Images API calls using GPT Image 2. All five images were saved, converted to 1264 × 1680 opaque grayscale palette PNG, and retained with their exact prompts and results.

The first sparse-text OCR pass rejected all five. A no-cost recheck using alternative full-image layout modes and the configured languages individually validated all five quotations exactly. No fuzzy text correction, quote truncation, image regeneration, or manual approval was used to make them pass. Russian needed its own language pass to avoid Latin/Cyrillic lookalike confusion. These are text/format checks, not proof of interpretation quality.

A further single API call with the final prompt revision and GPT Image 2.5 Flare also passed exact-text OCR and format validation. Its illustration still substituted a simplistic visual metaphor for a difficult literary passage. This test is not grounds for claiming superior model quality; GPT Image 2 remains the example default from the five-image pipeline test.

Private clippings, run receipts, prompts containing quotations, and live-test images are excluded from the repository. The two intentionally selected README images are earlier built-in ImageGen examples, accurately labeled as such.

## Software checks

- 26 local tests passed, including real Tesseract OCR, request serialization, chronological selection, deduplication, bounded attempts, cached failures, no-cost rechecks, image format, relay authentication and manifest integrity.
- Wheel and source distribution built successfully; neither contains private runtime state or credentials.
- A clean installation from the source distribution successfully selected a synthetic clipping without an image API call.
- The GitHub workflow runs the same tests with Python 3.11 and 3.13 on Linux. Its live result is visible in Actions; local results alone do not establish hosted CI status.

## Remaining limitations

Prompt evaluation improved explicit handling of mood, logical meaning and source uncertainty, but complex literary passages can still produce misleading or generic visual metaphors. The default is a documented starting point with a review rubric, not a reliability guarantee. Users should add verified passage context where available and review semantic fidelity separately from OCR.

No physical Kindle sleep/wake display test, KOReader synchronization, stock screensaver installation, or wireless account synchronization was completed. The generated files have the intended format; device display remains a separate validation step.
