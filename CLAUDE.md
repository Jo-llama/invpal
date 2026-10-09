# InvPal: Lieferschein & invoice extraction service (portfolio project)

## Goal
InvPal turns construction delivery notes, orders and invoices into
structured, validated data and flags discrepancies before payment.
Portfolio project for a (Senior) AI Engineer / MLOps role at VESTIGAS.
Show production ML practice: OCR + GenAI extraction, calibrated
uncertainty estimation, eval-gated CI, Azure via Terraform, monitoring.

## Headline metric
Auto-approval rate at a fixed field precision (e.g. 99%):
"X% of delivery notes processed without a human."

## Stack
Python 3.11+, uv for dependencies, pytest, Pydantic v2, MLflow,
Azure Document Intelligence + Azure OpenAI, Terraform, GitHub Actions.

## Conventions
- Domain terms stay German (Lieferschein, Bestellung, Rechnung, Baustelle,
  Wiegeschein); code and docs in English.
- Everything reproducible from a seed.
- Typed code, small modules, tests next to every module.
- Never commit secrets; use .env locally, Key Vault in Azure.

## Roadmap
See ROADMAP.md (single source of truth for steps, specs and status).

## Workflow (how to work through the roadmap)
- At the start of a session, read ROADMAP.md and find the first step not marked [x].
- Work on ONE step at a time. Present a plan first and wait for Jo's approval.
- If a step or prereq is marked [USER], stop and tell Jo the exact commands to run.
- After implementing: run `uv run pytest`, check the step's "Done when" criterion,
  then mark the step [x] in ROADMAP.md and add a short Notes line with key decisions
  and numbers.
- Finish by proposing a commit message. Never push, never start the next step without approval.