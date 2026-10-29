// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
//
// Exercises scripts/plugin.js against a fake ONLYOFFICE API. This catches wiring mistakes
// (wrong method names, wrong shape handed to the checker). It does not prove the real
// editor returns the same values; that needs a manual run in ONLYOFFICE.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.join(__dirname, "..");
const TW = 1440 / 25.4;
const tw = (mm) => Math.round(mm * TW);

function fakeRun(text, { font = "Times New Roman", sizeHp = 28, bold = false, color = null } = {}) {
  return {
    GetClassType: () => "run",
    GetText: () => text,
    GetTextPr: () => ({
      GetFontFamily: () => font,
      GetFontSize: () => sizeHp,
      GetBold: () => bold,
      GetColor: () => color,
    }),
  };
}
function fakeParagraph(runs) {
  return {
    GetClassType: () => "paragraph",
    GetText: () => runs.map((r) => r.GetText()).join(""),
    GetElementsCount: () => runs.length,
    GetElement: (i) => runs[i],
  };
}
function fakeApi(paragraphs, { margins = true, fail = false } = {}) {
  const section = { GetPageWidth: () => tw(210), GetPageHeight: () => tw(297) };
  // Editors up to 8.3.3 have no margin getters at all.
  if (margins)
    Object.assign(section, {
      GetPageMarginLeft: () => tw(30), GetPageMarginTop: () => tw(20),
      GetPageMarginRight: () => tw(15), GetPageMarginBottom: () => tw(20),
    });
  const doc = {
    GetSections: () => {
      if (fail) throw new Error("boom");
      return [section];
    },
    GetElementsCount: () => paragraphs.length + 1,
    // A table or other non-paragraph block must be skipped, not crash the reader.
    GetElement: (i) => (i < paragraphs.length ? paragraphs[i] : { GetClassType: () => "table" }),
  };
  return { GetDocument: () => doc };
}

function load(lang, fakeParagraphs, apiOptions) {
  const elements = {};
  const el = (id) => (elements[id] ??= { id, textContent: "", children: [], appendChild(c) { this.children.push(c); } });
  const document = { getElementById: el, createElement: () => ({ className: "", textContent: "" }) };
  let command, callback;
  const window = {
    Asc: { plugin: { info: { lang }, callCommand(fn, _close, _calc, cb) { command = fn; callback = cb; } } },
  };
  const context = { window, document, Api: fakeApi(fakeParagraphs, apiOptions) };
  context.window.VnDocChecker = require("../src/checker");
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root, "scripts/plugin.js"), "utf8"), context);
  window.Asc.plugin.init();
  // The editor hands the command's result back as JSON, so do the same here.
  const model = JSON.parse(JSON.stringify(vm.runInContext(`(${command.toString()})()`, context)));
  callback(model);
  return { model, elements };
}

test("reads sections and paragraphs into the model shape the checker expects", () => {
  const { model } = load("vi-VN", [
    fakeParagraph([fakeRun("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", { sizeHp: 26, bold: true })]),
    fakeParagraph([fakeRun("Độc lập - Tự do - Hạnh phúc", { sizeHp: 28, bold: true })]),
  ]);
  assert.equal(model.sections.length, 1);
  assert.equal(model.sections[0].marginLeftTw, tw(30));
  assert.equal(model.paragraphs.length, 2, "the table block is skipped");
  assert.deepEqual(model.paragraphs[0].runs[0], {
    text: "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", fontFamily: "Times New Roman", sizeHp: 26, bold: true, color: null,
  });
});

test("a compliant document shows the all-clear message in Vietnamese", () => {
  const { elements } = load("vi-VN", [
    fakeParagraph([fakeRun("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", { sizeHp: 26, bold: true })]),
    fakeParagraph([fakeRun("Độc lập - Tự do - Hạnh phúc", { sizeHp: 28, bold: true })]),
  ]);
  assert.equal(elements.summary.textContent, "Không phát hiện lỗi thể thức.");
  assert.equal(elements.findings.children.length, 0);
});

test("a wrong font is listed, with the paragraph number, in English for other locales", () => {
  const { elements } = load("en-US", [
    fakeParagraph([fakeRun("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", { sizeHp: 26, bold: true })]),
    fakeParagraph([fakeRun("Độc lập - Tự do - Hạnh phúc", { sizeHp: 28, bold: true })]),
    fakeParagraph([fakeRun("Nội dung", { font: "Arial" })]),
  ]);
  assert.match(elements.summary.textContent, /Errors: 1/);
  const texts = elements.findings.children.map((c) => c.textContent);
  assert.ok(texts.some((t) => t.startsWith("Paragraph 3: ") && t.includes("Arial")), texts.join("\n"));
});

test("an editor without margin getters still reads the document and says margins were skipped", () => {
  const { model, elements } = load("en-US", [
    fakeParagraph([fakeRun("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", { sizeHp: 26, bold: true })]),
    fakeParagraph([fakeRun("Độc lập - Tự do - Hạnh phúc", { sizeHp: 28, bold: true })]),
  ], { margins: false });
  assert.equal(model.paragraphs.length, 2);
  assert.equal(model.sections[0].marginLeftTw, undefined);
  assert.match(elements.summary.textContent, /Errors: 0, warnings: 0, notes: 1/);
  assert.ok(elements.findings.children[0].textContent.includes("margins were not checked"));
});

test("a failure inside the editor is shown as an error, never as a clean result", () => {
  const { model, elements } = load("en-US", [], { fail: true });
  assert.equal(model.error, "boom");
  assert.match(elements.summary.textContent, /^Could not read the document: boom/);
  assert.equal(elements.findings.children.length, 0);
});

test("document text is shown as text, never parsed as markup", () => {
  const source = fs.readFileSync(path.join(root, "scripts/plugin.js"), "utf8");
  assert.equal(/innerHTML|insertAdjacentHTML|document\.write/.test(source), false);
});

test("config.json is valid and names files that exist", () => {
  const config = JSON.parse(fs.readFileSync(path.join(root, "config.json"), "utf8"));
  assert.match(config.guid, /^asc\.\{[0-9A-F-]{36}\}$/);
  const variation = config.variations[0];
  for (const file of [variation.url, ...variation.icons]) assert.ok(fs.existsSync(path.join(root, file)), file);
  assert.deepEqual(variation.EditorsSupport, ["word"]);
});
