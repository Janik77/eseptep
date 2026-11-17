# Typed renovation-rate editions: exact coverage and safe upgrade

Base: reviewed #73 (`170e0a400981f5f07d0c5407209c942d1d9d4bb3`). This is a separate test branch, not a production deployment.

## What is actually configurable

Exactly three **monetary project-budget rates in KZT/m²**: economy, standard and premium. They are shared by turnkey estimation and explicit estimates of uploaded projects. They are NOT consumption coefficients, unit material prices, a shop quotation, or a full formula editor.

Django admin: `/admin/calculators/renovationrateedition/`. Create a draft with unique version, source note, effective date and all three positive Decimal rates (two fractional digits). No edition is inserted/published by migration. Partial/missing/negative rates cannot validate. Future-dated editions cannot activate. Activate exactly one edition using its list action. Published values are read-only; corrections require a new edition. Deactivation returns new calculations to clearly labelled historical reference values.

Draft editing, publication and upload estimate persistence use the shared transactional configuration lock introduced in #73. SQLite serialization is tested in the existing CI; PostgreSQL and production load are not certified. Source metadata are publicly displayed; do not enter secrets/private contacts.

## Preserved behaviour and provenance

- The default historical values remain **120000 / 170000 / 250000 KZT/m²**, exactly as in the previous code. They are explicitly labelled historical references, not current store prices.
- With no active edition, existing totals are unchanged. Input precision remains two decimal places; totals retain the existing whole-tenge half-even rounding policy. The regression compares the old float formula to the exact result across all supported marketplace areas from 1.00 to 10000.00 m², for all three historical rates.
- A new/explicit upload estimate stores area, stable tier key, exact rate, total, method identifier and full configuration version/source/date in `estimate_snapshot`.
- Opening that saved estimate or switching language reads its snapshot. New editions do not reprice it. A form opened before a publication change must be reviewed/recalculated before saving.
- Old uploads with no snapshot retain the original historical-rate interpretation on GET, regardless of active editions. No data backfill, automatic repricing or fictitious historical calculation timestamp is performed.
- The interface distinguishes rates for a new estimate from a previously saved result.
- The source note/date are administrator declarations, not independent evidence that these are market prices.

## Still NOT managed by these fields

All consumption/geometry/packaging/option coefficients and reference matrices of the twelve calculators remain code-defined. The previous #73 material-price book remains a separate price layer. Durations, package contents, cities/developers and demo plan analysis are unchanged. See `PARAMETER_INVENTORY.md` for every calculator, active versus unused legacy totals, methodology blockers and the next-stage requirements.

Do not configure arbitrary scripts/formulas, restore historical budget-fitting, or treat a price as a consumption norm. Before expanding norms obtain approved units, conditions, source, bounded valid ranges and regression examples. Electrical and heating estimates are not installation designs.

## Local upgrade

Stop the local server. Preserve Git changes. Back up the actual configured database and upload directories plus `.env` outside the repository; verify restoration on a copy. Keep the pre-upgrade backup. No seed command is needed.

```powershell
Set-Location 'C:\Users\Жаник\Desktop\eseptep'
if (git status --porcelain) { throw 'Preserve local changes before switching' }
git fetch origin feat/typed-calculator-parameters
$ReviewSha = 'EXACT_REVIEWED_SHA'
git switch --detach $ReviewSha
if ($LASTEXITCODE -ne 0) { throw 'Switch failed' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe manage.py migrate --plan
# After verified backup: two additional additive migrations on top of #73.
& .\.venv\Scripts\python.exe manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
& .\.venv\Scripts\python.exe manage.py check
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Rollback with the server stopped: preserve a new backup, switch to prior reviewed SHA, restore its matching pre-upgrade DB/uploads/config. Do not reverse migrations on the only data copy, because new snapshots/configurations would be removed. No production deployment is authorized or performed.

## Actual typed-rate concurrency evidence

`tools/qa_typed_rate_concurrency.py` runs in a separate, explicitly guarded SQLite database in CI. With real separate connections and an actual upload-estimate HTTP POST, publication-first makes the stale POST wait then refuse mutation; save-first makes publication wait and preserves the saved v1 snapshot after v2 becomes active. RU/KK reopening leaves the snapshot unchanged. These checks are specific to SQLite, not PostgreSQL or production load.
