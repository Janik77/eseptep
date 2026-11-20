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
# Two actual admin POST versus publication orderings, separate DB connections.
from django.test import Client
from unittest.mock import patch
admin_user=User.objects.create_superuser('isolated-concurrent-admin','admin@example.test','Synthetic-Only-835!')
client=Client();client.force_login(admin_user)
def draft(version):
 book=PriceBook.objects.create(store_name='Original synthetic',version=version,source_note='Synthetic concurrency',price_date=date(2026,1,1))
 row=r['materials'][0]
 entry=MaterialPrice.objects.create(book=book,calculator_slug=definition['slug'],variant_key=r['selected_variant'],material_key=material_key(row['title'],row['unit']),unit=row['unit'],price=Decimal('12.34'))
 payload={'store_name':'Edited synthetic','version':version,'source_note':'Edited source','price_date':'2026-01-01','entries-TOTAL_FORMS':'1','entries-INITIAL_FORMS':'1','entries-MIN_NUM_FORMS':'0','entries-MAX_NUM_FORMS':'1000','entries-0-id':entry.pk,'entries-0-book':book.pk,'entries-0-calculator_slug':entry.calculator_slug,'entries-0-variant_key':entry.variant_key,'entries-0-material_key':entry.material_key,'entries-0-unit':entry.unit,'entries-0-price':'88.88','entries-0-price_basis':'canonical','_save':'Save'}
 return book,entry,payload
book,entry,payload=draft('admin-publish-first');acquired.clear()
def admin_publisher_first():
 try:
  with transaction.atomic():
   lock_price_configuration();acquired.set();time.sleep(.5);publish(book.pk)
 except Exception as e:results['admin_pub_error']=repr(e)
 finally:connections.close_all()
t=threading.Thread(target=admin_publisher_first);t.start();assert acquired.wait(5)
start=time.monotonic();response=client.post(f'/admin/calculators/pricebook/{book.pk}/change/',payload);results['draft_wait']=round(time.monotonic()-start,3);t.join()
book.refresh_from_db();entry.refresh_from_db();results['published_edit_status']=response.status_code
assert response.status_code==403,results
assert book.published_at and book.store_name=='Original synthetic' and entry.price==Decimal('12.34'),(book.store_name,entry.price,response.status_code)
assert results['draft_wait']>.35,results
book2,entry2,payload2=draft('admin-draft-first');acquired.clear()
original=PriceBookAdmin.save_related
def paused_save_related(self,request,form,formsets,change):
 original(self,request,form,formsets,change);acquired.set();time.sleep(.5)
def admin_draft_first():
 try:
  response=client.post(f'/admin/calculators/pricebook/{book2.pk}/change/',payload2);results['admin_post_status']=response.status_code
 except Exception as e:results['admin_edit_error']=repr(e);acquired.set()
 finally:connections.close_all()
with patch.object(PriceBookAdmin,'save_related',paused_save_related):
 t=threading.Thread(target=admin_draft_first);t.start();assert acquired.wait(5)
 start=time.monotonic();publish(book2.pk);results['draft_publication_wait']=round(time.monotonic()-start,3);t.join()
book2.refresh_from_db();entry2.refresh_from_db()
assert results['admin_post_status']==302 and book2.published_at and book2.store_name=='Edited synthetic' and entry2.price==Decimal('88.88'),results
assert results['draft_publication_wait']>.35,results
assert not any(k.endswith('_error') for k in results),results
print('ADMIN_CONCURRENCY='+json.dumps(results))
