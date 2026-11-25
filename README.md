# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-16d4414d` (track: `academic-review`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable pipeline and all supporting documents. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `manuscript-argument-logic-audit`
- Summary: Use when a manuscript's reasoning must be audited, requiring reconstruction of the aim-to-conclusion chain, detection of causal wording under observational designs, scope overshoot, unanchored inference markers, missing alternative explanations, an explicit hypothesis verdict and located severity-rated findings.

## Contents

| File |
|------|
| `SKILL.md` |
| `docs/ERROR_HANDLING.md` |
| `examples/demo-case/case.json` |
| `examples/quickstart.md` |
| `references/output-contract.md` |
| `references/peer-review-checklist.md` |
| `scripts/review_core.py` |
| `scripts/review_ext.py` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/sk_entry.py --input /input --work /app/work --out /app/output
```

A single deterministic pass reads `/input`, computes the deliverable and writes a
contract-complete `/app/output/result.json` plus the human-readable review files
described in `SKILL.md`. The same input always produces byte-identical output; no
network access is used, and fields the materials cannot support are reported
explicitly instead of being left empty.

## Notes

- Pure Python standard library; no network access required.
- Every claim is anchored to paragraph-level evidence; unknown items are reported
  in `uncertainty` instead of being fabricated.
