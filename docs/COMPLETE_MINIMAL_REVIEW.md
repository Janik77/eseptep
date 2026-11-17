# Cohesive minimal interface review

Base: PR #71, `8fca5821307daeb6b8f5db563bfba9458128f800`, fetched from `ui/minimal-three-paths`. This review preserves its accepted light/blue direction and existing integration/security fixes. No production deployment or data migration.

## Changes

- Presentation-only filtering removes duplicate input metrics. Original fractional area remains visible once; the rounded derived tile area is not presented as the user's measurement.
- Money groups thousands consistently; variant switches update the summary using the same locale. Saved snapshots and calculator formulas are unchanged.
- Row subtotal is shown separately only when an additional package charge exists. The top amount is a summary and the bottom amount closes the detailed list.
- Compact shared surfaces and form/table states cover account roles, saved estimates, upload and turnkey.
- Extended isolated browser suite: five widths, both languages, role cabinets, three journeys and capture video. Consult actual CI outcome before treating browser coverage as passed.

## Methodology requiring owner decision

Tile uses `exact_key = (round(area), zone, tile_format)` to select benchmark totals. A fractional area can therefore match an integer benchmark (for example 36.5 floor 60x60). The material quantity helper also rounds larger quantities. This review does not change these rules. Owner should decide whether exact benchmarks apply only to exact areas, or to the existing rounded interval. No displayed precision fix changes a saved total.

## Safe local update

Stop the development server. Back up the existing database, `.env` and private uploads to a local folder outside the repository before changing versions. Do not commit the backup. Keep all local data; no reset, clean, seed or repeat clone.

```powershell
Set-Location 'C:\Users\Жаник\Desktop\eseptep'
$changes = git status --porcelain
if ($LASTEXITCODE -ne 0 -or $changes) { throw 'Preserve local changes before updating.' }
git fetch origin ui/complete-minimal-review
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
$ReviewSha = 'REPLACE_WITH_EXACT_REPORTED_SHA'
git switch --detach $ReviewSha
if ($LASTEXITCODE -ne 0) { throw 'Switch failed' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Install failed' }
& .\.venv\Scripts\python.exe manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Check failed' }
& .\.venv\Scripts\python.exe manage.py showmigrations --plan
# If unapplied migrations exist: stop, verify backups and review the earlier
# integration upgrade instructions. This UI change introduces no migrations.
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Review http://127.0.0.1:8000/. This is a test candidate, not production approval. Prices remain indicative and uploaded-plan analysis demonstrational. Native-language proofreading, assistive technologies and real mobile operating systems require separate review.
