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
1. Synthetic data generator
2. Extraction pipeline
3. Eval harness
4. Uncertainty layer (main focus)
5. Matching and exception queue
6. MLOps (MLflow, CI eval gate)
7. Azure deployment via Terraform
8. Monitoring and feedback loop
9. README and demo video