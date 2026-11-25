"""Personal loopback-only Workshop demo. No external call at launch, no live data."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HOST, PORT, OFFLINE_PORT = '127.0.0.1', 8250, 8251
OWNER = 'demo-client@example.test'
TITLE = 'Договор DEMO-01 · 40 м²'


def seed():
    from accounts.models import ClientProject, SavedWholeEstimate, ServiceRequest, SupplierProfile, WholeSupplierOffer
    from core.management.commands.seed_meeting_demo import Command
    from django.contrib.auth.models import User
    from django.core.management import call_command
    from projects.models import ProjectUpload, WholePlanEstimate
    from repairs.models import PilotCity, Repair
    from django.db import transaction
    with transaction.atomic():
        call_command(Command(), confirm_isolated=True, verbosity=0)
        user = User.objects.get(username=OWNER)
        project, _ = ClientProject.objects.get_or_create(user=user, title=TITLE, defaults={'city':'Шымкент','area_m2':40,'rooms':4})
        city, _ = PilotCity.objects.get_or_create(key='шымкент', defaults={'name':'Шымкент','enabled':True})
        repair, _ = Repair.objects.get_or_create(project=project, defaults={'city':city,'enabled':True})
        if not ServiceRequest.objects.filter(project=project,request_type='supplier').exists():
            store = SupplierProfile.objects.get(user__username='demo-supplier@example.test')
            seed_upload = ProjectUpload.objects.create(user=user,file='unused-demo-reference.pdf')
            seed_estimate = WholePlanEstimate.objects.create(upload=seed_upload,fingerprint='9'*64,snapshot={})
            saved = SavedWholeEstimate.objects.create(project=project,source=seed_estimate,snapshot={})
            request = ServiceRequest.objects.create(client=user,project=project,whole_estimate=saved,target_supplier=store,
                                                    request_type='supplier',status='responded')
            WholeSupplierOffer.objects.create(request=request,supplier=store,snapshot={
                'total':'12000.00','lines':[{'line_id':'1','quantity':'12','purchase_quantity':'12',
                            'name':'Ламинат учебной серии L','purchase_unit':'упак.', 'unit_price':'1000.00','availability':'available'}]})
    return repair.project_id


def configure(data, live=False, fixture=False):
    if data.is_symlink() or data.parent.is_symlink():
        raise SystemExit('Refusing symlink demo/review directories.')
    data.mkdir(parents=True, exist_ok=True)
    db = data/'contract-demo.sqlite3'
    if db.is_symlink() or (data/'private').is_symlink():
        raise SystemExit('Refusing symlink database or private media directory.')
    # Local-only live run uses the original signed-off ledger and its immutable
    # initialization marker, not this temporary app database.
    ledger = ROOT/'meeting-demo-data'/'local-ai-budget.sqlite3'
    seal = ROOT/'meeting-demo-data'/'local-ai-budget.initialized.json'
    if live and (not seal.is_file() or seal.is_symlink() or not ledger.is_file() or ledger.is_symlink()):
        raise SystemExit('Original initialized and sealed shared pilot ledger is required. No provider access.')
    if fixture:
        from core.local_ai_budget import initialize
        ledger = data/'synthetic-only-ledger.sqlite3'
        initialize(ledger,3,{'offline_browser_fixture': True})
    os.environ.update(DJANGO_SETTINGS_MODULE='config.settings', DJANGO_ENV='development',
        DJANGO_DEBUG='true', DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1',
        ESEPTEP_DEMO_MODE='1', DJANGO_DB_PATH=str(db), DJANGO_PRIVATE_MEDIA_ROOT=str(data/'private'),
        PLAN_AI_ENABLED='1' if live or fixture else '0', ESTIMATE_AI_ENABLED='0',
        OPENAI_LIVE_CONFIRMED='1' if live or fixture else '0', OPENAI_MODEL='gpt-6.1-sol',
        OPENAI_MAX_OUTPUT_TOKENS='1800', OPENAI_TIMEOUT_SECONDS='60',
        OPENAI_PILOT_MAX_RESERVED_CENTS='200',LOCAL_AI_BUDGET_PATH=str(ledger) if live or fixture else '',
        ESEPTEP_CONTRACT_DEMO_ENABLED='1',ESEPTEP_CONTRACT_AI_ENABLED='1' if live or fixture else '0',
        ESEPTEP_CONTRACT_BUDGET_VIEWERS=OWNER, ESEPTEP_CONTRACT_OFFLINE_MOCK='1' if fixture else '0')
    if fixture or not live:
        os.environ['OPENAI_API_KEY'] = 'mock-only' if fixture else ''
    return ledger


def main(argv=None):
    cli = argparse.ArgumentParser()
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument('--live',action='store_true',help='Enable existing shared pilot ledger; never initializes a new budget.')
    mode.add_argument('--offline-demo',action='store_true',help='A repeatable simulated demo; no OpenAI requests or real ledger.')
    mode.add_argument('--fixture-api',type=Path,help='QA only; temporary directory for entirely fake provider.')
    cli.add_argument('--prepare-only',action='store_true')
    args = cli.parse_args(argv)
    if args.fixture_api and args.fixture_api.resolve().parent != Path(os.environ.get('TMPDIR', '/tmp')).resolve():
        raise SystemExit('Temporary QA fixture must be outside the project and directly under TMPDIR.')
    if args.offline_demo:
        # Each launch gets a new throwaway pilot, not a reset of any saved DB.
        with TemporaryDirectory(prefix='eseptep-contract-offline-', ignore_cleanup_errors=True) as tmp:
            return serve(Path(tmp), port=OFFLINE_PORT, live=False, fixture=True, prepare_only=args.prepare_only)
    data = args.fixture_api if args.fixture_api else ROOT/'meeting-demo-data'/'contract-demo'
    return serve(data, port=PORT, live=args.live, fixture=bool(args.fixture_api), prepare_only=args.prepare_only)


def serve(data, *, port, live, fixture, prepare_only):
    with socket.socket() as sock:
        if not prepare_only and sock.connect_ex((HOST, port)) == 0:
            raise SystemExit(f'ESEPTEP already uses {port}. Its process was not modified.')
    ledger = configure(data, live, fixture)
    if fixture:
        from contract_fixture_provider import mock_provider
        mock_provider(data)
    import django
    django.setup()
    if live:
        from core.local_ai_budget import status
        from core.openai_client import validate_configuration
        validate_configuration()
        print(json.dumps({'app_pilot_not_provider_invoice':status(ledger),'startup_provider_calls':0},ensure_ascii=False))
    from django.core.management import call_command
    call_command('migrate',interactive=False,verbosity=0)
    project = seed()
    (data/'scenario.json').write_text(json.dumps({'project':project,'owner':OWNER,
        'base':f'http://{HOST}:{port}','mode':'mock' if fixture else ('live' if live else 'manual')}),encoding='utf-8')
    if fixture:
        print('OFFLINE DEMO · synthetic provider, synthetic ledger, zero real API calls',flush=True)
    print(f'Private loopback demo: http://{HOST}:{port}/accounts/login/?next=/repair/{project}/',flush=True)
    if not prepare_only:
        call_command('runserver',f'{HOST}:{port}',use_reloader=False)


if __name__ == '__main__':
    main()
