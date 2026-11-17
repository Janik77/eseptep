# Material catalogue and one-store pricing review

Based on the verified UI candidate #72 (`1abbc920`). Isolated test branch only. No real store prices, stock, supplier contacts or construction norms are invented or seeded by migrations.

## Implemented

1. Supplier material publication is explicit and default-off, including existing rows. A supplier can create/edit/unpublish only their own product. Public candidates expose product/company name, unit, submitted price/status/delivery and edit time, not personal contacts. Exact canonical name+unit is only a catalogue candidate, never a promise of specification or pack compatibility. No fuzzy matching, package conversion, stock inference or checkout.
2. Django admin has **Price books** with store name, unique version, source note and price date. Add a draft edition and its material rows. Publish exactly one edition using its list action; an older edition becomes inactive. Published editions cannot be edited in admin. A correction requires a new version; deactivation is available.
3. Each price row is scoped by calculator key, variant key, append-only `mat_####` material ID and exact unit. The admin dropdown identifies the canonical material. Blank variant is only for calculators without variants. Unknown keys/units or missing entries do not match. `material_registry.json` is a fixed registry, not a generated runtime order: append IDs, never reassign existing IDs.
4. The result displays a separate **store price quotation** for every variant, including per-line quantity × price, subtotal, version, source/date and coverage. Full coverage means the total of materials at those supplied prices; it does not include labour, delivery, package extras or imply compatibility. Partial coverage is clearly marked, with all unpriced rows listed. The existing reference total stays separate.
5. New saved estimates copy the selected quotation and version into their JSON snapshot. Opening historical estimates does not recompute their quotation. Publication/deactivation and saving use one transactional configuration lock (including SQLite writers). A price-edition change between preview and save requires the user to review the new calculation instead of silently saving a different version.
6. Russian/Kazakh UI, clear empty states, isolated synthetic regression/browser scenarios. All seeded prices in browser QA are explicitly synthetic and are guarded behind the QA-only environment/database.

## Not implemented / not claimed

- Existing hardcoded reference matrices, reference totals, labour, turnout/turnkey and uploaded-project tariffs are NOT now admin-managed. CalculatorTemplate is still metadata, not the runtime formula editor.
- Construction coefficients/norms remain code-defined pending methodological decisions. No string-evaluated formulas or arbitrary execution in admin.
- No multi-shop comparison, automatic best-price selection, orders/payments, stock verification, SKU/specification or package-volume matching, tax/delivery calculation, or market scraping.
- No automatic translation of supplier-authored names/text. If canonical mapping cannot be established, show no match.
- Old estimates without a store-quote snapshot remain reference estimates; migration does not reprice them.
- Date on a supplier card is edit time, not verification time. Price-book date/source are administrator declarations, not independent verification.
- Quote quantity uses existing calculation output. A price configuration cannot cure a disputed quantity or methodology.

## Admin workflow (one store)

1. Review the calculation and selected variant. Open `/admin/calculators/pricebook/add/` using the existing authorized admin account.
2. Enter actual store, version, source/date. These metadata are displayed publicly with quotations; do not put secrets or private contacts into them.
3. Add rows with calculator, exact variant, canonical material ID, unit and real positive price per that unit. Do not enter pack price for a square-metre unit. Verify specifications/pack coverage separately.
4. Save draft; review all entries. In the price-book list select exactly one edition, then publish/activate. Recalculate on the website. Check coverage, line sums and source. Missing prices must not be inferred from reference values.
5. For corrections create a new edition; preserve old editions for provenance. Deactivate if an edition is no longer usable. Saved estimates remain unchanged.

## Local upgrade and rollback, never production

Stop the local server and preserve uncommitted changes. Back up the actual configured SQLite DB via SQLite backup and copy both configured upload directories plus `.env` to a location outside the repository. If the backend is not SQLite, use its native dump/restore instead. Do not run `seed_demo` or QA seed on user data.

```powershell
Set-Location 'C:\Users\Жаник\Desktop\eseptep'
if (git status --porcelain) { throw 'Preserve local changes before update' }
git fetch origin feat/verified-material-offers
$ReviewSha = 'EXACT_REVIEWED_SHA'
git switch --detach $ReviewSha
if ($LASTEXITCODE -ne 0) { throw 'Switch failed' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe manage.py migrate --plan
# Only after verified backup: three additive migrations, no data rewrite or price seed.
& .\.venv\Scripts\python.exe manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; do not start server' }
& .\.venv\Scripts\python.exe manage.py check
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Rollback: stop server; preserve a backup of the new DB first. Switch to prior reviewed SHA and restore the matching pre-upgrade database plus uploads/config together. Do not roll migrations backward on the only copy: that would remove new catalogue/pricing fields. Keep both backups outside Git. This branch includes no deployment workflow.

## Concurrency scope

Publication/deactivation and estimate persistence serialize on a singleton configuration row. Saving acquires its write lock before transactional reads, then validates the snapshot version. A deterministic between-validation-and-save regression is included. An actual isolated two-connection SQLite check also held publication open while saving: the save waited and rejected the obsolete version without creating an estimate. This is not a load test or a PostgreSQL concurrency certification; lock timeout and operational deployment limits still require target-environment testing.
