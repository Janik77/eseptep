# One self-level mixture coefficient: scope, evidence and limitations

Base: reviewed #74, `eb785d3fc89d31716a02b46a4d05d42af6410f22`. Separate test branch. No main merge, production deployment or user-data edits.

## Exact parameter and unchanged method

Calculator `nalivnoy-pol` uses `area_m2 × thickness_cm × 15`, followed by `ceil(total_kg / 25)` for the main mixture bags. The input explicitly uses centimetres. This slice makes **only that existing 15 kg/(m²·cm) coefficient** administrator-configurable. It does not assert that 15, or any edited value, is valid for a particular manufacturer/product.

The historical default remains exactly 15. The fixed 25 kg bag, floating-point multiplication order, upward bag rounding, auxiliary-material reference matrix, area scaling, needle-roller threshold and all other eleven calculators are unchanged. No legacy target-budget adjustment is reintroduced.

A manufacturer's kg/(m²·mm) figure is a different unit: it requires ×10 before entering a kg/(m²·cm) value. No silent automatic conversion or title-based compatibility inference is performed. A different pack mass is NOT supported by this setting.

## Typed edition

Django admin `/admin/calculators/selflevelmixedition/`: version, source/date, fixed unit and Decimal consumption. Draft default is 15; no edition is created or activated by migration. Publish exactly one edition explicitly. Published editions cannot be changed; a correction requires a new edition. Future source dates, unknown units, zero/negative/nonfinite/oversized values and excessive precision are rejected.

The accepted **0.01–99.99 with two fractional digits is a technical representation/storage bound, not a manufacturer-approved range**. At existing maximum inputs 10000 m² and 20 cm, 99.99 gives 799920 bags; the existing reference total is 2323553760 KZT, below the current Decimal(12,2) storage limit. This is a software bound, not a safe construction recommendation.

Source text/date are administrator declarations, displayed with an explicit applicability warning. Do not include secrets or private contacts. Verify the actual product documentation and method before using a changed coefficient.

## End-to-end consistency and history

The same selected coefficient drives displayed consumption, main-mixture quantity, reference line sums, copied material list and any separate store quote derived from those quantities. Auxiliary rows remain identical. Scope, coefficient, fixed unit, 25 kg pack, version, source/date and method identifier are copied into the saved estimate snapshot.

Publication and persistence share the existing transactional configuration lock. A form calculated under an earlier coefficient cannot silently save after publication changes it. Persistence rechecks the version under the lock; historical estimates never recalculate from a current edition. Old estimates without a parameter snapshot show that provenance is unavailable, without inventing it or changing their totals.

While testing this complete path, an existing bug was reproduced: saved non-variant estimates stored `variants=None`, and localization attempted to iterate it. A separate minimal guard and regression fix that display crash; no formula change.

## Evidence

- Captured pre-change results for boundary/fractional self-level inputs compare exactly after removing only the new provenance field.
- All other eleven default calculator results retain their captured hashes even when this coefficient is active.
- Synthetic coefficient changes alter only the main-mixture row; auxiliary materials are byte-equal.
- Fixed units/bounds, copied quantities, source escaping, nonstaff denial, immutable publication, stale saves and historical snapshots have regression coverage.
- Real SQLite separate-connection publication/save orderings run in an explicitly isolated database in CI. This is not PostgreSQL/load or engineering validation.
- Browser CI records actual admin editing, results/copy/stale save, RU/KK and saved history. Check the exact commit's CI outcome before claiming those browser stages passed.

## Local update

Use the existing copy and `.venv`, stop the server, preserve Git changes and take a verified database/uploads/config backup outside Git. This adds one model migration; it does not rewrite user calculations or seed parameters.

```powershell
Set-Location 'C:\Users\Жаник\Desktop\eseptep'
if (git status --porcelain) { throw 'Preserve local changes first' }
git fetch origin feat/self-level-consumption-parameter
$ReviewSha = 'EXACT_REVIEWED_SHA'
git switch --detach $ReviewSha
if ($LASTEXITCODE -ne 0) { throw 'Switch failed' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe manage.py migrate --plan
# Only after verified backup:
& .\.venv\Scripts\python.exe manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
& .\.venv\Scripts\python.exe manage.py check
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Rollback with the server stopped: preserve a new backup, switch to the prior reviewed SHA and restore the matching pre-upgrade DB/uploads/config. Do not reverse migrations on the only data copy. Real material consumption and applicability remain subject to an approved methodology/product specification.
