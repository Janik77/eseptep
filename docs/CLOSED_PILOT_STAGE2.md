# Closed pilot: readable apartment estimate (Stage 2)

Base: Stage 1 PR #82, `8a9ab4079eb0b8b53b08cb002b4786491771ee66`.

- Room names can be corrected in «Уточнить данные» in RU/KK, including rooms without a readable area.
- Name-only and unchanged-area edits retain source evidence and the existing proposed/project/user finish distinction. Other rooms and original saved revisions remain unchanged.
- Summary and saved PDF show calculated room coverage and the number of priced procurement positions. Null prices remain unknown, not zero. Existing saved snapshots work without migration or re-analysis.
- Newly calculated procurement lines retain canonical material key, calculator, variant and supported specification. Only identical supported specifications combine; unknown registry keys never merge by label. Existing calculator quantities, rounding and price lookup are unchanged.
- New finish selection is explicitly user-selected; project finish evidence is shown separately from a service suggestion.

No new AI call, Windows modification, production deployment or merge. No schema migration. Existing published price editions are not rewritten.

## Validation

Synthetic mocked-provider Django checks cover rename, unchanged evidence, unknown-room edits, invalid names, partial price coverage, specification isolation, immutable old revisions, RU/KK render and PDF. Run:

```
DJANGO_ENV=test .venv/bin/python manage.py test --noinput
DJANGO_ENV=test .venv/bin/python manage.py makemigrations --check --dry-run
```

Focused whole-plan suite: 14 tests passed. Full-suite result recorded in PR. Browser visual acceptance for these changes is not claimed; layout/CSS have not been redesigned.

## Remaining scope

Stage 3: connect the selected whole-plan revision to an owned ClientProject and the existing targeted supplier request flow, then persist item-level supplier offers with idempotent submission and client access. The current supplier button remains explicitly a local simulation.

Not solved here: deterministic cross-page room identity/deduplication, explicit waste/pack-size fields beyond existing calculator output, arbitrary product formats/packaging, real partner pricing. Do not silently invent construction methods or merge similarly named rooms.
