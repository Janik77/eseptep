"""Closed-pilot turnkey replies. No external message, deposit or agreement."""
import hashlib

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import F
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from calculators.pricing import lock_price_configuration
from core.renovation_rates import rate_configuration, renovation_estimate
from .forms import MasterResponseForm
from .models import ClientProject, MasterProfile, MasterResponse, ServiceRequest, UserProfile
from .views import role_required
from .whole_views import digest, tr

SCHEMA = 'turnkey-demo-v1'
SALT = 'turnkey-quote.v1'
RESPONSE_SALT = 'turnkey-reply.v1'
DEMO_MASTER = 'demo-master@example.test'


def meeting_master():
    if not settings.ESEPTEP_DEMO_MODE or settings.PRODUCTION:
        return None
    return MasterProfile.objects.filter(
        user__username=DEMO_MASTER, user__is_active=True, is_available=True,
        user__profile__role=UserProfile.Role.MASTER,
    ).first()


def signed_quote(estimate, city, provider):
    snapshot = {
        'schema': SCHEMA, 'area': estimate['area'], 'city': city,
        'package': estimate['repair_level_key'], 'rate': estimate['rate_per_m2'],
        'budget': estimate['total'], 'rate_version': estimate['configuration']['version'],
        'recipient': provider.full_name, 'recipient_id': provider.pk,
    }
    return signing.dumps(snapshot, salt=SALT)


def valid_snapshot(token, master):
    data = signing.loads(token, salt=SALT, max_age=3600)
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or data.get('recipient_id') != master.pk or data.get('recipient') != master.full_name:
        raise ValueError
    return data


@role_required(UserProfile.Role.CLIENT)
@require_http_methods(['GET', 'POST'])
def preview(request):
    master = meeting_master()
    if master is None:
        raise Http404
    token = request.GET.get('quote', '') if request.method == 'GET' else request.POST.get('quote', '')
    try:
        snapshot = valid_snapshot(token, master)
    except (signing.BadSignature, ValueError):
        return HttpResponseBadRequest(tr('Расчёт устарел. Откройте предварительную оценку заново.', 'Есеп ескірді. Бастапқы бағалауды қайта ашыңыз.'))
    from repairs.models import Repair, city_key
    from repairs.services import scoped_repair
    pilot_projects = [row.project for row in Repair.objects.filter(project__user=request.user,
                      enabled=True, city__enabled=True, city__key=city_key(snapshot['city'])).select_related('project','city')
                      if city_key(row.project.city) == row.city.key]
    selected = request.POST.get('repair_project', '') if request.method == 'POST' else ''
    if selected and not any(str(project.pk) == selected for project in pilot_projects):
        raise Http404
    identity = f'{request.user.pk}:{digest(snapshot)}' + (f':repair:{selected}' if selected else '')
    key = hashlib.sha256(identity.encode()).hexdigest()
    if request.method == 'POST':
        if request.POST.get('confirm') != 'yes':
            return HttpResponseBadRequest(tr('Подтвердите состав и получателя.', 'Құрамы мен алушыны растаңыз.'))
        with transaction.atomic():
            project = None
            if selected:
                repair, role = scoped_repair(request.user, int(selected), lock=True)
                if role != 'client' or city_key(repair.project.city) != city_key(snapshot['city']):
                    raise Http404
                project = repair.project
            lock_price_configuration()
            master = meeting_master()
            if not master or master.pk != snapshot['recipient_id'] or master.full_name != snapshot['recipient']:
                raise Http404
            existing = ServiceRequest.objects.filter(pilot_key=key, client=request.user, project__user=request.user, target_master=master).first()
            if existing:
                return redirect('accounts:turnkey_request', pk=existing.pk)
            config = rate_configuration()
            current = renovation_estimate(snapshot['area'], snapshot['package'], config)
            if (config['version'], current['total'], current['rate_per_m2']) != (snapshot['rate_version'], snapshot['budget'], snapshot['rate']):
                return HttpResponseBadRequest(tr('Тарифы изменились. Пересчитайте бюджет перед подтверждением.', 'Тарифтер өзгерді. Растау алдында бюджетті қайта есептеңіз.'))
            if project is None:
                project = ClientProject.objects.create(
                    user=request.user, title=tr('Ремонт под ключ', 'Толық жөндеу'),
                    city=snapshot['city'], area_m2=snapshot['area'], rooms=0,
                )
            req = ServiceRequest.objects.create(client=request.user, project=project,
                request_type=ServiceRequest.RequestType.FULL_REPAIR, target_master=master,
                pilot_key=key, request_snapshot=snapshot)
        return redirect('accounts:turnkey_request', pk=req.pk)
    return render(request, 'accounts/turnkey_preview.html', {'snapshot':snapshot, 'token':token, 'pilot_projects':pilot_projects})


@require_http_methods(['GET', 'POST'])
@role_required(UserProfile.Role.MASTER)
def reply(request, pk):
    return _request(request, pk, True)


@require_http_methods(['GET', 'POST'])
@role_required(UserProfile.Role.CLIENT)
def receipt(request, pk):
    return _request(request, pk, False)


def _request(request, pk, recipient):
    if not settings.ESEPTEP_DEMO_MODE or settings.PRODUCTION:
        raise Http404
    qs = ServiceRequest.objects.filter(request_type=ServiceRequest.RequestType.FULL_REPAIR,
        target_master__isnull=False, project__user=F('client'), request_snapshot__schema=SCHEMA).select_related('target_master')
    if recipient:
        master = meeting_master()
        if not master or master.user_id != request.user.pk:
            raise Http404
        qs = qs.filter(target_master=master)
    else:
        qs = qs.filter(client=request.user)
    req = get_object_or_404(qs, pk=pk)
    payload = {'request': req.pk, 'target': req.target_master_id, 'digest': digest(req.request_snapshot)}
    form, error = MasterResponseForm(), ''
    if request.method == 'POST':
        if not recipient:
            return HttpResponseForbidden()
        data = request.POST.copy()
        data['price_from'] = data.get('price_from', '').strip().replace(',', '.')
        form = MasterResponseForm(data)
        try:
            if signing.loads(request.POST.get('token',''),salt=RESPONSE_SALT,max_age=3600) != payload:
                raise ValueError
            if not form.is_valid() or form.cleaned_data['price_from'] <= 0 or len(form.cleaned_data['message']) > 2000:
                raise ValueError
        except (signing.BadSignature, ValueError):
            error = tr('Укажите положительную цену и комментарий до 2 000 знаков.', 'Оң бағаны және 2 000 таңбаға дейінгі түсініктемені көрсетіңіз.')
        else:
            with transaction.atomic():
                qs.filter(pk=req.pk).update(status=F('status'))
                locked = get_object_or_404(qs, pk=req.pk)
                current = meeting_master()
                if current is None or current.pk != locked.target_master_id or digest(locked.request_snapshot) != payload['digest']:
                    raise Http404
                open_statuses = (ServiceRequest.Status.NEW, ServiceRequest.Status.VIEWED, ServiceRequest.Status.RESPONDED)
                if locked.status not in open_statuses:
                    return HttpResponseBadRequest(tr('Заявка закрыта.', 'Өтінім жабық.'))
                _, created = MasterResponse.objects.get_or_create(request=locked, master=current,
                    defaults={'price_from':form.cleaned_data['price_from'], 'message':form.cleaned_data['message']})
                if created:
                    qs.filter(pk=req.pk).update(status=ServiceRequest.Status.RESPONDED)
            return redirect('accounts:turnkey_reply', pk=req.pk)
    response = MasterResponse.objects.filter(request=req, master=req.target_master).first()
    return render(request,'accounts/turnkey_request.html',{
        'service_request':req, 'snapshot':req.request_snapshot, 'recipient':recipient,
        'reply':response, 'form':form, 'error':error, 'token':signing.dumps(payload,salt=RESPONSE_SALT),
    },status=400 if error else 200)
