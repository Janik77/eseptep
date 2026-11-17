"""Real isolated SQLite demolition film parameter publication versus estimate persistence."""
import os,time,threading,json
from pathlib import Path
db=Path(os.environ.get('DJANGO_DB_PATH',''))
if os.environ.get('ESEPTEP_BROWSER_QA')!='1' or not db.is_absolute() or 'browser-qa' not in db.name or 'concurrency' not in db.name:
 raise SystemExit('Explicit isolated browser-qa concurrency database required')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from datetime import date
from decimal import Decimal
from django.db import transaction,connections
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from calculators.admin import DemolitionFilmEditionAdmin
from calculators.models import DemolitionFilmEdition
from calculators.pricing import attach_quotation,lock_price_configuration
from calculators.services import calculate_materials,save_calculation_for_user
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.views import _get_form_data
from accounts.models import UserProfile,ClientProject,Calculation
assert connections['default'].settings_dict['ENGINE']=='django.db.backends.sqlite3'
u=User.objects.create_user('demolition-concurrency-client');UserProfile.objects.create(user=u,role='client')
p=ClientProject.objects.create(user=u,title='Synthetic concurrent',area_m2=60,rooms=2)
d=CALCULATORS_BY_SLUG['demontazh'];data={**_get_form_data(d,None),'area':'42','demolition_type':'partial','selected_variant':'optimal'}
books=[]
for version,value in [('consumption-race-v1','1.20'),('consumption-race-v2','1.30')]:
 books.append(DemolitionFilmEdition.objects.create(version=version,source_note='Synthetic concurrency only',source_date=date(2026,1,1),consumption=Decimal(value)).pk)
a=DemolitionFilmEditionAdmin(DemolitionFilmEdition,admin.site);a.message_user=lambda *args,**kwargs:None
request=RequestFactory().post('/admin/calculators/demolitionmixedition/')
def publish(pk):a.activate(request,DemolitionFilmEdition.objects.filter(pk=pk))
publish(books[0]);r=calculate_materials(d,data);attach_quotation(d['slug'],r)
results={};acquired=threading.Event()
def publisher():
 try:
  with transaction.atomic():
   lock_price_configuration();acquired.set();time.sleep(.5);publish(books[1])
 except Exception as e:results['publication_error']=repr(e)
 finally:connections.close_all()
t=threading.Thread(target=publisher);t.start();assert acquired.wait(5)
start=time.monotonic()
try:save_calculation_for_user(u,d['slug'],r,p.pk);results['stale']='WRONGLY SAVED'
except ValidationError:results['stale']='blocked'
results['stale_wait']=round(time.monotonic()-start,3);t.join()
assert results['stale']=='blocked' and Calculation.objects.count()==0 and results['stale_wait']>.35,results
publish(books[0]);acquired.clear()
def saver():
 try:
  user=User.objects.get(pk=u.pk)
  with transaction.atomic():
   lock_price_configuration();save_calculation_for_user(user,d['slug'],r,p.pk);acquired.set();time.sleep(.5)
 except Exception as e:results['save_error']=repr(e);acquired.set()
 finally:connections.close_all()
t=threading.Thread(target=saver);t.start();assert acquired.wait(5)
start=time.monotonic();publish(books[1]);results['publication_wait']=round(time.monotonic()-start,3);t.join()
saved=Calculation.objects.get();assert saved.result_data['parameter_snapshot']['version']=='consumption-race-v1'
assert saved.result_data['materials'][1]['quantity']==51
assert DemolitionFilmEdition.objects.get(is_active=True).version=='consumption-race-v2'
assert calculate_materials(d,data)['materials'][1]['quantity']==55
assert results['publication_wait']>.35 and not any(k.endswith('_error') for k in results),results
results['snapshot']='v1 51m2 immutable, v2 55m2 active';results['engine']=connections['default'].settings_dict['ENGINE']
print('DEMOLITION_CONCURRENCY='+json.dumps(results))
