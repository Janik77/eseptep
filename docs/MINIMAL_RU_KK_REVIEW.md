# Minimal three-path interface: review candidate

This is a separate test branch. Do not deploy or merge it without the owner's review.

## Scope

The home screen gives equal weight to material calculations, the existing preliminary turnkey budget and project upload. All twelve calculators use the same neutral presentation. Business formulas, technical POST keys and saved data remain stable. Prices are indicative; uploaded-plan analysis is still explicitly a demonstration.

The new interface uses a single Noto Sans family with Cyrillic Extended/Kazakh support and one restrained blue accent. Google Fonts is an external dependency; system sans-serif remains the fallback when unavailable.

## Existing Windows copy, PowerShell

Do not clone again and do not use `git reset --hard` or `git clean`. Close the local development server first. The commands below stop if there are uncommitted changes; preserve them before switching. They do not run against the VPS.

```powershell
Set-Location 'C:\Users\Жаник\Desktop\eseptep'
$changes = git status --porcelain
if ($LASTEXITCODE -ne 0) { throw 'Git status failed' }
if ($changes) { throw 'There are local changes. Preserve them before updating; do not reset them.' }
git fetch origin ui/minimal-three-paths
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
# Replace REVIEW_SHA with the exact reviewed commit supplied in the report.
$ReviewSha = 'REVIEW_SHA'
git switch --detach $ReviewSha
if ($LASTEXITCODE -ne 0) { throw 'Switch failed' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& .\.venv\Scripts\python.exe manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Django check failed' }
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000/. Keep the existing `.env`, database and private uploads. No migration or seed command is needed solely for the visual change. If Django reports unapplied migrations from an older local version, stop and back up the database/uploads before following the underlying integration upgrade instructions; do not assume this checkout is current.

## Review checklist

- Desktop 1440px / mobile 390px, RU and KK: home, catalog, one empty and filled calculator.
- All twelve calculator routes, validation, master template, variants, copy and save.
- Language selection stays on the current screen and does not send save/request POST again.
- Input values, selected variant and project survive language change without duplicate records.
- All user-facing claims remain truthful; demo data and indicative prices are labelled.

Browser tests must be reported independently of Django test-client results. A successful HTML response alone is not visual acceptance.
