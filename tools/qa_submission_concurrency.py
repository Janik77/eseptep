"""Concurrent retries on real isolated SQLite: exactly one atomic submission."""
import json
import os
import threading
import time
from pathlib import Path

path = Path(os.environ.get('DJANGO_DB_PATH', ''))
if (os.environ.get('ESEPTEP_BROWSER_QA') != '1' or not path.is_absolute()
        or 'browser-qa' not in path.name or 'concurrency' not in path.name):
    raise SystemExit('Explicit isolated browser-qa concurrency database required')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.contrib.auth.models import User
from django.db import connections
from accounts.models import Calculation, CalculationSubmission, ClientProject, ServiceRequest, UserProfile
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.services import calculate_materials, save_calculation_for_user
from calculators.submissions import result_token, submit_result
from calculators.views import _get_form_data

assert connections['default'].settings_dict['ENGINE'] == 'django.db.backends.sqlite3'
user = User.objects.create_user('submission-concurrency-client')
UserProfile.objects.create(user=user, role='client')
project = ClientProject.objects.create(user=user, title='Synthetic concurrency', area_m2=60, rooms=2)
slug = 'elektrika'
data = _get_form_data(CALCULATORS_BY_SLUG[slug])
result = calculate_materials(CALCULATORS_BY_SLUG[slug], data)
post = {**data, 'action': 'request_master', 'project_id': str(project.pk),
        'submission_token': result_token(user, slug, data)}
entered = threading.Event()
results = {}

def slow_save(*args):
    calculation = save_calculation_for_user(*args)
    entered.set()
    time.sleep(.5)
    return calculation

def worker(name, save):
    try:
        actor = User.objects.get(pk=user.pk)
        start = time.monotonic()
        calculation = submit_result(actor, slug, data, post, result, save)
        results[name] = {'id': calculation.pk, 'seconds': round(time.monotonic() - start, 3)}
    except Exception as exc:
        results[name] = {'error': repr(exc)}
        entered.set()
    finally:
        connections.close_all()

first = threading.Thread(target=worker, args=('first', slow_save))
first.start()
assert entered.wait(5), results
second = threading.Thread(target=worker, args=('retry', save_calculation_for_user))
second.start()
first.join(10)
second.join(10)
assert not first.is_alive() and not second.is_alive(), results
assert all('error' not in item for item in results.values()), results
assert results['first']['id'] == results['retry']['id'], results
assert results['retry']['seconds'] > .35, results
assert Calculation.objects.filter(project=project).count() == 1
assert ServiceRequest.objects.filter(project=project).count() == 1
assert CalculationSubmission.objects.filter(user=user).count() == 1
print('SUBMISSION_CONCURRENCY=' + json.dumps(results))
