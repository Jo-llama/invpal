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

## 1c. Scans [x]
Done. Lieferscheine only (Rechnungen stay clean digital PDFs, as they wouldn't realistically be
scanned paper). PDF → PNG (pdf2image, 200 dpi), augraphy degradation at 3 hand-tuned severities
(clean/medium/bad, weighted 60/25/15, seeded per-doc so the whole run is reproducible from --seed).
Optional overlays, each with its own seeded probability: a drawn "WARENEINGANG" receiving stamp,
and an augraphy Markup "crossed" strikethrough standing in for a handwritten correction mark.
Output: data/rendered/img/<ls_number>.png; data/labels/doc_quality.csv (ls_number, quality_level,
has_stamp, has_correction) -- kept out of docs/ and rendered/. generator/test_scan.py checks PNG
coverage, distribution within tolerance, Rechnungen excluded, and label-leak absence.
Notes: augraphy's own `default_augraphy_pipeline()` was unusable as "medium" -- on this page layout
it flipped the page 180° and added heavy rainbow color-banding, found only via visual PNG inspection
(the "Done when" tests gave no signal). Replaced with 3 hand-picked, visually-verified augmentation
sets instead of relying on the library default. Also: `cv2.setRNGSeed` requires a signed 32-bit int
and `Geometric(rotate_range=...)` requires integer degrees -- both failed loudly, unlike the silent
default-pipeline issue.

## 2. Extraction pipeline [x]
Done. Azure resources: resource group `invpal-rg` in East US (West Europe rejected new resources
on this subscription), Document Intelligence `invpal-docintel` (F0 free tier), Azure OpenAI
`invpal-openai` with `gpt-5-mini` deployed (GlobalStandard SKU). `extraction/` package: Pydantic
schemas (`LieferscheinExtraction`, `RechnungExtraction`) matching what's actually printed on the
document (not internal master-data IDs); `Provider` protocol with `AzureDocIntelOpenAIProvider`
(pipeline A: DI layout → `chat.completions.parse` structured output), `VisionOnlyProvider`
(pipeline B: image straight to the LLM, PDFs rasterized via pdf2image first), and `MockProvider`
(reads the generator's own ground truth + master data, no network -- used by all 7 pytest tests).
`CachedProvider` disk-caches results by (provider, schema, doc content hash) under
`data/cache/extraction/`. Both pipelines run live against real Azure resources on 20 docs
(10 Lieferscheine + 10 Rechnungen) → `data/extracted/` (40 results).
Notes: gpt-4o is deprecated on Azure as of 2026-03-31; used gpt-5-mini instead (Jo's call).
gpt-5-mini rejects the `logprobs` chat-completions parameter outright (reasoning-model
restriction), so `token_logprob` signals are always None for now -- the plumbing (token-span
reconstruction from `message.content` + `logprobs.content`) stays in place for a model that
supports it. Document Intelligence F0 free tier caps request size at 4MB; one of the 10 sampled
Lieferscheine (LS-2024-0003, "bad" quality, 5.7MB) exceeded it, so pipeline A re-encodes
oversized scans as JPEG (shrinking quality/scale) before sending -- not caught by a unit test,
found by running the live 20-doc batch. Per-field OCR confidence (best-effort substring match
against DI's words, not a layout-aware mapping) looks sane on that same degraded doc: garbled
fields like order_number and position_no dropped to 0.10-0.17 confidence while clean fields
(driver_name, vehicle_plate, unit) stayed at 0.99+ -- a good early signal for step 4. Also
surfaced a real (not a bug) extraction-quality issue step 3's eval harness is meant to catch: the
LLM sometimes misreads the printed German DD.MM.YYYY date into a nonsense ISO date (e.g.
"1505-04-24" instead of "2024-05-15").

## 3. Eval harness [x]
Done. `extraction/golden_set.py` and `extraction/ground_truth.py` pulled out of step 2's
`MockProvider`/CLI so both the extraction run and the eval harness agree on exactly the same
fixed 20 docs (first 10 Lieferscheine + first 10 Rechnungen by filename sort) and the same
ground-truth construction. `eval/` package: `normalize.py` (unit aliases, numeric rounding, text
casefold -- fields with no rule just use exact equality for both variants; dates need no rule
since Pydantic already coerces them to a real `date`), `metrics.py` (per-field exact/normalized
comparison, `Rechnung.positions` matched by `position_no` with missing/extra lines counted as
mismatches, aggregated per pipeline × doc_type × quality_level × field), `report.py` (markdown
table + JSON). `python -m eval` reads step 2's cached `data/extracted/` results (zero new Azure
calls) and ground truth, writes `reports/eval_<run_id>.{json,md}`, prints the table. 13 new
tests, all offline (synthetic fixtures, no dependency on live `data/extracted/`); full suite
(60 tests) green.
Notes: two real findings worth carrying into step 4/9, not pipeline bugs to fix here --
(1) `date` is at 0% accuracy (exact and normalized) across every pipeline/quality bucket: the
LLM systematically misreads the printed German DD.MM.YYYY date into a nonsense ISO date
(see step 2's note) -- this isn't quality-correlated, it happens even on clean docs, so it looks
like a prompt/format issue rather than an OCR-noise issue. (2) pipeline A's `signed` accuracy is
0% across all quality levels while pipeline B is ~100%: pipeline A only ever sends Document
Intelligence's extracted *text* to the LLM, never the image, so it structurally cannot see
whether the signature box has a scribble in it -- a design gap in pipeline A, not something the
eval harness should paper over. Also confirms normalization is pulling its weight: pipeline A's
`unit` exact accuracy is as low as 0.33 (DI/LLM round-tripping drops the unicode "³" to "3") but
normalized accuracy is 1.00, while pipeline B (reads the image directly) is 1.00 on both.

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