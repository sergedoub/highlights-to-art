# Wireless collection: current limits and next options

The supported starting point is the standard Kindle reader and a USB copy of `documents/My Clippings.txt`. This does not require KOReader, a jailbreak, or an Amazon password. It reads the file from one device; it is not an account-wide annotation export. The current parser expects English metadata headers and dates, even when the highlighted text is in another language.

For future wireless collection, the most practical route for Amazon-purchased books is an explicit integration with a highlights service or a user-authorized browser export. Readwise's own documentation describes a Kindle browser extension and a manual clippings importer. It also notes that its extension cannot collect highlights from sideloaded or emailed documents. An integration here would therefore need to disclose coverage, preserve source timestamps, and deduplicate imports; it would not replace USB for every library.

A possible next adapter is the Readwise export API after the user has configured Kindle synchronization. This is a design direction, not implemented functionality or a bundled account integration. No Amazon credentials or browser cookies are requested by this project.

The experimental KOReader plugin can upload the standard reader's clippings file when KOReader runs, but it requires a device that can run KOReader and time spent in that app. It is not background account synchronization for ordinary stock Kindle users.

Wireless highlight collection and displaying custom sleep screens are separate problems. The stock Kindle reader does not become a custom-image screensaver merely because this tool produced PNG files. The optional device runbook describes the separate, unverified screensaver path.

Sources checked September 27, 2026:

- [Readwise: Import from Amazon Kindle](https://docs.readwise.io/readwise/docs/importing-highlights/kindle)
- [Readwise export API](https://readwise.io/api_deets)

These sources establish integration options and limitations, not successful wireless operation of this project.
