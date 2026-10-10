# InvPal Roadmap

Status: [x] done · [ ] open · [USER] needs Jo (sudo, accounts, secrets)

## 1a. Synthetic data generator [x]
Done. Master data, business logic, 6 planted discrepancy types, labels in data/labels/, 31 tests.
Notes: QTY_MISMATCH minimum deviation: 8%.

## 1b. Rendering [x]
Done. 5 Lieferschein layouts + 5 Rechnung layouts (one pair per supplier), Jinja2 → WeasyPrint PDF,
wired into the CLI (`python -m generator`, or `--no-render` to skip). Wiegeschein block shown for
BULK_UNITS materials (t/m³/kg); synthetic seeded signature scribble when signed. generator/test_render.py
covers all 5 layouts with pdfplumber text extraction against ground-truth field values, plus the
discrepancy-leak check from test_writer.py.
Notes: table-layout:fixed items tables need box-sizing:border-box or padding overflows the page
(silently clips the last column) -- found via visual PDF inspection, not caught by the text-extraction
test itself. Column widths were sized empirically against the longest real material name
("Einfassung Rasenkantenstein 100x20x5", 37 chars) rather than guessed, since pdfplumber's reading
order breaks silently (not an error) if any single field wraps across lines in a table cell.

## 1c. Scans [ ]
- PDF → PNG (pdf2image, 200 dpi), augraphy degradation at 3 levels: clean / medium / bad (~60/25/15).
- Optional overlays: handwritten-looking quantity correction, stamp.
- Output: data/rendered/img/<doc_id>.png; quality level in data/labels/doc_quality.csv (never in docs/).
Done when: tests check level distribution and that labels stay out of data/docs and data/rendered.

## 2. Extraction pipeline [ ]
Prereq [USER]: Azure account, Document Intelligence + Azure OpenAI resources, keys in .env.
- Pydantic extraction schema per document type.
- Pipeline A: Azure Document Intelligence (layout) → Azure OpenAI structured output.
- Pipeline B: vision model only (baseline).
- Provider interface + mock provider so tests run without keys.
- Cache API responses on disk (cost control).
- Keep raw uncertainty signals per field: OCR word confidence, token logprobs.
Done when: both pipelines run on 20 docs; tests pass with mock provider.

## 3. Eval harness [ ]
- Field-level accuracy (exact + normalized: numbers, dates, units), per pipeline, per doc type, per quality level.
- Fixed golden set of 20 docs; results to reports/eval_<run>.json + markdown table.
Done when: one command prints the comparison table.

## 4. Uncertainty layer (main focus) [ ]
- Signals: OCR confidence, logprobs, self-consistency (n samples), pipeline A/B agreement,
  cross-check against the Bestellung.
- Combine (logistic regression), calibrate (isotonic) on a calibration split.
- Split by Bestellung (no leakage between train/calib/test).
- Outputs: reliability diagram, ECE, precision vs auto-approval-rate curve,
  threshold for 99% field precision.
Done when: report states "At 99% precision, X% of Lieferscheine auto-approved."

## 5. Matching + exception queue [ ]
- Link Rechnung lines ↔ Lieferscheine ↔ Bestellung; ±3% weighing tolerance is normal.
- Reason codes = the 6 discrepancy types; precision/recall per type vs data/labels.
- Streamlit exception queue: approve / reject / correct; corrections logged.
Done when: per-type precision/recall table + working queue.

## 6. MLOps [ ]
- MLflow: log pipeline version, model, prompt hash, metrics per run.
- Prompts as versioned files.
- GitHub Actions: lint, tests, eval on golden set with cached responses;
  fail if field accuracy drops > 1 pp vs baseline.
Done when: a PR that worsens a prompt fails CI.

## 7. Azure via Terraform [ ]
Prereq [USER]: az login, subscription, budget alert.
- azurerm: resource group, storage, Key Vault, Document Intelligence, Azure OpenAI,
  Container App running a FastAPI extraction service. Remote state.
- Documented `terraform destroy`.
Done when: deployed endpoint extracts one Lieferschein; then torn down.

## 8. Monitoring + feedback loop [ ]
- Log per request: confidence, latency, cost.
- Drift check: PSI on confidence distribution vs baseline.
- Corrections from the queue flow back into the labelled set.
Done when: drift report runs on a deliberately shifted batch (e.g. only "bad" scans) and flags it.

## 9. README + demo [ ]
- Problem, architecture diagram, headline metric, eval tables, trade-offs,
  compliance notes (GoBD retention, signatures/eIDAS, XRechnung/ZUGFeRD), next steps.
- 2-minute demo video.