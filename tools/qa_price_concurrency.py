"""Real concurrent SQLite connections on an isolated, throwaway CI database."""
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
from django.core.exceptions import ValidationError
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory
from calculators.admin import PriceBookAdmin
from calculators.models import PriceBook,MaterialPrice
from calculators.pricing import attach_quotation,lock_price_configuration
from calculators.services import calculate_materials,save_calculation_for_user
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.views import _get_form_data
from calculators.material_keys import material_key
from accounts.models import UserProfile,ClientProject,Calculation
if connections['default'].settings_dict['ENGINE'] != 'django.db.backends.sqlite3':
 raise SystemExit('This integration test is specifically SQLite; do not claim other backend coverage')
u=User.objects.create_user('isolated-concurrent-client');UserProfile.objects.create(user=u,role='client')
p=ClientProject.objects.create(user=u,title='Synthetic concurrent',city='Test',area_m2=60,rooms=2)
definition=CALCULATORS_BY_SLUG['plitka-keramogranit']; data={**_get_form_data(definition,None),'area':'36.5'}
books=[]
for version,price in [('v1',Decimal('12.34')),('v2',Decimal('25.67'))]:
 b=PriceBook.objects.create(store_name='SYNTHETIC',version=version,source_note='Synthetic concurrency',price_date=date(2026,1,1))
 r=calculate_materials(definition,data)
 for v in r['variants']:
  for row in v['materials']:
   MaterialPrice.objects.create(book=b,calculator_slug=definition['slug'],variant_key=v['key'],material_key=material_key(row['title'],row['unit']),unit=row['unit'],price=price)
 books.append(b.pk)
a=PriceBookAdmin(PriceBook,admin.site);a.message_user=lambda *a,**kw:None
request=RequestFactory().post('/admin/calculators/pricebook/')
def publish(pk):a.activate(request,PriceBook.objects.filter(pk=pk))
publish(books[0]);r=calculate_materials(definition,data);attach_quotation(definition['slug'],r)
results={}; acquired=threading.Event()
def publisher_first():
 try:
  with transaction.atomic():
   lock_price_configuration();acquired.set();time.sleep(.5);publish(books[1])
 except Exception as e:results['writer_error']=repr(e)
 finally:connections.close_all()
t=threading.Thread(target=publisher_first);t.start();assert acquired.wait(5)
start=time.monotonic()
try:save_calculation_for_user(u,definition['slug'],r,p.pk);results['stale']='WRONGLY SAVED'
except ValidationError:results['stale']='blocked'
results['stale_wait']=round(time.monotonic()-start,3);t.join()
assert results['stale']=='blocked' and Calculation.objects.count()==0 and results['stale_wait']>.35,results
publish(books[0]);acquired.clear()
def saver_first():
 try:
  user=User.objects.get(pk=u.pk)
  with transaction.atomic():
   lock_price_configuration();save_calculation_for_user(user,definition['slug'],r,p.pk);acquired.set();time.sleep(.5)
 except Exception as e:results['save_error']=repr(e);acquired.set()
 finally:connections.close_all()
t=threading.Thread(target=saver_first);t.start();assert acquired.wait(5)
start=time.monotonic();publish(books[1]);results['publication_wait']=round(time.monotonic()-start,3);t.join()
saved=Calculation.objects.get();assert saved.result_data['admin_quote']['version']=='v1';assert PriceBook.objects.get(is_active=True).version=='v2';assert results['publication_wait']>.35,results
assert 'save_error' not in results and 'writer_error' not in results,results
results['saved_snapshot']='v1 immutable, v2 active';results['engine']=connections['default'].settings_dict['ENGINE'];print(json.dumps(results))
