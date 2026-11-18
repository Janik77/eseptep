"""Existing-checkout launcher: no clone, venv creation, dotenv rewrite or DB reset."""
import os,sys,argparse,sqlite3,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
p=argparse.ArgumentParser();p.add_argument('--ai',action='store_true');p.add_argument('--prepare-only',action='store_true');p.add_argument('--port',type=int,default=8220);args=p.parse_args()
os.environ.update(DJANGO_ENV='development',DJANGO_DEBUG='true',DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1',ESEPTEP_DEMO_MODE='1',DJANGO_DB_PATH=str(ROOT/'typical-demo.sqlite3'),DJANGO_PRIVATE_MEDIA_ROOT=str(ROOT/'meeting-demo-private-media'),PLAN_AI_ENABLED='0',ESTIMATE_AI_ENABLED='0',OPENAI_LIVE_CONFIRMED='0',OPENAI_MODEL='gpt-6.1-sol')
# Paid access requires a persisted, owner-confirmed allowance, never inferred from an empty DB.
approval=ROOT/'meeting-demo-data/live-approval.json'
if args.ai and approval.exists():
 a=json.loads(approval.read_text(encoding='utf-8'))
 if a.get('confirmed') is True and a.get('database')==str(ROOT/'typical-demo.sqlite3') and 20<=int(a.get('remaining_cents',0))<=200:
  db=sqlite3.connect((ROOT/'typical-demo.sqlite3').as_uri()+'?mode=ro',uri=True)
  row=db.execute('select reserved_cents from projects_plananalysisbudget where id=1').fetchone();db.close()
  cap=int(a['max_reserved_cents'])
  if row is None or row[0]<int(a['previous_reserved_cents']):raise SystemExit('Budget history missing or rolled back. Reconcile before live use.')
  os.environ['OPENAI_PILOT_MAX_RESERVED_CENTS']=str(cap)
  if row[0]+20<=cap:
   os.environ.update(PLAN_AI_ENABLED='1',OPENAI_LIVE_CONFIRMED='1')
  else: print('Single-call allowance already consumed. Live API remains OFF.')
else:
 if args.ai:print('AI access remains OFF: cumulative remaining pilot allowance must first be confirmed.')
# Refuse symlink/replaced production data BEFORE migration or seed.
dbpath=ROOT/'typical-demo.sqlite3'
if dbpath.is_symlink() or dbpath.resolve().parent!=ROOT.resolve():raise SystemExit('Demo database must be a regular file inside this checkout.')
if dbpath.exists():
 with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as check:
  tables={r[0] for r in check.execute("select name from sqlite_master where type='table'")}
  if 'auth_user' in tables:
   unexpected=check.execute("select count(*) from auth_user where username not in ('demo-client@example.test','demo-supplier@example.test')").fetchone()[0]
   if unexpected:raise SystemExit('Non-demo users detected: refusing migration and seed.')
  for table in ('calculators_pricebook','calculators_renovationrateedition'):
   if table in tables and check.execute('select count(*) from '+table+" where version not like 'meeting-demo-%'").fetchone()[0]:raise SystemExit('Non-demo editions detected: refusing migration and seed.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.core.management import call_command
from datetime import datetime
backup=ROOT/'meeting-demo-data/backups';backup.mkdir(parents=True,exist_ok=True)
if (ROOT/'typical-demo.sqlite3').exists():
 with sqlite3.connect(ROOT/'typical-demo.sqlite3') as source,sqlite3.connect(backup/('meeting-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3')) as dest:source.backup(dest)
call_command('migrate',interactive=False)
call_command('seed_meeting_demo',confirm_isolated=True)
print('URL: http://127.0.0.1:'+str(args.port)+'/projects/upload/')
print('Plan live enabled: '+os.environ['PLAN_AI_ENABLED']+'; explanation live disabled. Existing .env untouched.')
if not args.prepare_only:call_command('runserver','127.0.0.1:'+str(args.port),use_reloader=False)
