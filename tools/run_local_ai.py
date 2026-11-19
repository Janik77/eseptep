"""Repeatable local Play: existing checkout/venv/key, persistent budget and records.
No paid network request on startup. No automatic retry, reset or hidden allowance.
"""
import argparse,hashlib,json,os,socket,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
DB=ROOT/'whole-plan-live-20261119.sqlite3'
LEDGER=ROOT/'meeting-demo-data/local-ai-budget.sqlite3'
SEAL=ROOT/'meeting-demo-data/local-ai-budget.initialized.json'
URL='http://127.0.0.1:8220/projects/upload/'


def history():
    from core.local_ai_budget import usage_bound
    marker=ROOT/'meeting-demo-data/whole-live-20261119.approval.json'
    report=ROOT/'meeting-demo-data/whole-live-20261119.report.json'
    a=json.loads(marker.read_text(encoding='utf-8'));r=json.loads(report.read_text(encoding='utf-8'))
    old=json.loads((ROOT/'meeting-demo-data/live-approval.json').read_text(encoding='utf-8'))
    if not (a.get('consumed') is True and a.get('reserved_cents')==600 and a.get('combined_cap_cents')==800 and old.get('confirmed') is False and old.get('consumed') is True and old.get('max_reserved_cents')==20):raise SystemExit('Historical approval changed; reconcile before enabling.')
    with sqlite3.connect((ROOT/'typical-demo.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
        if c.execute('select reserved_cents from projects_plananalysisbudget where id=1').fetchone()!=(20,):raise SystemExit('Previous pilot ledger changed.')
    with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as c:
        rows=c.execute('select status,model,request_id,usage from projects_plananalysis').fetchall()
    if len(rows)!=1:raise SystemExit('Expected exactly one historical call.')
    state,model,rid,usage=rows[0];usage=json.loads(usage)
    if not (state=='completed' and model=='gpt-6.1-sol' and rid=='resp_051ad2931638634c016afef055a4a487d09a199f8cf9ce4ca5' and r.get('provider_calls')==1 and r.get('provider_calls_after_reload')==1 and r.get('analysis_status')=='completed' and r.get('usage')==usage):raise SystemExit('Historical response cannot be reconciled.')
    if usage != {'input_tokens':2547,'input_tokens_details':{'cache_write_tokens':2544,'cached_tokens':0,'cache_write_tokens_details':{'ttl_12h_tokens':0,'ttl_30m_tokens':2544}},'output_tokens':258,'output_tokens_details':{'reasoning_tokens':0},'total_tokens':2805}:raise SystemExit('Historical usage changed.')
    bound=usage_bound({'id':rid,'status':state,'usage':usage})
    return bound,{'request_id':rid,'usage':usage,'model':model,'service_tier':'default','no_retries':True,'provider_calls':1,'marker_sha256':hashlib.sha256(marker.read_bytes()).hexdigest(),'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'basis':'fixed official SDK max_retries0; one-shot wrapper guards one call; original sources preserved; worst-rate bound NOT invoice'}


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--confirm-local-budget',action='store_true');p.add_argument('--check',action='store_true');args=p.parse_args(argv)
    if DB.is_symlink() or not DB.is_file():raise SystemExit('Existing live result database missing; never create/reset it.')
    if args.confirm_local_budget:
        if SEAL.exists() or LEDGER.exists():raise SystemExit('Budget already initialized; never reset. Use normal Play.')
        bound,evidence=history()
        with SEAL.open('x',encoding='utf-8') as f:json.dump(evidence,f,sort_keys=True);f.flush();os.fsync(f.fileno())
        from core.local_ai_budget import initialize
        initialize(LEDGER,bound,evidence)
    if not SEAL.is_file() or not LEDGER.is_file():raise SystemExit('Local pilot budget not initialized; no API access.')
    os.environ.update(DJANGO_SETTINGS_MODULE='config.settings',DJANGO_ENV='development',DJANGO_DEBUG='true',DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1',ESEPTEP_DEMO_MODE='1',DJANGO_DB_PATH=str(DB),DJANGO_PRIVATE_MEDIA_ROOT=str(ROOT/'meeting-demo-data/whole-live-private'),PLAN_AI_ENABLED='1',ESTIMATE_AI_ENABLED='0',OPENAI_LIVE_CONFIRMED='1',OPENAI_MODEL='gpt-6.1-sol',OPENAI_MAX_OUTPUT_TOKENS='1800',OPENAI_TIMEOUT_SECONDS='60',OPENAI_PILOT_MAX_RESERVED_CENTS='200',LOCAL_AI_BUDGET_PATH=str(LEDGER))
    import django;django.setup()
    from django.conf import settings
    from core.openai_client import validate_configuration
    from core.local_ai_budget import status
    validate_configuration();budget=status(LEDGER)
    print(json.dumps({'url':URL,'key_present':bool(settings.OPENAI_API_KEY),'budget':budget,'scope':'local app pilot, not organisation billing cap','startup_api_calls':0}))
    if args.check:return
    # Refuse a second listener; no other service is stopped by this launcher.
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',8220))==0:raise SystemExit('ESEPTEP already uses8220. Open '+URL+' or stop its existing Play before restarting.')
    from django.core.management import call_command
    call_command('check')
    call_command('runserver','127.0.0.1:8220',use_reloader=False)

if __name__=='__main__':main()
