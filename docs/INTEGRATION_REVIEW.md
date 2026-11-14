# Isolated integration review

This branch combines drafts #63, #64, #65, #66, #67 and #68. It is not a
production release or permission to merge. No production service, credentials or
client database was changed.

## Included revisions
- Input validation #63: d868a3724feaafdd08902fbd5694f757989bdd54
- Consistent totals #67 (depends on #63): 6485475f9f2f4e85eedfbc0c9c743f93e6dab152
- Account workflows and explicit project selection #64: 995883dc0c29be9ee1796dbb6a65eb2a45d8e630
- Environment settings #65: fb8e5f6bed92fa07c22d6913ba36fc7fed51c98f
- Private uploads #66 (depends on #65): 80afbb07c175ed68af0ecd63c951ed2765919c26
- Coherent Django UI #68: e51dfb02bbe0ec3a57cfe53525933feab6e27245

All merges applied without textual conflicts. Semantic fixture reconciliation:
calculator save tests now create and explicitly select an owned editable project;
project-selection HTTP tests now supply the required demolition type. The tests
continue to exercise validation and ownership, rather than weakening either.

## Reproducible isolated launch

Requires Python 3.11+ and Node for the JavaScript regression test. Use a new
database and an isolated private-media directory, never a production database.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export DJANGO_ENV=development DJANGO_DEBUG=true
export DJANGO_DB_PATH="$PWD/review.sqlite3"
export DJANGO_PRIVATE_MEDIA_ROOT="$PWD/private_media"
export DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
python manage.py migrate --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
node --test calculators/js_tests/variants.test.cjs
python manage.py runserver 127.0.0.1:8000
```

Register a synthetic client through /accounts/register/, create a project in the
client cabinet, calculate and explicitly select that project before saving.
Do not commit review.sqlite3 or uploaded files. This is a loopback-only review
server, not public hosting. See SECURE_CONFIGURATION.md and PRIVATE_UPLOADS.md
before planning a production deployment.

## Automated verification
- Combined Django suite: 45 tests passed on a temporary test database.
- JavaScript variant regression: 1 test passed (synthetic DOM, not browser proof).
- Django system check: passed.
- Migration drift check: no changes detected.
- git diff --check: passed.
- Browser evidence is reported separately; automated passes alone do not establish
  full visual approval or live production readiness.
- The separate independent security retest of #66 was blocked by a tool safety
  check. The producer reported 13 tests passed. This integration's ordinary suite
  is not a substitute for that missing independent security review.

## Remaining release gates
- Existing public legacy upload bytes need operator quarantine and web-server/CDN
  deny rules; application code does not remove those bytes.
- Rotate the historically committed secret operationally, outside Git.
- Calculator construction norms, tier descriptions and the composition of the
  pre-existing plumbing extra charge remain unverified (see calculators/REVIEW_NOTES.md).
- Recommendations/prices/file analysis are explicitly demonstrational, not live
  vendor offers or validated engineering estimates.
- Review the actual production proxy/storage configuration and backup/restore.
- No real client-data readiness or production security certification is claimed.

## Suggested review order
#65 then #66; #63 then #67; #64 reconciled with those calculator changes; #68
last. Alternatively review this combined branch as one candidate. Do not merge
both the aggregate and equivalent individual patches twice. Owner approval is
required for any merge to main or deployment.

## Integration review follow-up
Untrusted project_id, request_id and response_id now use a shared positive signed
64-bit parser before ORM access. Oversized, malformed, zero and non-ASCII values
produce existing validation errors (project save) or HTTP 400 (workflow actions),
not integer-conversion HTTP 500 errors. Regression coverage includes 5000 digits.

The client cabinet currently lists saved projects/calculations but has no
project-detail or saved-calculation-detail endpoint in accounts/urls.py. No fake
open/detail links were added. Saving redirects to the calculator's clean GET,
which resets visible inputs; the saved variant remains in result_data. A detail
view and post-save continuity need a separate implementation.
