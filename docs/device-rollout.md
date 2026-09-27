# Physical Kindle rollout and rollback

Target baseline: Kindle Oasis 9th generation, firmware 5.16.2.1.1, KOReader v2026.03, WinterBreak2 hotfix, KUAL, and MRPI.

## 1. Read-only preflight

1. Keep the Kindle in airplane mode until the test explicitly needs the LAN.
2. Exit KOReader before connecting USB mass storage.
3. Mount the device and run:

   ```sh
   python3 bin/preflight_kindle.py
   ```

4. Confirm the expected firmware file, KOReader plugin directory, KUAL/MRPI directories, and sufficient free space.
5. On the live device, verify that Special Offers are inactive. KOReader and the stock screensaver hack must not be forced around an active ad screensaver.
6. Make a new complete timestamped backup before installing anything.

## 2. KOReader-only activation

1. Start the relay on the Mac and verify authenticated `/v1/health` access.
2. Install the plugin without `--enable-stock`.
3. Eject, start KOReader, enable Wi-Fi, and use **Tools → Highlight Art → Sync now**.
4. Confirm a `background_sync` receipt appears under `var/receipts/`.
5. Verify actual files under `/mnt/us/highlight-art/screensavers` after remounting.
6. Perform at least five suspend/wake cycles. Confirm that the artwork changes and that every displayed quote is complete and legible.

## 3. Stock screensaver compatibility gate

This stage is optional and higher-risk. The Oasis 2 must pass it before stock synchronization is enabled.

1. Obtain the current maintainer-distributed ScreenSavers Hack package and its documented dependencies. Inspect package checksums and release notes before installation.
2. Install only through MRPI. Never copy generated files into Kindle system partitions or `/usr/share/blanket`.
3. Put exactly one validated 1264×1680 project PNG8 image in `linkss/screensavers`.
4. Perform three complete stock-UI suspend/wake cycles, including one magnetic-cover cycle if used.
5. If any white screen, stale overlay, failed wake, or framework failure occurs, reboot once, uninstall the package through its supported uninstaller, and stop stock rollout.
6. If the one-image test passes, test ten validated images for at least ten cycles using the package's supplied random-mode controls.
7. Only after both tests pass, reinstall the Highlight Art plugin with `--enable-stock`. The installer refuses this flag unless `linkss/screensavers` already exists.

The KOReader plugin copies the same active manifest into the stock folder but deletes only `highlight-art-*.png`. It leaves package samples and user-owned screensavers untouched.

## Rollback

1. In KOReader, select **Tools → Highlight Art → Restore previous sleep-screen settings**.
2. Exit KOReader and connect USB.
3. Remove `koreader/plugins/highlightart.koplugin`, `koreader/settings/highlightart.lua`, and the project-owned `highlight-art-*` images only.
4. Disable and uninstall the stock screensaver package using its supplied KUAL/MRPI procedure if it was installed.
5. Stop and boot out both Mac LaunchAgents.
6. Preserve `var/` and the latest Kindle backup until normal sleep/wake behavior has been confirmed.

Do not factory-reset a frozen Kindle. Use the established forced-restart procedure and restore from the pre-install backup only if required.
