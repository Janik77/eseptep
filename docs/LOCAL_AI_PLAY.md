# ESEPTEP local AI Play

Use existing project and `.venv`, configuration **ESEPTEP AI Pilot**.
Open http://127.0.0.1:8220/projects/upload/ . Upload PDF/photo using **Загрузить и рассчитать**. The existing selected `.env` credential stays on the backend, is not rewritten. Uploaded pages are sent to OpenAI only after the explicit button/disclosure. Existing synthetic login remains available; real documents should be uploaded only by their owner with authority to share them.

`tools/run_local_ai.py` uses the existing whole-plan-live-20261119.sqlite3 and private media. Startup neither seeds nor resets data nor calls the provider. Repeat Play reuses the same ledger. If8220 is already listening, the second process exits and shows the URL; stop the original Play before restarting. The old replay launcher is not the live configuration.

## Budget, not invoice

Owner total ceiling: USD10. The original full pilot USD2 remains reserved, despite its20-cent admission counter. The separately sealed successful one-shot USD6 is reconciled only from its persisted completed request ID, exactly matching usage/report and fixed one-call no-retry code; original sources stay unchanged. All2547 input tokens are priced at the worst long-context cache-write USD5/M and all258 output tokens at USD15/M, plus10%, rounded up with a minimum3c. The new event ledger therefore begins at203c. This is a conservative accountable allowance, NOT a provider invoice or organisation-level billing cap.

Before each NEW call, an atomic event reserves600c. Bound: `(1050000*5 + 1800*15)/1000000*1.10 = USD5.8047`, rounded below600c. Fixed gpt-6.1-sol, default tier, no tools, maximum1800output, official endpoint, SDK retries0. Concurrent calls cannot exceed1000c. Payload fingerprint prevents a duplicate SDK call. Normal upload identity also caches by owner/file/parser.

Only a completed response with matching returned model/tier, response ID and valid complete usage within context/output bounds can release the difference ONCE; every token uses worst rates+10% and cents round upward. Failed/timeout/ambiguous calls retain600c. A missing ledger is never recreated by Play. Exclusive initialization is a separate deliberate operator action, never a way to restore consumed approval. Historical approvals are not edited.

`--check` is local health only, no API request. Initialization was explicitly authorized for this local app, not production. No change to the old live-approval.json and no API-side permissions or billing settings.

References verified2026-11-19:
- https://developers.openai.com/api/docs/models/gpt-6.1-sol
- https://developers.openai.com/api/docs/pricing

## Verification scope

Mock budget/HTTP tests cover concurrency, no retry, reserve retention, sequential QA then owner, replay, invalid usage, manual known-area correction without AI. Browser live validation is separate and must not be claimed from these tests. Proposed next browser-only synthetic fixture: tests/fixtures/plans/typical-two-room.pdf (never an owner/client document).
