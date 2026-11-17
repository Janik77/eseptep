"""Actual SQLite connections: typed edition publication versus upload estimate POST."""
import os,time,threading,json
from pathlib import Path
db=Path(os.environ.get('DJANGO_DB_PATH',''))
if os.environ.get('ESEPTEP_BROWSER_QA')!='1' or not db.is_absolute() or 'browser-qa' not in db.name or 'concurrency' not in db.name:
 raise SystemExit('Explicit isolated browser-qa concurrency database required')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from datetime import date
from decimal import Decimal
from django.db import connections,transaction
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import Client,RequestFactory
from unittest.mock import patch
from calculators.models import RenovationRateEdition
from calculators.admin import RenovationRateEditionAdmin
from calculators.pricing import lock_price_configuration
from projects.models import ProjectUpload
assert connections['default'].settings_dict['ENGINE']=='django.db.backends.sqlite3'
u=User.objects.create_user('typed-concurrency-client')
upload=ProjectUpload.objects.create(user=u,file='synthetic-not-opened.png',area=Decimal('36.50'),repair_level='standard')
client=Client(HTTP_HOST='localhost');client.force_login(u)
a=RenovationRateEditionAdmin(RenovationRateEdition,admin.site);a.message_user=lambda *args,**kwargs:None
request=RequestFactory().post('/admin/calculators/renovationrateedition/')
books=[]
for version,rate in [('typed-race-v1','222.00'),('typed-race-v2','444.00')]:
 books.append(RenovationRateEdition.objects.create(version=version,source_note='Synthetic concurrency only',effective_date=date(2026,1,1),economy_rate=Decimal('111'),standard_rate=Decimal(rate),premium_rate=Decimal('999')).pk)
def publish(pk):a.activate(request,RenovationRateEdition.objects.filter(pk=pk))
publish(books[0])
payload={'action':'estimate','upload_id':upload.pk,'area':'36.5','repair_level':'standard','rate_version':'typed-race-v1'}
results={};acquired=threading.Event()
def publisher():
 try:
  with transaction.atomic():
   lock_price_configuration();acquired.set();time.sleep(.5);publish(books[1])
 except Exception as e:results['publication_error']=repr(e)
 finally:connections.close_all()
t=threading.Thread(target=publisher);t.start();assert acquired.wait(5)
start=time.monotonic();response=client.post('/projects/upload/',payload);results['stale_post_wait']=round(time.monotonic()-start,3);t.join()
upload.refresh_from_db()
assert response.status_code==200 and not upload.estimate_snapshot,results
assert 'Версия ставок изменилась' in response.content.decode(),results
assert results['stale_post_wait']>.35 and 'publication_error' not in results,results
publish(books[0]);acquired.clear()
def paused_lock():
 lock_price_configuration();acquired.set();time.sleep(.5)
def saver():
 try:results['save_status']=client.post('/projects/upload/',payload).status_code
 except Exception as e:results['save_error']=repr(e);acquired.set()
 finally:connections.close_all()
with patch('projects.views.lock_price_configuration',paused_lock):
 t=threading.Thread(target=saver);t.start();assert acquired.wait(5)
 start=time.monotonic();publish(books[1]);results['publication_wait']=round(time.monotonic()-start,3);t.join()
upload.refresh_from_db();snapshot=upload.estimate_snapshot
assert results['save_status']==200 and snapshot['configuration']['version']=='typed-race-v1' and snapshot['total']==8103,results
assert RenovationRateEdition.objects.get(is_active=True).version=='typed-race-v2',results
assert results['publication_wait']>.35 and 'save_error' not in results,results
for lang in ['ru','kk']:
 client.cookies['django_language']=lang
 response=client.get(f'/projects/upload/?upload_id={upload.pk}')
 assert response.status_code==200
 upload.refresh_from_db();assert upload.estimate_snapshot==snapshot
results['snapshot']='typed-race-v1 immutable, typed-race-v2 active'
results['engine']=connections['default'].settings_dict['ENGINE']
print('TYPED_RATE_CONCURRENCY='+json.dumps(results))
