# Closed pilot Stage 1: 2026-11-19

Base: PR81, 6cf04cf8b1e92d9db2b212fd2d848b655fe1b104.

## Local launch
Use existing canonical checkout and .venv. Single PyCharm configuration: ESEPTEP AI Pilot.
The Windows interpreter path in the shared run configuration is corrected to the existing absolute interpreter.
Verified interpreter execution and the same launcher via CLI; PyCharm Play itself was not clicked.
Open http://127.0.0.1:8220/projects/upload/ . Existing listener is left running. The launcher refuses duplicate listeners and does not reset the database or budget.

## One ordinary browser submission
Official isolated Playwright MCP, synthetic typical-two-room.pdf SHA256 7032f3c703b82c29f394378f677bbb57fa61687a0ff982440a6c106bf84d236c.
One click on Upload and calculate; no repeat after navigation wait timeout. The browser automatically reached the saved whole-plan result.
Completed gpt-6.1-sol: 9327 ms, 3383 input +327 output =3710 tokens.
All five rooms match synthetic ground truth: living18, bedroom18, corridor16.2, kitchen13.2, bathroom6.6 square metres; total72.
No manual area entry. Initial proposed laminate for dry rooms and tile for bathroom. Known-price subtotal61200 KZT; total explicitly unknown, not zero, because laminate/accessory and tile-levelling prices are absent.
Changed living-room finish to tile through the normal form: known-price subtotal215600 KZT, other room areas/finishes preserved. Grouped procurement recomputed. Language change and reload retained result without new analysis.
RU desktop1440 and KK mobile390 captured in ignored meeting-demo-data. Mobile document width390, no horizontal overflow. UI labels switch to Kazakh, source room names stay as on the Russian synthetic drawing. Catalog-source disclaimer still Russian; tracked for subsequent localization work.

## Budget and limitations
Authoritative local application ledger before206 cents, after209 cents; remaining791 cents, next600-cent hold available. Added3 cents is a conservative accounted bound, NOT a provider invoice. Legacy200-cent cap remains accounted. No credential changes, no retries or extra paid calls. Startup/preflight makes no API call.
This is floor-material estimation, not full renovation cost or actual supplier outreach. PyCharm GUI Play and real customer drawings were not tested. No production/merge.

## Regression
14 offline tests passed: core.test_local_ai_budget and projects.test_whole_plan, in-memory test database, AI disabled. Canonical foreign untracked eseptep-review directory untouched.
