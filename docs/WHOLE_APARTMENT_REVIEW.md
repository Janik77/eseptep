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


## Verified live follow-up, 19 November 2026

After the checkpoint, a supported one-shot mode `tools/qa_whole_plan_live_once.py` was added. It requires `--confirm-one-live-synthetic`, accepts only the committed synthetic PDF SHA `dfcfa8c39d04a16a0c99e91aff70b20b715a820203809d73caaf0cc28e127876`, creates a fresh exclusive consumed approval, refuses an existing run, and uses its own isolated `whole-plan-live-20261119.sqlite3`. This is NOT a copy of or shared ledger with the previous pilot. The previous full $2 cap plus the new conservative $6 reservation is $8, below the owner's $10 ceiling. Do not rerun or delete its marker. A failed run consumes the allowance too.

Bound checked against https://developers.openai.com/api/docs/models/gpt-6.1-sol on19November: even full1,050,000 context at worst long-context cache-write $5/M plus1800output at$15/M and10%regional surcharge is$5.80470. Fixed standard/default tier, no tools, no retry. The new $6 is a reserve, NOT actual spend.

One real call completed in10375ms:2547input tokens, including2544cache-write,258output tokens. The four returned areas were18.00,10.20,4.80,6.00m², sum39.00m², matching the synthetic fixture without manual entry. Upload HTTP302, Russian/Kazakh result HTTP200, saved PDF200. Repeated analysis returned the same record without another provider call. Approximate token price using the documented standard rates is$0.008946 before any applicable regional charges, not a billing statement.

The provider result and report were saved successfully; console output alone then hit a Windows cp1251 encoding error for m². Output was changed to ASCII-safe JSON. The paid request was NOT repeated. Original and follow-up evidence remain in ignored `meeting-demo-data/`; old budget and consumed approval untouched. This live verification is HTTP-based, not visual browser QA, and does not validate arbitrary real projects or twelve-page recognition quality.

Final full application regression before the live harness:176Django tests passed; migrations check clean;10JS tests passed.


Replay the saved successful live result with API OFF:
```powershell
.\.venv\Scripts\python.exe tools\run_whole_plan_review.py --live-result
```
This uses port8221 and the new live QA database, never calls seed/migrate on replay, and does not recalculate the initial saved snapshot. Use the actual URL printed by the launcher. Login is the existing synthetic demo-client@example.test and documented demo password. Existing8220 is unchanged. Stop an already-running8221 process only if it is this QA launcher; do not run a second listener.

Additional HTTP follow-up verified finish change, save, local supplier simulation, saved PDF and restoration with zero extra provider calls. Known-price subtotal changed44,600KZT to202,300KZT when the18m² room switched from laminate to tile. These are synthetic prices, not commercial totals. Missing prices: laminate, underlay, skirting, connectors, threshold, rubbish bags and SVP; work price also absent. Missing prices are explicitly displayed. No video or browser screenshots were recorded in this run.
