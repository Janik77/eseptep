"""Create a private, disposable Repair acceptance fixture; never use real data."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    if os.environ.get('DJANGO_ENV') != 'test' or os.environ.get('ESEPTEP_REPAIR_BROWSER_QA') != '1':
        raise SystemExit('Only the isolated Repair browser QA environment may seed this data.')
    if any(os.environ.get(key, '0') != '0' for key in ('PLAN_AI_ENABLED', 'ESTIMATE_AI_ENABLED', 'OPENAI_LIVE_CONFIRMED')):
        raise SystemExit('Provider-disabled fixture required.')
    if len(sys.argv) != 2:
        raise SystemExit('Pass an explicit disposable output directory.')
    output = Path(sys.argv[1]).resolve(strict=True)
    database = Path(os.environ.get('DJANGO_DB_PATH', '')).resolve()
    if database.parent != output or database.name != 'repair-browser.sqlite3' or database.exists():
        raise SystemExit('Use a fresh explicitly isolated repair-browser.sqlite3 database.')

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from accounts.models import (
        ClientProject, MasterProfile, MasterResponse, SavedWholeEstimate,
        ServiceRequest, SupplierProfile, UserProfile, WholeSupplierOffer,
    )
    from projects.models import ProjectUpload, WholePlanEstimate
    from repairs.models import PilotCity, Repair

    call_command('migrate', verbosity=0)
    password = 'Repair-local-QA-only!'
    def identity(role, suffix=''):
        email = f'repair-{role}{suffix}@example.test'
        user = get_user_model().objects.create_user(username=email, email=email, password=password)
        UserProfile.objects.update_or_create(user=user, defaults={'role': role, 'city': 'Шымкент'})
        return user

    client = identity('client')
    other = identity('client', '-unrelated')
    supplier = SupplierProfile.objects.create(user=identity('supplier'), company_name='Пилот · Магазин',
                                               city='Шымкент', address='Демо-офис')
    master = MasterProfile.objects.create(user=identity('master'), full_name='Пилот · Мастер',
                                           city='Шымкент', specialization='Полы')
    reviewer = identity('admin')
    shymkent = PilotCity.objects.create(name='Шымкент', enabled=True)
    taraz = PilotCity.objects.create(name='Тараз', enabled=False)
    def project(title, city):
        return ClientProject.objects.create(user=client,title=title,city=city,area_m2=40,rooms=2)
    disabled = project('Пилот · Другой город', 'Тараз')
    Repair.objects.create(project=disabled, city=taraz, enabled=True)
    same_city = project('Пилот · Не включён', 'Шымкент')
    Repair.objects.create(project=same_city, city=shymkent)
    results = {'disabled': disabled.pk, 'sameCityDisabled': same_city.pk}
    for language in ('ru', 'kk'):
        pr = project('Тестовая квартира' if language=='ru' else 'Сынақ пәтері','Шымкент')
        Repair.objects.create(project=pr, city=shymkent, enabled=True, reviewer=reviewer,
                              delivery_address='Синтетический адрес QA 123')
        source_upload = ProjectUpload.objects.create(user=client, file='synthetic-unused.pdf')
        source = WholePlanEstimate.objects.create(upload=source_upload, fingerprint='a'*64, snapshot={})
        saved = SavedWholeEstimate.objects.create(project=pr, source=source, snapshot={})
        req = ServiceRequest.objects.create(client=client, project=pr, whole_estimate=saved,
                                            target_supplier=supplier, request_type='supplier', status='responded')
        offer_line = dict(line_id='1', name='Ламинат', unit='упак.', quantity='12', unit_price='10000',
                          availability='available')
        WholeSupplierOffer.objects.create(request=req, supplier=supplier,
                                          snapshot={'lines': [offer_line], 'total': '120000'})
        work = ServiceRequest.objects.create(client=client, project=pr, target_master=master,
                                             request_type='full_repair', status='responded')
        MasterResponse.objects.create(request=work, master=master, price_from=90000,
                                       message='Укладка ламината в спальне' if language=='ru' else 'Жатын бөлмеге ламинат төсеу')
        results[language] = pr.pk
    (output / 'repair-fixture.json').write_text(json.dumps(results), encoding='ascii')


if __name__ == '__main__':
    main()
