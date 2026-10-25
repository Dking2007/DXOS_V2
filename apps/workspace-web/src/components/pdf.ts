// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Loaded on demand so pdf.js (~1 MB) only downloads when someone opens a PDF.
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
// Bundled by Vite as a .js worker, so it is served with a JavaScript content type.
import PdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?worker'

let worker: Worker | null = null

export function openPdf(data: ArrayBuffer) {
  worker ??= new PdfWorker()
  GlobalWorkerOptions.workerPort = worker
  // Only pages are drawn to canvas: no PDF viewer, so scripts inside a PDF never run.
  return getDocument({ data, isEvalSupported: false }).promise
}
