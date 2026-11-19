# Whole-apartment floor estimate: verified local implementation, 19 November 2026

## Scope and safe launch

Use only the existing `C:\Users\Жаник\Desktop\eseptep` and its `.venv`. No clone/worktree, Docker, production, secrets or prior databases were changed. Existing untracked `eseptep-review/` is untouched. The new migration is applied only to the new offline QA database `whole-plan-qa.sqlite3`; never apply to the user's database without backup and installation review.

PowerShell in the existing checkout:

```powershell
.\.venv\Scripts\python.exe tools\run_whole_plan_review.py
```

URL: http://127.0.0.1:8221/projects/1/whole/ . Sign in as the documented synthetic `demo-client@example.test` with the existing demo password in CLIENT_MEETING_DEMO.md. The launcher prints the actual upload URL; retain it rather than assuming an ID on later runs. Do not start a second process on 8221. This is a new isolated local QA service, not the existing 8220 demo. API and explanation calls are forced OFF. The shown four-room result is an explicitly labelled synthetic offline fixture, not a live recognition result.

PyCharm: keep the existing project and interpreter `.venv\Scripts\python.exe`. Add a Python run configuration for `tools/run_whole_plan_review.py`, working directory the existing project. No new virtual environment. Do not replace the current demo run configuration or stop unrelated services.

## Implemented

- A primary upload-and-calculate submission with explicit OpenAI notice and waiting state. Successful analysis redirects directly to the whole-apartment result.
- Whole-floor parser namespace, all-room prompt, floor-plan vs elevation distinction, explicit numeric evidence/page, unknown values retained as null. PDF limit 12 pages / 5 MB; image 20 MP, resized to 1600 px. Legacy analyses are not silently promoted or charged again.
- Existing tile and flooring calculators, one grouped calculation per finish before purchase rounding; room quantities are labelled proportional allocations. Wet rooms default to proposed tile, dry rooms to proposed laminate; explicit documented finish wins. Finish change and missing-area correction never call the provider.
- Published scoped price book only. Missing prices and work costs remain unknown, not zero. This is floor-material scope, not an all-trades repair quote. Walls require separate heights and dimensions.
- Immutable upload-scoped JSON revisions, active revision pointer, deduplicated repeated saves, owner/session checks, private saved PDF. The supplier action records a LOCAL simulation marker; it is not a real supplier inbox/order or an external message.
- RU/KK templates, responsive CSS and reduced-motion handling are implemented. HTTP language tests do not establish visual mobile correctness.

## Verified and limits

Django tests exercise auto redirect, all four rooms without manual entry, changing finish and reverting it, unknown room without blocking known rooms, changed-file/manual identity isolation, old cache rejection without a new charge, page 2 plan behind page 1 elevation, private PDF, same-file deduplication, other-user denial and local supplier idempotency. Provider responses in these tests are MOCKED.

Full baseline regression: 174 Django tests passed before two final HTTP cases were added. Final run is recorded in the delivery report. 10 existing JavaScript tests and `node --check static/js/whole-plan.js` passed. No claim that source-only responsive CSS was visually tested.

Windows CUA refused browser verification because it could not reliably determine Chrome's current URL. No alternative browser route was used. Real 390/768/1440 screenshots, recording, keyboard visual QA and browser finish flow remain unverified.

No new paid request was sent. Read-only reconciliation found `typical-demo.sqlite3` has reserved_cents=20 and one completed analysis. Its persisted approval is consumed, confirmed=false, max_reserved_cents=20; the launcher refuses another request. The application bound is 200 cents (below the owner's broader $10 ceiling). Budget rows and analysis records currently share the same database; a new isolated DB is not a shared cumulative ledger. Existing demo data, consumed approval and prior ledger were not reset/copied/replaced. A safe shared-ledger/explicit renewed allowance flow is needed before a new isolated live test. Twelve-page worst-case token bounds must also be checked before that test; the previous two-page 20-cent reservation is not a proof for twelve pages.

No main merge, production deploy, Docker cleanup, actual supplier outreach or user-data migration was performed. This is a tested implementation slice, not final end-to-end live acceptance.
