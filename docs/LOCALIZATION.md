# Russian and Kazakh interface

Django LocaleMiddleware and the standard POST `set_language` endpoint select `ru`/`kk`.
The language cookie survives navigation. No translated URL keys, POST values, model
choices or persisted calculation snapshots are introduced. Compiled `.mo` files are
committed, so installing or running the project on Windows does not require GNU gettext.

## Rendering and preservation

`core.localization` translates explicitly identified system display fields only.
There is no substring/word substitution. Composite calculator summaries and copied
lists are formatted from structured inputs and translated field/material labels.
Calculations and saved snapshots remain canonical. Customer text is not translated.

For calculators and turnkey budgets, changing language navigates to a **read-only**
GET preview of the same input. The preview never calls save/request actions. Other
non-secret field values, project selection and master-template quantities use a
one-use tab session draft, removed on restoration, with a 60-second expiry.
This is not an autosave service; closing the tab does not promise draft recovery.

When a password or file is already selected, language selection fetches only the
standard language form and translated page. It retains the original sensitive input
nodes in memory, never stores password/FileList in browser storage and never posts the
business form. Validation of the replacement form occurs before moving the nodes.
Browser acceptance for this path is mandatory; unit tests alone do not prove FileList
preservation. If the request fails, the old page remains and displays a localized error.

The selected uploaded-project result is reopened through a permission-checked GET
`upload_id`; no upload or estimate write is replayed. No language GET creates a saved
calculation or project.

## Updating translation catalogs

Use GNU gettext and Django's standard commands on a development machine:

```sh
python manage.py makemessages -l kk
python manage.py makemessages -l kk -d djangojs
python manage.py compilemessages
```

System definition messages are retained through `core/translation_phrases.py` gettext
markers; frontend aliases use extraction-only `static/js/i18n_messages.js`. Edit the
`.po` translations and regenerate `.mo` together. Review new labels in context, not
as isolated word replacements. Translation is an implementation, not native-speaker
editorial certification; owner review is still appropriate.

```sh
python manage.py test core.test_localization
node --test calculators/js_tests/*.cjs
```

Browser acceptance additionally covers both languages at 1440/390px, non-empty
forms, file/password preservation, selected variants/projects, copying and saving.
