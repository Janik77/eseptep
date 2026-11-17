# Protective film ratio: one preliminary parameter

Base: reviewed PR #75, `15ea35e6f57a7df7343def9118c698f95e7b70b2`.

## Scope and units

Only `film_m2 = ceil(area_m2 * consumption)` is configurable. Historical fallback is **1.20 m² of film per 1 m² demolition area**, exactly the former `area * 1.2` floating-point operation before upward rounding. No configured edition means the original mathematical results are preserved.

This is a historical preliminary allowance, **not an approved engineering norm, universal coverage factor or manufacturer specification**. It applies to all three existing demolition types (cosmetic/partial/full) and all three variants (base/optimal/maximum). Existing differences in film names and reference prices remain. No rolls, widths, packaging, overlap model or product compatibility are inferred. Other consumables, removal quantities, prices and formulas are unchanged.

Admin technical range: Decimal with two decimal places, 0.01–99.99, strictly positive. This prevents unsupported values; it does not certify useful or safe bounds for any building. Unit is immutable `m2_per_m2`. The administrator must supply a source, source date and unique version, and verify applicability before publication. Future source dates cannot activate. Migration creates no edition or synthetic values.

## Editions, history and rights

Use Django admin **Demolition film editions**. Create a draft, enter the ratio and provenance, then explicitly publish one edition. Previous edition becomes inactive. Published editions cannot be edited/deleted through admin; create another draft. Activation/deactivation and draft changes share the existing transactional configuration lock.

New calculation snapshots save scope, ratio, unit, version, source/date and method/version. They never consult a newer ratio when reopened. Older snapshots without this metadata remain unchanged and clearly disclose missing provenance.

A result opened before an edition changes cannot silently save with new quantities: the form's `parameter_version` and current active version must match. Missing tokens are rejected. Persistence checks again under the shared lock. Calculation ownership and existing admin permissions remain enforced. This is not a commercial supplier-price setting: independent store quotes remain separate.

## Verification

- 45 pre-change golden results: 5 areas × 3 demolition types × 3 variants. Exact digests after removing only newly added provenance.
- 42 m²: historical 1.20 → 51 m² film; synthetic 1.30 → 55 m². All non-film rows unchanged, derived differences equal 4 × each variant's existing price.
- All other 11 calculator results unchanged across publication.
- Invalid unit/range/precision/reserved versions, ownership, source escaping, published edit denial, missing/stale tokens and immutable saved history.
- Isolated SQLite separate-connection publication/save tests in both orders; no PostgreSQL/load guarantee.
- Browser workflow edits/publishes a synthetic ratio, checks all types/variants, stale refusal, copy, RU/KK 390/1440 and historical snapshot after a newer edition. Verify the exact commit CI and artifacts before claiming browser completion.

## Update existing local copy

Do not clone again. Stop the server. Preserve Git changes and make a verified backup of the actual database, private media and configuration outside Git. Use the final reviewed commit from the report, not an unreviewed moving branch.

```powershell
Set-Location 'C:\Users\Жаник\Desktop\eseptep'
if (git status --porcelain) { throw 'Preserve local changes first' }
git fetch origin feat/demolition-film-parameter
$ReviewSha = 'EXACT_REVIEWED_SHA'
git switch --detach $ReviewSha
if ($LASTEXITCODE -ne 0) { throw 'Switch failed' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe manage.py migrate --plan
# Proceed only after backup verification.
& .\.venv\Scripts\python.exe manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
& .\.venv\Scripts\python.exe manage.py check
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Rollback: stop server, preserve a fresh backup, restore the matching prior reviewed code/database/media/config backup. Do not reverse migrations on the only data copy. No seed command, production update or real-data modification is required by this PR.

## Still not managed here

Bag/disk/respirator/container/truck coefficients, coverage assumptions and reference prices are still code-defined; the other calculators' norms and methodological limitations remain in `PARAMETER_INVENTORY.md`. No new construction or waste-removal assumptions have been approved by this feature.
