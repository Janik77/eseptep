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
    client = User.objects.get(username='client@eseptep.test')
    project = ClientProject.objects.select_for_update().get(
        user=client, title='Тест ИИ · квартира 40 м²')
    repair = Repair.objects.get(project=project, enabled=True, city__enabled=True)
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
            source = WholePlanEstimate.objects.create(upload=upload, fingerprint='contract-demo', snapshot={})
            saved = SavedWholeEstimate.objects.create(project=project, source=source, snapshot={})
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
    print('OPEN: https://82.115.43.144' + reverse('repairs:detail', args=[project.pk]))


prepare()
