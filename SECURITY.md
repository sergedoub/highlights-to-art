# Security and privacy

The core workflow reads a local clippings file and sends selected quotation text and source metadata to the configured image provider. Personal files, generated prompts and images, validation results and receipts remain under `var/`. Do not put secrets in prompts or commit local configuration.

The optional relay uses bearer authentication but plain HTTP by default. It binds to loopback in the example configuration. LAN use requires an explicit bind address change and a trusted private network; it does not provide TLS or production service hardening. Never expose it directly to the internet. A bearer token is not encryption.

Only OCR-validated images enter the downloadable manifest. OCR can reject correct artwork or occasionally misread incorrect artwork; visually review results before using them on a device. Generation and validation failures do not trigger silent provider fallback or unbounded spending.

For a suspected security issue, do not include credentials or personal clippings in a public issue. Report a minimal synthetic reproduction.
