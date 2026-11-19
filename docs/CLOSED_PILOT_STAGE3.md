# Closed pilot Stage 3: apartment estimate → local store offer

Stacked after Stage 2 PR83 (`ec305c9e0a0943a7c2ef82b40c3c56cd8c67cb8a`). No merge, deploy, real supplier outreach, payment or provider request.

## One path

1. From an owned whole-plan result, open **Запросить предложение**.
2. Select an existing owned ClientProject. The explicit POST attaches an immutable copy of that exact WholePlanEstimate revision. Old source revisions cannot be newly saved after the active result changed; repeated save returns the same record.
3. Check the test shop, exact quantities and unknown prices. Only explicit signed confirmation creates a targeted ServiceRequest in its local cabinet. This is not an order or purchase commitment.
4. Log in as the seeded local demo supplier, open the request and enter each unit price/availability. Blank price and unconfirmed availability remain unknown. The server multiplies frozen quantities, not client-submitted quantities or totals.
5. The client finds the saved apartment estimate and store response in the original project's dashboard. Original estimate PDF and separate offer PDF read only saved snapshots. Later price-book changes do not reprice them.

One immutable supplier offer is accepted per request. Repeated submissions return that stored offer; amendments/new negotiated proposals are not part of this slice. The generic legacy total-price form cannot submit a response to these requests. No assignment to real suppliers is enabled: the existing demo-mode/non-production gate and explicitly seeded demo account are retained.

## Database and update safety

New additive migration `accounts.0006_whole_supplier_pilot` creates SavedWholeEstimate and WholeSupplierOffer, nullable ServiceRequest linkage, and duplicate-prevention constraints. It does not rewrite legacy estimates or introduce fake totals. Existing apps/users/databases on Windows were not changed by this cloud implementation.

Before applying to any persistent stand: stop its writer normally, use SQLite's backup API (not just a copy of the main file while WAL may exist), verify `PRAGMA integrity_check`, and retain that backup plus the prior code SHA. Then migrate and run checks. Restore rehearsal is provided below on disposable data. Do not run a reverse migration against real new offers: it would remove the new records. Prefer fixing forward or retaining the schema on code rollback; a database restore requires explicit scope and reconciliation of any activity after the backup, including AI budget accounting.

## Offline verification

```
DJANGO_ENV=test .venv/bin/python manage.py test --noinput
DJANGO_ENV=test .venv/bin/python tools/qa_whole_supplier_concurrency.py
DJANGO_ENV=test .venv/bin/python tools/qa_whole_supplier_migration.py
DJANGO_ENV=test .venv/bin/python manage.py makemigrations --check --dry-run
node --test calculators/js_tests/*.test.cjs
```

The concurrency rehearsal uses two simultaneous SQLite writers for save, request confirmation and offer submission; each must create exactly one record. Migration rehearsal verifies old data survives forward migration and an independent restored backup contains the old schema/data.

`tools/run_closed_pilot_review.py` seeds only an isolated synthetic 72m² fixture and demo accounts, with both AI paths disabled. It never reuses a live-result database. It is a **review fixture**, not the canonical Windows launcher. Known rooms:18+18+16.2+13.2+6.6m². Authentication comes from existing seed_meeting_demo documentation. Use `--prepare-only` for fixture setup without a server.

## Remaining limits

No purchase acceptance, negotiated revisions, real partner onboarding or external notifications. Legacy broad request flows retain their existing behavior; the new path is explicitly addressed and owner-scoped. Cross-page room reconciliation and richer package/waste provenance still need separate work. Visual evidence and exact test counts are reported with the final commit, not inferred from HTTP tests.
