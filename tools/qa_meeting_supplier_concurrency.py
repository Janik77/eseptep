"""Repeat one explicit demo request concurrently in an isolated SQLite DB."""
import os
if os.environ.get('ESEPTEP_BROWSER_QA') != '1' or 'browser-qa' not in os.environ.get('DJANGO_DB_PATH', ''):
    raise SystemExit('Dedicated synthetic browser-qa database required')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
from django.test import Client, override_settings
from django.test.utils import setup_test_environment
from django.contrib.auth.models import User
from django.db import close_old_connections
from accounts.models import Calculation, ClientProject, ServiceRequest, SupplierProfile, UserProfile
setup_test_environment()
user=User.objects.create_user('concurrent-demo-client')
UserProfile.objects.create(user=user,role='client')
recipient=User.objects.create_user('demo-supplier@example.test')
UserProfile.objects.create(user=recipient,role='supplier')
SupplierProfile.objects.create(user=recipient,company_name='SYNTHETIC STORE',city='Шымкент',address='Test')
project=ClientProject.objects.create(user=user,title='SYNTHETIC PROJECT',city='Шымкент',area_m2='36.5',rooms=2)
calculation=Calculation.objects.create(project=project,calculator_slug='plitka-keramogranit',area_m2='36.5',rooms=2,thickness=0,segment='economy',result_data={'input':{'zone':'floor'},'materials':[{'title':'Плитка','quantity':42,'unit':'м²'}]})
url=f'/accounts/calculations/{calculation.pk}/request-offer/'
clients=[Client() for _ in range(8)]
for client in clients:client.force_login(user)
with override_settings(ESEPTEP_DEMO_MODE=True,PRODUCTION=False,ALLOWED_HOSTS=['testserver']):
    token=clients[0].get(url).context['request_token']
    def submit(client):
        close_old_connections()
        try:
            response=client.post(url,{'request_token':token,'confirm':'yes'})
            assert response.status_code==302,response.status_code
            return response.url
        finally:close_old_connections()
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(submit,clients))
assert len(set(results))==1,results
assert ServiceRequest.objects.count()==1
print('8 concurrent POSTs -> 1 targeted demo request; no external notification')
