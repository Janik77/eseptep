"""Two real SQLite writers, synthetic fixture, no network/provider calls."""
import os,sys,tempfile,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='eseptep-supplier-') as tmp:
 os.environ.update(DJANGO_SETTINGS_MODULE='config.settings',DJANGO_ENV='test',DJANGO_DB_PATH=str(Path(tmp)/'qa.sqlite3'),DJANGO_ALLOWED_HOSTS='testserver',ESEPTEP_DEMO_MODE='1',PLAN_AI_ENABLED='0',ESTIMATE_AI_ENABLED='0',OPENAI_LIVE_CONFIRMED='0')
 import django;django.setup()
 from django.core.management import call_command
 from django.test import Client
 from django.db import connections
 from django.urls import reverse
 from accounts.test_whole_supplier import WholeSupplierTests
 from accounts.models import SavedWholeEstimate,ServiceRequest,WholeSupplierOffer
 call_command('migrate',verbosity=0,interactive=False)
 fixture=WholeSupplierTests();fixture.client=Client();fixture.setUp()
 def race(user,url,data):
  clients=[Client(),Client()]
  for c in clients:c.force_login(user)
  barrier=threading.Barrier(2)
  def submit(c):
   try:
    barrier.wait(timeout=5)
    return c.post(url,data).status_code
   finally:connections.close_all()
  with ThreadPoolExecutor(max_workers=2) as pool: codes=list(pool.map(submit,clients))
  assert codes==[302,302],codes
 race(fixture.owner,reverse('accounts:save_whole',args=[fixture.source.pk]),{'project_id':fixture.project.pk})
 assert SavedWholeEstimate.objects.count()==1
 saved=SavedWholeEstimate.objects.get()
 url=reverse('accounts:whole_preview',args=[saved.pk]);token=fixture.client.get(url).context
 # Outside Django test runner response.context isn't instrumented; extract only signed form token.
 import re,html
 token=html.unescape(re.search(r'name="token" value="([^"]+)"',fixture.client.get(url).content.decode()).group(1))
 race(fixture.owner,url,{'token':token,'confirm':'yes'})
 assert ServiceRequest.objects.count()==1
 req=ServiceRequest.objects.get();url=reverse('accounts:whole_request',args=[req.pk])
 fixture.client.force_login(fixture.vendor)
 token=html.unescape(re.search(r'name="token" value="([^"]+)"',fixture.client.get(url).content.decode()).group(1))
 race(fixture.vendor,url,{'token':token,'price_0':'100','availability_0':'available'})
 assert WholeSupplierOffer.objects.count()==1
 assert WholeSupplierOffer.objects.get().snapshot['total'] is None
 connections.close_all()
 print('PASS: concurrent save, request confirmation and partial offer each produce exactly one immutable record.')
