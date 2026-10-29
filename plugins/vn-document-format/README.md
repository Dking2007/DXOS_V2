<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# Vietnamese document format check (ONLYOFFICE plugin)

Checks the open document against the layout rules for Vietnamese administrative
documents (*văn bản hành chính*) and lists what does not comply. It is a checker, not an
auto-formatter: it never changes the document.

*(Tiếng Việt: plugin ONLYOFFICE kiểm tra thể thức văn bản hành chính theo Nghị định
30/2020/NĐ-CP, Phụ lục I. Plugin chỉ báo lỗi, không tự sửa tài liệu.)*

**Status: version 0.1.0, not yet submitted to any marketplace, not yet run in a real
ONLYOFFICE editor.** See "What has and has not been verified".

## What it checks

Rules come from Nghị định 30/2020/NĐ-CP, Phụ lục I, Phần I. The values are in
[`src/rules.js`](src/rules.js) with the clause each one comes from.

| Check | Rule | Severity |
|---|---|---|
| Paper | A4, 210 x 297 mm (1 mm tolerance); landscape reported as a note | error |
| Margins | top and bottom 20-25 mm, left 30-35 mm, right 15-20 mm (0.5 mm tolerance) | error |
| Font | Times New Roman | error |
| Legacy encodings | fonts of the VNI, VietWare and TCVN3 families (`.VnTime`, `VNI-Times`) instead of Unicode | error |
| Colour | text is black | warning |
| Size | every element is 10-14 pt; long body paragraphs (100+ characters) are 13-14 pt | warning |
| National title | `CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM`: exact wording, bold, 12-13 pt | error |
| Motto | `Độc lập - Tự do - Hạnh phúc`: exact wording, bold, 13-14 pt | error |
| Title and motto sizes | 12 with 13, or 13 with 14 (footnote 1 of the size table) | warning |

If the national title and motto are absent, the header checks are skipped with a note
(an internal memo or a draft is not an error).

## What it does not check

- Page numbers, the position of each element on the page, the signature block, the
  recipients list, document numbers and dates. The decree specifies these but the plugin
  does not read them yet.
- Per-element sizes beyond the national title and motto (for example the "Nơi nhận" block
  at 11-12 pt). Only the 10-14 pt range and the body rule are enforced.
- Text whose font or size comes from a paragraph style is reported as a note ("font
  inherited"), not guessed. A document whose font is set only in styles will show that
  note instead of a font error.
- Documents other than *văn bản hành chính* (the decree has separate rules for copies,
  and other document types follow other regulations).

## What has and has not been verified

Verified (`npm test`, Node 22, 22 tests):
- Every rule above against boundary values and violations, including wording with
  different dash characters, and that Verdana is not mistaken for a legacy font.
- The ONLYOFFICE glue against a **fake** editor API: it builds the model the checker
  expects, skips non-paragraph blocks, renders results as text (never markup), and
  `config.json` is valid and points at files that exist.
- The rule values were read from a PDF copy of Phụ lục I on 2026-10-30.

Not verified:
- **Running in a real ONLYOFFICE editor.** The fake API follows the Document Builder API
  documentation (`ApiSection`, `ApiTextPr`, units in twips and half-points). The real editor
  may return different values for inherited properties.
- **Colour** relies on `ApiColor.GetRGB`, available from ONLYOFFICE 9.1. On older editors,
  including 8.3.3, colour is not checked.
- **Icons are placeholders** (solid squares) and the marketplace needs real light and dark
  icons plus screenshots.
- The rule values against the official gazette text, and with a records-management
  specialist.

## Run the tests

```bash
npm test
```

## Try it in ONLYOFFICE

1. Copy this folder into the editor's plugin directory (for Docs Developer or a self-hosted
   Document Server: `sdkjs-plugins/`), or load it with the Plugin Manager's "Add plugin".
2. Open a text document and start the plugin from the **Plugins** tab.

## Submitting to the ONLYOFFICE marketplace

The marketplace takes a pull request to
[`ONLYOFFICE/onlyoffice.github.io`](https://github.com/ONLYOFFICE/onlyoffice.github.io),
adding a folder under `sdkjs-plugins/content/`. Before submitting:

- Replace the placeholder icons and add store screenshots, as in other plugins' `resources/`.
- Read that repository's contributing notes and license requirements. Plugins published by
  ONLYOFFICE carry AGPL headers; third-party plugins have their own license, and this one is
  Apache-2.0. Confirm the marketplace accepts that.
- Run the plugin in a real editor and note the versions tested.

## License

Apache-2.0.
