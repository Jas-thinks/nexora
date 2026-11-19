# Nexora Capture (browser extension, v0.1)

Records the **verdict, problem, language and runtime** of your own LeetCode submissions and uploads them to your Nexora account, so platforms without an official API still feed your analytics.

**It never reads or sends your code**, only reads the responses of the site's own submission-result polling, and only uploads to the server you configure.

## Install (developer mode)
1. Chrome → `chrome://extensions` → enable *Developer mode* → *Load unpacked* → select this `extension/` folder.
2. In Nexora → Settings → *Browser extension* → **Create capture token** (shown once).
3. Extension → Options: API URL (e.g. `http://localhost:18080`) and the token → Save (Chrome asks permission for that origin only).
4. Submit a solution on leetcode.com. The popup shows the upload status.

## Trust model
The token can **only** upload submissions (it cannot read anything and is not a login). Because the extension runs in your browser, uploads can be forged by you; Nexora stores them as `extension` provenance ("captured, not verified by the platform"). They count toward practice history and mastery, but never auto-verify a Daily Challenge.

## Status — read this
- Parser logic is unit-tested (`node --test test/`).
- The LeetCode response field names (`state`, `status_msg`, `status_runtime`, `lang`, `task_finish_time`) and the `/submissions/detail/<id>/check/` URL are from the author's knowledge of a private, undocumented web API and are **NOT verified against the live site**; LeetCode can change them at any time. If a field is missing the extension sends nothing.
- LeetCode's terms may restrict automated tooling; this extension only observes your own logged-in session and makes no requests to LeetCode. Check the terms yourself before relying on it.
- Only leetcode.com is supported. Adding a site = a new parser in `parse.js` plus a host permission.
- Not published to the Chrome Web Store; no icons yet.
