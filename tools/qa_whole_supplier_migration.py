"""Isolated migration + verified SQLite backup/restore rehearsal, no real data."""
import os,sys,tempfile,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='eseptep-migration-') as tmp:
 db=Path(tmp)/'before.sqlite3';backup=Path(tmp)/'backup.sqlite3';restored=Path(tmp)/'restored.sqlite3'
 os.environ.update(DJANGO_SETTINGS_MODULE='config.settings',DJANGO_ENV='test',DJANGO_DB_PATH=str(db),PLAN_AI_ENABLED='0',ESTIMATE_AI_ENABLED='0',OPENAI_LIVE_CONFIRMED='0')
 import django;django.setup()
 from django.core.management import call_command
 from django.db import connections
 call_command('migrate','accounts','0005',verbosity=0,interactive=False)
 with sqlite3.connect(db) as source:
  source.execute("INSERT INTO auth_user(password,last_login,is_superuser,username,last_name,email,is_staff,is_active,date_joined,first_name) VALUES ('!','2026-01-01',0,'synthetic-legacy','','',0,1,'2026-01-01','')")
  source.commit()
  with sqlite3.connect(backup) as out:source.backup(out)
 call_command('migrate',verbosity=0,interactive=False)
 with sqlite3.connect(db) as source:
  assert source.execute("select count(*) from auth_user where username='synthetic-legacy'").fetchone()[0]==1
  assert source.execute("select count(*) from sqlite_master where name='accounts_savedwholeestimate'").fetchone()[0]==1
  assert source.execute('pragma integrity_check').fetchone()[0]=='ok'
 with sqlite3.connect(backup) as source,sqlite3.connect(restored) as out:source.backup(out)
 with sqlite3.connect(restored) as out:
  assert out.execute('pragma integrity_check').fetchone()[0]=='ok'
  assert out.execute("select count(*) from auth_user where username='synthetic-legacy'").fetchone()[0]==1
  assert out.execute("select count(*) from sqlite_master where name='accounts_savedwholeestimate'").fetchone()[0]==0
 connections.close_all()
 print('PASS: accounts0005 backup -> forward migration preserves legacy row -> independent restore verifies original schema/data.')
