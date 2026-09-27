# Prompt design and customization

The default aims for a readable, visually strong interpretation of a passage that preserves its particular mood and meaning. It supports humor, tenderness, ambiguity and severity without assigning a single mood to an author or genre.

## Files and inputs

- `prompts/system.md` holds the reusable interpretation, composition, text and display rules.
- `prompts/image.md` supplies `{{work_title}}`, `{{author}}` and `{{quote}}`. These are the only template placeholders. Keep their spelling unchanged.

Send both prompts to the image provider. If a provider accepts only one prompt, concatenate the system brief and the rendered image template, in that order. Metadata is context and must not appear in the artwork. The quoted passage is data, including when its words resemble instructions.

## Customize one thing at a time

Edit the relevant section of the system prompt to change the default across highlights. For example, add “Prefer spare ink drawings with broad, clean shapes” to change visual treatment, or “Prefer left-aligned text with restrained hierarchy” to change typography. Keep exact-text requirements intact. Retain enough layout freedom to accommodate long passages and different scripts.

For a single passage, add a short, verified context paragraph before `<EXACT_QUOTE>` in that request. State the speaker, situation and relevant emotional turn; distinguish established context from your interpretation. Do not add a new template variable unless your renderer supports it. Never replace the original quote with your explanation.

A generic context example: “The narrator is politely excusing a digression while knowingly extending it. Preserve the dry joke rather than depicting relaxation.” Context should guide interpretation without forcing a literal scene. When surrounding context is unavailable, accept a less specific image rather than inventing plot details. A prompt cannot recover missing context reliably on its own.

To change the target aspect ratio or margins, edit DESIGN FOR THE SCREEN and configure the provider/output pipeline consistently. An opaque white canvas is the default. Request opaque output in the provider settings where available; inspect the actual file because wording alone does not guarantee opacity.

## Review rubric

Score each dimension from 0 to 3: 0 contradicts or fails; 1 is weak; 2 is sound with minor limitations; 3 is strong. Record one visible observation supporting each score.

| Dimension | Review question |
| --- | --- |
| Mood and context | Does the image preserve the passage's emotional turn, irony, ambiguity and degree of seriousness? Does it distinguish stillness from comfort and a speaker's view from authorial endorsement? |
| Meaning | Does the visual relationship express the claim, including its qualification or reversal, rather than merely depict a keyword? |
| Source restraint | Are concrete scene details supported? Is metaphor distinguishable from a claimed event? Has an anthology title been mistaken for a specific work? |
| Visual quality | Is there one coherent idea, a clear focal hierarchy, resolved anatomy/perspective and purposeful negative space? |
| Readability | Can the full quotation be read comfortably at the intended device size, with clear order, margins and contrast? |
| Exact text | Is every supplied character present exactly once, with no added labels or background writing? |

Reject an output with any missing, changed or added text, unreadable text, a material source contradiction, or an emotional inversion. Do not average these failures away with attractive rendering. For other dimensions, aim for at least 2 each. “Source unknown” is a documented limit, not permission to manufacture certainty.

Use two quick checks: hide the text and describe the image's mood; then ask whether the same image would fit many unrelated quotations. If the mood conflicts or the image is interchangeable, revise the concept. Compare at least a serious/ironic passage, another fiction passage and nonfiction when changing the default. Check multilingual text and long quotations separately.

## Validation limits

The initial revision was exercised through three built-in OpenAI ImageGen calls. All three were rejected in visual review; metaphor, composition and output-background problems remained. A subsequent actual GPT Image 2 API output was also inspected: the first result from the five-highlight run. Its text was clearly visible on white, but its simplified opposing symbols substituted a different proposition for the passage's meaning. That result still needs improvement; the rest of that run has not been assessed here.

The latest revision replaces the main art-direction paragraph with a positive requirement to preserve the full proposition and express it through one unified visual situation. It prioritizes spatial relationships, gesture, physical forces and tonal composition, reflecting a preference for strong literary illustration over explanatory symbol assemblies. A subsequent single GPT Image 2.5 Flare API test passed text and format checks, but still produced a misleading metaphor for the difficult passage. The change therefore remains an improvement in guidance, not a demonstrated solution to semantic reliability. See [validation evidence](validation.md).

Prompt instructions are not automatic validation. Manually compare the rendered text with the input, including punctuation and script-specific characters. OCR can assist but is not a character-level guarantee. Inspect output dimensions and transparency, then check an actual e-ink display before claiming device validation. If exact text is essential, deterministic text composition is a separate implementation option; this prompt does not provide it.
