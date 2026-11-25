#!/bin/bash
set -euo pipefail
cd /opt/eseptep-pilot/current
exec 9>/run/eseptep-enable-ai.lock
flock 9
src=${1:?Pass the absolute path of the transferred ledger}
digest=${2:?Pass its SHA256}
dst=/var/lib/eseptep-pilot/local-ai-budget.sqlite3
envfile=/etc/eseptep-pilot/app.env
[[ "$digest" =~ ^[a-fA-F0-9]{64}$ ]]
tmp=$(mktemp -d /etc/eseptep-pilot/activation.XXXXXX)
trap 'rm -rf "$tmp"' EXIT
if [[ ! -e "$dst" ]]; then
    install -m 0600 "$src" "$tmp/snapshot"
    printf '%s  %s\n' "$digest" "$tmp/snapshot" | sha256sum -c -
    python3 - "$tmp/snapshot" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1])
if c.execute("pragma integrity_check").fetchall()!=[("ok",)]:
    sys.exit("Ledger integrity check failed")
if not c.execute("select count(*) from events where kind='reserve'").fetchone()[0]:
    sys.exit("Missing budget history")
PY
    install -m 0600 -o eseptep-pilot -g eseptep-pilot "$tmp/snapshot" "$dst"
fi
cp -p "$envfile" "$tmp/original"
cp -p core/local_ai_budget.py "$tmp/budget.py"
rollback() {
    cp -p "$tmp/original" "$envfile"
    cp -p "$tmp/budget.py" core/local_ai_budget.py
    systemctl restart eseptep-pilot
}
trap 'rc=$?; if ((rc)); then rollback; fi; rm -rf "$tmp"; exit "$rc"' EXIT
python3 - <<'PY'
from pathlib import Path
p=Path('core/local_ai_budget.py');s=p.read_text()
if '\nCEILING = 1000\n' in s:
    p.write_text(s.replace('\nCEILING = 1000\n','\nCEILING = 1500\n'))
elif '\nCEILING = 1500\n' not in s:
    raise SystemExit("Unknown ledger version")
p=Path('/etc/eseptep-pilot/app.env')
lines=p.read_text().splitlines()
flags={'PLAN_AI_ENABLED','ESEPTEP_CONTRACT_AI_ENABLED','OPENAI_LIVE_CONFIRMED'}
for k in flags:
    if sum(x.startswith(k+'=') for x in lines)!=1: raise SystemExit("Invalid setting "+k)
p.write_text('\n'.join(x.split('=',1)[0]+'=1' if x.split('=',1)[0] in flags else x for x in lines)+'\n')
PY
systemd-run --quiet --wait --pipe --collect -p User=eseptep-pilot -p WorkingDirectory="$PWD" -p EnvironmentFile="$envfile" "$PWD/.venv/bin/python" manage.py shell -c '
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.db import transaction
from accounts.models import ClientProject
from repairs.models import PilotCity, Repair, city_key
from core.closed_pilot import PAID_GROUP, INVITED_GROUP
from core.local_ai_budget import status
from core.openai_client import validate_configuration
validate_configuration()
b=status(settings.LOCAL_AI_BUDGET_PATH)
assert b["next_call_available"] and b["ceiling_cents"]==1500, b
with transaction.atomic():
    u=User.objects.get(username="client@eseptep.test",is_active=True,groups__name=INVITED_GROUP)
    name="Шымкент"
    c,_=PilotCity.objects.get_or_create(key=city_key(name),defaults={"name":name,"enabled":True})
    assert c.enabled, "Existing pilot city disabled"
    p,_=ClientProject.objects.get_or_create(user=u,title="Тест ИИ · квартира 40 м²",defaults={"city":name,"area_m2":40,"rooms":2})
    r,_=Repair.objects.get_or_create(project=p,defaults={"city":c,"enabled":True})
    assert r.enabled and r.city_id==c.pk and city_key(p.city)==c.key
    u.groups.add(Group.objects.get_or_create(name=PAID_GROUP)[0])
print("Plan and contract AI enabled; remaining cents:", b["remaining_cents"])
'
systemctl restart eseptep-pilot
curl --retry 8 --retry-all-errors --retry-delay 1 -fsS -o /dev/null -H 'Host: 82.115.43.144' -H 'X-Forwarded-Proto: https' http://127.0.0.1:18420/accounts/login/
echo 'ESEPTEP AI READY'
