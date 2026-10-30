// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { checkDocument, formatFinding, normalise } = require("../src/checker");
const RULES = require("../src/rules");

const tw = (mm) => Math.round(mm * RULES.TWIPS_PER_MM);

function run(text, over = {}) {
  return { text, fontFamily: "Times New Roman", sizeHp: 28, color: null, bold: false, ...over };
}
function paragraph(text, over = {}) {
  return { text, runs: [run(text, over)] };
}
function goodSection(over = {}) {
  return {
    widthTw: tw(210), heightTw: tw(297),
    marginTopTw: tw(20), marginBottomTw: tw(20), marginLeftTw: tw(30), marginRightTw: tw(15),
    ...over,
  };
}
function goodDocument() {
  return {
    sections: [goodSection()],
    paragraphs: [
      paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", { sizeHp: 26, bold: true }),
      paragraph("Độc lập - Tự do - Hạnh phúc", { sizeHp: 28, bold: true }),
      paragraph("Kính gửi: Bộ Nội vụ"),
    ],
  };
}
const codes = (doc) => checkDocument(doc).map((f) => f.code);

test("a document that follows the decree has no errors or warnings", () => {
  const found = checkDocument(goodDocument()).filter((f) => f.severity !== "info");
  assert.deepEqual(found, []);
});

test("margins at the edges of each allowed range pass, just outside fails", () => {
  const edges = { marginTopTw: tw(25), marginBottomTw: tw(25), marginLeftTw: tw(35), marginRightTw: tw(20) };
  const ok = goodDocument();
  ok.sections = [goodSection(edges)];
  assert.equal(codes(ok).includes("margin"), false);

  const bad = goodDocument();
  bad.sections = [goodSection({ marginLeftTw: tw(25), marginRightTw: tw(25), marginTopTw: tw(10) })];
  const margins = checkDocument(bad).filter((f) => f.code === "margin");
  assert.deepEqual(margins.map((f) => f.params.edge).sort(), ["left", "right", "top"]);
});

test("margins that the editor cannot report are one info line, not errors", () => {
  const doc = goodDocument();
  doc.sections = [{ widthTw: tw(210), heightTw: tw(297) }];
  const found = checkDocument(doc);
  assert.deepEqual(found.filter((f) => f.severity !== "info"), []);
  assert.ok(found.some((f) => f.code === "margin_unavailable"));
});

test("a section with no readable paper size is skipped, not reported as wrong", () => {
  const doc = goodDocument();
  doc.sections = [{}];
  assert.equal(codes(doc).includes("page_size"), false);
});

test("paper must be A4; landscape A4 is reported as info, not error", () => {
  const letter = goodDocument();
  letter.sections = [goodSection({ widthTw: tw(215.9), heightTw: tw(279.4) })];
  assert.ok(codes(letter).includes("page_size"));

  const landscape = goodDocument();
  landscape.sections = [goodSection({ widthTw: tw(297), heightTw: tw(210) })];
  const found = checkDocument(landscape);
  assert.ok(found.some((f) => f.code === "page_landscape" && f.severity === "info"));
  assert.equal(found.some((f) => f.severity === "error"), false);
});

test("wrong or legacy fonts are errors, reported once per paragraph", () => {
  const doc = goodDocument();
  doc.paragraphs.push({
    text: "Nội dung",
    runs: [run("Nội ", { fontFamily: "Arial" }), run("dung ", { fontFamily: "Arial" }), run("khác", { fontFamily: ".VnTime" })],
  });
  const fonts = checkDocument(doc).filter((f) => f.code === "font_family" || f.code === "legacy_font");
  assert.deepEqual(fonts.map((f) => f.code).sort(), ["font_family", "legacy_font"]);
});

test("Verdana and Vietnamese-looking names are not mistaken for legacy fonts", () => {
  const doc = goodDocument();
  doc.paragraphs.push(paragraph("Nội dung", { fontFamily: "Verdana" }));
  const found = checkDocument(doc);
  assert.ok(found.some((f) => f.code === "font_family"));
  assert.equal(found.some((f) => f.code === "legacy_font"), false);
});

test("non-black text is a warning; automatic colour counts as black", () => {
  const doc = goodDocument();
  doc.paragraphs.push(paragraph("Chữ đỏ", { color: { r: 255, g: 0, b: 0 } }));
  doc.paragraphs.push(paragraph("Chữ tự động", { color: { auto: true } }));
  const colours = checkDocument(doc).filter((f) => f.code === "font_color");
  assert.equal(colours.length, 1);
  assert.equal(colours[0].severity, "warning");
});

test("sizes outside 10-14 warn anywhere; long body text must be 13-14", () => {
  const doc = goodDocument();
  doc.paragraphs.push(paragraph("Chữ nhỏ", { sizeHp: 16 }));
  doc.paragraphs.push(paragraph("Chữ lớn", { sizeHp: 36 }));
  const long = "Nội dung văn bản dài hơn một trăm ký tự để được coi là phần nội dung chính của văn bản hành chính này. ";
  doc.paragraphs.push(paragraph(long, { sizeHp: 24 }));
  doc.paragraphs.push(paragraph(long, { sizeHp: 26 }));
  const found = checkDocument(doc);
  assert.equal(found.filter((f) => f.code === "font_size").length, 2);
  assert.equal(found.filter((f) => f.code === "body_size").length, 1);
});

test("size 11 or 12 in a short line (e.g. Nơi nhận) is accepted", () => {
  const doc = goodDocument();
  doc.paragraphs.push(paragraph("Nơi nhận:", { sizeHp: 24, bold: true }));
  doc.paragraphs.push(paragraph("- Lưu: VT.", { sizeHp: 22 }));
  assert.deepEqual(checkDocument(doc).filter((f) => f.severity !== "info"), []);
});

test("national title and motto: wording, bold, size and pairing", () => {
  const doc = goodDocument();
  doc.paragraphs[0] = paragraph("Cộng hòa xã hội chủ nghĩa Việt Nam", { sizeHp: 26, bold: false });
  doc.paragraphs[1] = paragraph("Độc lập – Tự do – Hạnh phúc", { sizeHp: 24, bold: true });
  const found = codes(doc);
  assert.ok(found.includes("national_title_text"));
  assert.ok(found.includes("national_title_bold"));
  assert.equal(found.includes("motto_text"), false, "different dash characters are normalised");
  assert.ok(found.includes("motto_size"));
});

test("title 12 with motto 14 breaks the pairing rule; 13 with 14 is fine", () => {
  const mismatched = goodDocument();
  mismatched.paragraphs[0] = paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", { sizeHp: 24, bold: true });
  mismatched.paragraphs[1] = paragraph("Độc lập - Tự do - Hạnh phúc", { sizeHp: 28, bold: true });
  assert.ok(codes(mismatched).includes("title_motto_pair"));

  const fine = goodDocument();
  fine.paragraphs[0] = paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", { sizeHp: 26, bold: true });
  assert.equal(codes(fine).includes("title_motto_pair"), false);
});

test("a document without the header is not an error, only an info line", () => {
  const doc = { sections: [goodSection()], paragraphs: [paragraph("Ghi chú nội bộ")] };
  const found = checkDocument(doc);
  assert.deepEqual(found.map((f) => f.code), ["header_not_found"]);
  assert.equal(found[0].severity, "info");
});

test("only one half of the header present is a warning", () => {
  const doc = goodDocument();
  doc.paragraphs.splice(0, 1);
  assert.ok(codes(doc).includes("national_title_missing"));
});

test("runs with unknown font are counted as info, not guessed", () => {
  const doc = goodDocument();
  doc.paragraphs.push({ text: "Kế thừa", runs: [run("Kế thừa", { fontFamily: null })] });
  const info = checkDocument(doc).find((f) => f.code === "font_inherited");
  assert.deepEqual(info.params, { runs: 1 });
});

test("findings are ordered errors, warnings, then info", () => {
  const doc = goodDocument();
  doc.sections = [goodSection({ marginLeftTw: tw(10) })];
  doc.paragraphs.push(paragraph("Đỏ", { color: { r: 255, g: 0, b: 0 } }));
  doc.paragraphs.push({ text: "x", runs: [run("x", { fontFamily: null })] });
  const order = checkDocument(doc).map((f) => f.severity);
  assert.deepEqual(order, [...order].sort((a, b) => ({ error: 0, warning: 1, info: 2 }[a] - { error: 0, warning: 1, info: 2 }[b])));
});

test("every code the checker can emit has a Vietnamese and an English message", () => {
  const { MESSAGES } = require("../src/checker");
  assert.deepEqual(Object.keys(MESSAGES.vi).sort(), Object.keys(MESSAGES.en).sort());
  const doc = goodDocument();
  doc.sections = [goodSection({ marginLeftTw: tw(10), widthTw: tw(200) })];
  for (const item of checkDocument(doc)) {
    for (const lang of ["vi", "en"]) assert.notEqual(formatFinding(item, lang), item.code);
  }
});

test("normalise treats dash variants and spacing the same", () => {
  assert.equal(normalise("Độc lập – Tự do — Hạnh phúc"), "Độc lập - Tự do - Hạnh phúc");
  assert.equal(normalise("  A   B "), "A B");
});

test("empty document model does not throw", () => {
  assert.deepEqual(checkDocument({}).map((f) => f.code), ["header_not_found"]);
});
