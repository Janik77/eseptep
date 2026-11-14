# Configuration and local launch

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export DJANGO_DB_PATH="$PWD/test.sqlite3"
python manage.py migrate
python manage.py test
python manage.py runserver 127.0.0.1:8000
```

Production requires DJANGO_ENV=production, DJANGO_DEBUG=false, a strong
DJANGO_SECRET_KEY, explicit DJANGO_ALLOWED_HOSTS and DJANGO_PRIVATE_MEDIA_ROOT
outside all public web roots. Set CSRF trusted origins to the actual HTTPS origin.
Do not trust forwarded headers unless nginx removes and replaces client headers.
Run `python manage.py check --deploy` with actual production environment before launch.
No production configuration, existing secret or live database was changed by this PR.

## Operator-only secret rotation
The historical committed key must be treated as exposed. Before deployment, generate a
new key using `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
and save it only in the server secret store/environment. Do not paste it into chat,
Git or logs. Rotation invalidates signed sessions/tokens: schedule the logout impact.
Do not retain the exposed key as SECRET_KEY_FALLBACKS. This document does not rotate it.
