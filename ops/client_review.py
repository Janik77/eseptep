"""Run through manage.py shell on the dedicated client demo. No provider calls."""
from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse
from accounts.models import (ClientProject, UserProfile, MasterProfile, MasterResponse,
    SupplierProfile, ServiceRequest, SavedWholeEstimate, WholeSupplierOffer)
from projects.models import ProjectUpload, WholePlanEstimate
from repairs.models import Repair
from repairs.services import offer_rows


@transaction.atomic
def prepare():
    import secrets
    from django.contrib.auth.models import Group
    from django.urls import reverse
    from core.closed_pilot import INVITED_GROUP, PAID_GROUP
    from repairs.models import PilotCity, city_key
    email = 'review@eseptep.test'
    if User.objects.filter(username=email).exists():
        raise SystemExit('Кабинет уже создан. Пароль и данные сохранены.')
    password = secrets.token_urlsafe(18)
    client = User.objects.create_user(username=email, email=email, password=password)
    UserProfile.objects.create(user=client, role='client')
    for group in (INVITED_GROUP, PAID_GROUP):
        client.groups.add(Group.objects.get_or_create(name=group)[0])
    city = PilotCity.objects.get(key=city_key('Шымкент'), enabled=True)
    project = ClientProject.objects.create(user=client,title='Учебный заказ · квартира 40 м²',city=city.name,area_m2=40,rooms=2)
    repair = Repair.objects.create(project=project,city=city,enabled=True)
    for kind in ('materials', 'works'):
        if repair.agreements.filter(kind=kind).exists() or any(
                row['kind'] == kind for row in offer_rows(repair)):
            continue
        username = 'contract-demo-' + kind + '@example.invalid'
        actor, created = User.objects.get_or_create(username=username)
        if created:
            actor.set_unusable_password()
            actor.save(update_fields=['password'])
        if actor.has_usable_password() or actor.is_staff or actor.is_superuser:
            raise ValueError('Demo account collision')
        role = 'supplier' if kind == 'materials' else 'master'
        profile, _ = UserProfile.objects.get_or_create(user=actor, defaults={'role':role})
        if profile.role != role:
            raise ValueError('Demo role mismatch')
        if kind == 'materials':
            store, _ = SupplierProfile.objects.get_or_create(user=actor, defaults={
                'company_name':'Демо-магазин · учебное предложение', 'city':project.city})
            upload = ProjectUpload.objects.create(user=client, comment='Учебная смета для договора')
            source = WholePlanEstimate.objects.create(upload=upload, fingerprint='contract-demo', snapshot={'known_area':'40.00','procurement':[]})
            saved = SavedWholeEstimate.objects.create(project=project, source=source, snapshot={'known_area':'40.00','procurement':[]})
            req = ServiceRequest.objects.create(client=client, project=project, target_supplier=store,
                whole_estimate=saved, request_type='supplier', status='responded')
            WholeSupplierOffer.objects.create(request=req, supplier=store, snapshot={
                'total':'12000.00','lines':[{'line_id':'1','quantity':'12','purchase_quantity':'12',
                'purchase_unit':'упак.','name':'Учебный ламинат','unit_price':'1000.00','availability':'available'}]})
        else:
            master, _ = MasterProfile.objects.get_or_create(user=actor, defaults={
                'full_name':'Демо-мастер · учебное предложение','city':project.city,'specialization':'Укладка пола'})
            req = ServiceRequest.objects.create(client=client, project=project, target_master=master,
                request_type='full_repair', status='responded')
            MasterResponse.objects.create(request=req, master=master, price_from='80000.00',
                message='Учебное предложение: укладка пола в квартире.')
    available = {r['kind'] for r in offer_rows(repair)} | set(repair.agreements.values_list('kind',flat=True))
    if available != {'materials','works'}:
        raise ValueError('Could not prepare both choices')
    from django.conf import settings
    from core.local_ai_budget import status
    budget = status(settings.LOCAL_AI_BUDGET_PATH)
    print('ИИ: следующий запрос доступен =', budget['next_call_available'], 'остаток в центах =', budget['remaining_cents'])
    print('Логин:', email)
    print('Пароль:', password)
    print('OPEN: https://82.115.43.144' + reverse('repairs:detail', args=[project.pk]))


prepare()
