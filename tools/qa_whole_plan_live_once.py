"""Explicit, non-replayable synthetic QA. Independent $6 cap, not a shared ledger.
Previous pilot's full $2 cap plus this cap = $8, below the owner's $10 ceiling.
Never clears a marker or retries. A failed preparation consumes this allowance too.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIXTURE_SHA='dfcfa8c39d04a16a0c99e91aff70b20b715a820203809d73caaf0cc28e127876'
MARKER=ROOT/'meeting-demo-data/whole-live-20261119.approval.json'
DB=ROOT/'whole-plan-live-20261119.sqlite3'
REPORT=ROOT/'meeting-demo-data/whole-live-20261119.report.json'


def cost_bound():
    # Full context ceiling rather than an assumption about image tokenization.
    # Long-context cache-write $5/M, output $15/M, plus10% regional surcharge.
    return (Decimal(1050000)*Decimal('5')+Decimal(1800)*Decimal('15'))/Decimal(1000000)*Decimal('1.10')


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--confirm-one-live-synthetic',action='store_true')
    args=parser.parse_args(argv)
    raw=(ROOT/'tests/fixtures/plans/apartment-explication.pdf').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=FIXTURE_SHA:raise SystemExit('Synthetic fixture hash differs; no request allowed.')
    if cost_bound()>Decimal('6') or Decimal('2')+Decimal('6')>Decimal('10'):raise SystemExit('Budget bound failed')
    if not args.confirm_one_live_synthetic:
        print(json.dumps({'preflight_only':True,'fixture_sha256':FIXTURE_SHA,'maximum_new_usd':'6.00','previous_full_cap_usd':'2.00','combined_cap_usd':'8.00','calculated_upper_bound_usd':str(cost_bound())}))
        return
    if MARKER.exists() or DB.exists() or REPORT.exists():raise SystemExit('One-shot run already reserved or created; refusing retry. Preserve all evidence.')
    previous=ROOT/'typical-demo.sqlite3'
    with sqlite3.connect(previous.as_uri()+'?mode=ro',uri=True) as db:
        reserved=db.execute('select reserved_cents from projects_plananalysisbudget where id=1').fetchone()
    if not reserved or not 20<=reserved[0]<=200:raise SystemExit('Prior budget history needs reconciliation')
    os.chdir(ROOT);sys.path.insert(0,str(ROOT))
    os.environ.update(DJANGO_SETTINGS_MODULE='config.settings',DJANGO_ENV='development',DJANGO_DEBUG='false',
        DJANGO_ALLOWED_HOSTS='testserver,localhost,127.0.0.1',ESEPTEP_DEMO_MODE='1',
        DJANGO_DB_PATH=str(DB),DJANGO_PRIVATE_MEDIA_ROOT=str(ROOT/'meeting-demo-data/whole-live-private'),
        PLAN_AI_ENABLED='0',ESTIMATE_AI_ENABLED='0',OPENAI_LIVE_CONFIRMED='0',OPENAI_MODEL='gpt-6.1-sol',
        OPENAI_MAX_OUTPUT_TOKENS='1800',OPENAI_TIMEOUT_SECONDS='45',OPENAI_PILOT_MAX_RESERVED_CENTS='20')
    import django;django.setup()
    from django.conf import settings
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith(('REPLACE_','PASTE_')):raise SystemExit('Existing key unavailable; not modified.')
    from pypdf import PdfReader
    import io
    if len(PdfReader(io.BytesIO(raw)).pages)!=1:raise SystemExit('One-page synthetic fixture required')
    # Exclusive durable file reserves the independent cap BEFORE any live operation.
    record={'confirmed':True,'consumed':True,'scope':'one synthetic whole-apartment HTTP upload',
        'fixture_sha256':FIXTURE_SHA,'database':str(DB),'reserved_cents':600,'previous_full_cap_cents':200,
        'combined_cap_cents':800,'owner_ceiling_cents':1000,'created_at':datetime.now(timezone.utc).isoformat(),
        'no_refund_on_error':True,'not_shared_with_prior_ledger':True}
    with MARKER.open('x',encoding='utf-8') as f:
        json.dump(record,f,indent=2);f.flush();os.fsync(f.fileno())
    from django.core.management import call_command
    call_command('migrate',interactive=False,verbosity=0)
    call_command('seed_meeting_demo',confirm_isolated=True,verbosity=0)
    from django.contrib.auth.models import User
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.test import Client
    from unittest.mock import patch
    from projects import plan_analysis
    from projects.models import PlanAnalysis,PlanAnalysisBudget,WholePlanEstimate
    original=plan_analysis.responses_create
    calls=0
    def guarded(**payload):
        nonlocal calls
        if calls or payload.get('model')!='gpt-6.1-sol' or payload.get('max_output_tokens')!=1800 or payload.get('tools'):
            raise RuntimeError('one_shot_guard')
        content=payload['input'][0]['content']
        if sum(p.get('type')=='input_image' for p in content)!=1:raise RuntimeError('one_image_guard')
        calls+=1
        return original(**payload)
    client=Client();client.force_login(User.objects.get(username='demo-client@example.test'))
    settings.PLAN_AI_ENABLED=True;settings.OPENAI_LIVE_CONFIRMED=True
    try:
        with patch('projects.plan_analysis.responses_create',side_effect=guarded):
            response=client.post('/projects/upload/',{'action':'upload_calculate','file':SimpleUploadedFile('synthetic-four-room.pdf',raw)})
    finally:
        settings.PLAN_AI_ENABLED=False;settings.OPENAI_LIVE_CONFIRMED=False
    analysis=PlanAnalysis.objects.order_by('-pk').first()
    estimate=WholePlanEstimate.objects.order_by('-pk').first()
    report={'provider_calls':calls,'http_status':response.status_code,'analysis_status':analysis.status if analysis else None,
        'error_code':analysis.error_code if analysis else None,'model':analysis.model if analysis else None,
        'elapsed_ms':analysis.elapsed_ms if analysis else None,'usage':analysis.usage if analysis else {},
        'rooms':analysis.rooms if analysis else [],'estimate_id':estimate.pk if estimate else None,
        'known_area':estimate.snapshot['known_area'] if estimate else None,'new_independent_reservation_usd':'6.00',
        'old_pilot_db_unchanged':True,'no_retry':True,'browser_verified':False}
    if estimate:
        url=f'/projects/{estimate.upload_id}/whole/'
        report['ru_http']=client.get(url,HTTP_ACCEPT_LANGUAGE='ru').status_code
        report['kk_http']=client.get(url,HTTP_ACCEPT_LANGUAGE='kk').status_code
        report['pdf_http']=client.get(f'/projects/{estimate.upload_id}/whole/{estimate.pk}/pdf/').status_code
        report['repeat_analysis_id']=plan_analysis.analyze(estimate.upload).pk
        report['provider_calls_after_reload']=calls
    with REPORT.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':
    main()
