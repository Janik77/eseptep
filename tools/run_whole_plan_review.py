"""OFFLINE synthetic whole-floor QA only. Does not touch prior demo DB or API ledger."""
import os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
LIVE_RESULT='--live-result' in sys.argv
DB=ROOT/('whole-plan-live-20261119.sqlite3' if LIVE_RESULT else 'whole-plan-qa.sqlite3')
if LIVE_RESULT and not DB.is_file():raise SystemExit('Saved live result is absent; no new call is permitted.')
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings',DJANGO_ENV='development',DJANGO_DEBUG='true',
 DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1,testserver',ESEPTEP_DEMO_MODE='1',
 DJANGO_DB_PATH=str(DB),DJANGO_PRIVATE_MEDIA_ROOT=str(ROOT/('meeting-demo-data/whole-live-private' if LIVE_RESULT else 'meeting-demo-data/whole-private')),
 PLAN_AI_ENABLED='0',ESTIMATE_AI_ENABLED='0',OPENAI_LIVE_CONFIRMED='0')
import django;django.setup()
from django.core.management import call_command
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from projects.models import ProjectUpload,PlanAnalysis
from projects.plan_analysis import analysis_identity,normalize_rooms,pages
from projects.whole_plan import initial_rooms,persist_estimate
# Refuse a preexisting non-QA database, never reset data.
import sqlite3
p=DB
if p.is_symlink():raise SystemExit('Refusing symlink DB')
if p.exists():
 db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
 tables={r[0] for r in db.execute("select name from sqlite_master where type='table'")}
 if 'auth_user' in tables and db.execute("select count(*) from auth_user where username not in ('demo-client@example.test','demo-supplier@example.test')").fetchone()[0]:raise SystemExit('Non-demo users; refusing QA seed')
 db.close()
if not LIVE_RESULT:
 call_command('migrate',interactive=False)
 call_command('seed_meeting_demo',confirm_isolated=True)
user=User.objects.get(username='demo-client@example.test')
raw=(ROOT/'tests/fixtures/plans/apartment-explication.pdf').read_bytes()
identity=analysis_identity(f'user:{user.pk}',raw)
analysis=PlanAnalysis.objects.filter(identity=identity).first()
if LIVE_RESULT and (not analysis or analysis.status!='completed'):raise SystemExit('Saved completed analysis missing; no API fallback.')
if not analysis:
 upload=ProjectUpload.objects.create(user=user,file=ContentFile(raw,name='synthetic-whole-apartment.pdf'))
 _,frames=pages(upload)
 rooms=[dict(name=n,kind=k,area=a,page=1,source='stated',page_type='floor_plan',evidence=e)
  for n,k,a,e in [('Гостиная','other',18,'18,0 м²'),('Кухня','other',10.2,'10,2 м²'),('Ванная','bathroom',4.8,'4,8 м²'),('Коридор','other',6,'6,0 м²')]]
 analysis=PlanAnalysis.objects.create(upload=upload,identity=identity,status='completed',model='offline-fixture',rooms=normalize_rooms(rooms,frames,strict=True))
if not LIVE_RESULT:record=persist_estimate(analysis.upload,initial_rooms(analysis),analysis.pk)
print('Saved LIVE synthetic result replay; API disabled.' if LIVE_RESULT else 'OFFLINE SYNTHETIC fixture; no provider request; budget ledger unchanged.')
print('Review: http://127.0.0.1:8221/projects/'+str(analysis.upload_id)+'/whole/')
if '--prepare-only' not in sys.argv:call_command('runserver','127.0.0.1:8221',use_reloader=False)
