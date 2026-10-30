# Submitting `vn-document-format` to the ONLYOFFICE marketplace

Status on 2026-10-30: **prepared, not submitted.** Nothing has been posted to GitHub.
The plugin is in [`plugins/vn-document-format`](../plugins/vn-document-format).

Source of the process: the marketplace repository's
[store README](https://github.com/ONLYOFFICE/onlyoffice.github.io/blob/master/store/README.md)
and its [icon requirements](https://api.onlyoffice.com/docs/plugins/configuration/icons-and-branding/),
read on 2026-10-30. Re-read them before submitting; they may have changed.

## What the marketplace asks for, and where we stand

| Requirement (from their guide) | Status |
|---|---|
| Folder under `sdkjs-plugins/content/` | Ready: copy `plugins/vn-document-format` |
| `config.json`, `index.html`, a script, `CHANGELOG.md` | Present |
| `version` as `x.x.x` and `offered` | `0.1.0`, `Desktiny contributors` |
| `store` block: background, screenshots, icons, categories | Present (`work`) |
| Toolbar icons, light and dark, 100-200% | Present: 28, 35, 42, 49 and 56 px, drawn by us |
| Store icons (`icon.png`, `@1.25x` to `@2x`, `icon.svg`) | Present: 120x60 to 240x120 |
| Screenshots | 2, at 2480x1416, taken in Document Server 8.3.3 |
| Localisation (their guide says "localize it") | **Partly:** names and descriptions have `vi`; the panel text switches between Vietnamese and English by editor language. There is no `translations/` folder like other plugins have |
| Test in Desktop Editors | **Not done** |
| Test in the Plugin Manager and in the dark theme | **Not done** (only a browser light theme) |
| Entry in `store/config.json` | Not added yet (done in the fork, see below) |

## Open questions to settle before sending

1. **License.** The marketplace repository is AGPL-3.0. Their other third-party plugins carry
   their own licenses (some have `LICENSE` and `3rd-Party.txt` files). Ours is Apache-2.0,
   which can be included in an AGPL-3.0 work. We have not confirmed that they accept it, so
   the pull request asks.
2. **Who submits.** A team member's own GitHub account. The fork, the commit sign-off and
   the replies to reviewers must be theirs.
3. **Rule accuracy.** The rules were read from a PDF copy of Phụ lục I of Nghị định
   30/2020/NĐ-CP, not from the official gazette, and nobody who does records management has
   checked them. Say so in the pull request, and ideally have someone check first.
4. **Margins.** They cannot be checked on 8.3.3. Test on a newer editor so the margin check
   is exercised at least once; today it has only been run against a fake API.
5. **Duplicates.** The marketplace had 59 plugins on 2026-10-30 and none for Vietnamese
   administrative documents, judging by folder names only. Search again before sending.

## Steps

1. Test in ONLYOFFICE Desktop Editors (pack the plugin files into a zip renamed `.plugin`
   and add it through the Plugin Manager), light and dark theme. Note the versions.
2. Fork `ONLYOFFICE/onlyoffice.github.io` and clone it.
3. Copy the plugin folder to `sdkjs-plugins/content/vn-document-format`. Do not copy
   `test/`, `package.json` or `node_modules`; the marketplace folder holds only plugin files.
   (Keep `README.md`; `CHANGELOG.md` is required.)
4. Add `{ "name": "vn-document-format", "discussion": "" }` to `store/config.json`.
5. Commit with `git commit --signoff` (our own repository uses DCO; theirs does not say, and
   signing off does no harm). One commit.
6. Open the pull request with the text below. Say plainly that AI helped write the code.
7. Answer reviewers yourself. When there is a result, record the link and the real status
   (merged, waiting, or declined with the reason) in the "Đóng góp ngược" table of the
   Desktiny README.

## Pull request text (edit it so every sentence is true when you send it)

**Title:** `Add Vietnamese document format check plugin`

**Body:**

```
Adds a plugin that checks a document against the layout rules for Vietnamese
administrative documents (Decree 30/2020/ND-CP, Appendix I, Part I): A4 paper,
Times New Roman and legacy-encoding fonts, text colour, font sizes, and the
national title and motto. It only reports problems; it never edits the document.

Why: every Vietnamese school and agency writes documents to this layout, and the
editor has no way to check it. There is a similar tool for Chinese official
documents (chineseautoformattool) but none for Vietnamese ones, as far as I could
tell from the plugin list.

Checked:
- 29 unit tests (Node), including each rule at its boundaries.
- Run in ONLYOFFICE Document Server 8.3.3 (Docker) on two small .docx files: a
  compliant one gave 0 errors and 0 warnings; one with deliberate faults gave 6
  errors and 3 warnings.

Not checked:
- Desktop Editors, the dark theme in the Plugin Manager, and editors newer than 8.3.3.
- Page margins: ApiSection has no margin getters in 8.3.3, so the plugin shows a note
  instead. The margin check has only run against a fake API.
- The rule values were read from a PDF copy of the appendix, not the official gazette.
- The panel text is Vietnamese or English by editor language; there is no
  translations/ folder yet.

License: the plugin is Apache-2.0 (see the SPDX headers). The marketplace repository is
AGPL-3.0. Is that acceptable for a third-party plugin? If you need a different license
or a LICENSE / 3rd-Party file, I will add it.

Use of AI: the code, tests and this description were written with the help of an AI
assistant (Claude). I have read all of it and can explain it.
```
