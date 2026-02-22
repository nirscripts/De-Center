# De-Center

Data-first project for identifying contradictions between official policy claims and community impact evidence about California AI/data center electricity and water usage.

## Scope (Step 2: Data Acquisition)
- Collect official policy and assessment documents (2025–2026).
- Collect local/community counter-data (news, filings, utility notices).
- Build a hand-labeled contradiction benchmark in `data/ground_truth.json`.

## Structure
- `data/raw/` source text, PDFs, exports
- `data/processed/` cleaned extracts and normalized tables
- `notebooks/` EDA and source review notebooks
- `src/` utility scripts (no RAG logic yet)

## Initial dependencies
See `requirements.txt`.
