"""Offline synthetic 72m² review. Isolated cloud/local QA, never live provider calls."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
DB=ROOT/'meeting-demo-data/closed-pilot-qa.sqlite3'
DB.parent.mkdir(exist_ok=True)
if DB.is_symlink():raise SystemExit('Refusing symlink DB')
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings',DJANGO_ENV='development',DJANGO_DEBUG='true',
 DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1,testserver',ESEPTEP_DEMO_MODE='1',
 DJANGO_DB_PATH=str(DB),DJANGO_PRIVATE_MEDIA_ROOT=str(ROOT/'meeting-demo-data/closed-pilot-private'),
 PLAN_AI_ENABLED='0',ESTIMATE_AI_ENABLED='0',OPENAI_LIVE_CONFIRMED='0')
import django;django.setup()
from django.core.management import call_command
from django.contrib.auth.models import User
from accounts.models import ClientProject
from django.core.files.base import ContentFile
from projects.models import ProjectUpload,PlanAnalysis
from projects.whole_plan import initial_rooms,persist_estimate
from projects.plan_analysis import analysis_identity
from tools.closed_pilot_db import inspect_db, mark_prepared, read_two_room_fixture
prepared = inspect_db(DB)
call_command('migrate',interactive=False)
if not prepared:
 call_command('seed_meeting_demo',confirm_isolated=True)
user=User.objects.get(username='demo-client@example.test')
ClientProject.objects.get_or_create(user=user,title='ESEPTEP · 72 м²',defaults={'city':'Шымкент','area_m2':'72.00','rooms':5})
raw, rooms = read_two_room_fixture(ROOT)
identity=analysis_identity(f'user:{user.pk}',raw)
analysis=PlanAnalysis.objects.filter(identity=identity).first()
if not analysis:
 upload=ProjectUpload.objects.create(user=user,file=ContentFile(raw,name='synthetic-72m2.pdf'))
 analysis=PlanAnalysis.objects.create(upload=upload,identity=identity,status='completed',model='offline-fixture',rooms=rooms)
 persist_estimate(upload,initial_rooms(analysis),analysis.pk)
elif analysis.model == 'offline-fixture' and analysis.rooms != rooms:
 print('Existing synthetic result kept unchanged. For the corrected plan, open a new typical-plan sample.', file=sys.stderr)
if not prepared:
 mark_prepared(DB)
if '--seed-area-pack-price' in sys.argv:
 from django.db import transaction
 from django.utils import timezone
 from calculators.models import PriceBook
 from calculators.price_import import import_floor_prices
 from calculators.pricing import lock_price_configuration
 version='meeting-demo-area-pack-qa'
 with transaction.atomic():
  lock_price_configuration()
  sku=PriceBook.objects.filter(version=version).first()
  if not sku:
   csv='material,unit,price_basis,pack_coverage,price_kzt\nlaminate,м²,canonical,2.2,4500.00\n'
   sku,_=import_floor_prices(csv.encode(),store='Тестовая упаковка',version=version,
    source='Учебный расчёт, не цена магазина.',date_text='2026-11-20',write=True)
  PriceBook.objects.filter(is_active=True).exclude(pk=sku.pk).update(is_active=False)
  sku.is_active=True;sku.published_at=sku.published_at or timezone.now();sku.save(update_fields=['is_active','published_at'])
print('OFFLINE SYNTHETIC 72m². No AI request. Review: http://127.0.0.1:8233/projects/'+str(analysis.upload_id)+'/whole/',flush=True)
if '--prepare-only' not in sys.argv:call_command('runserver','127.0.0.1:8233',use_reloader=False)
