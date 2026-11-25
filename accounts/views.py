from core.localization import render
from django.utils.translation import gettext as translate
from .identifiers import parse_positive_id
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden
from django.db import transaction
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy

from .forms import (
    ClientProjectCreateForm,
    EseptepAuthenticationForm,
    MasterProfileForm,
    MasterResponseForm,
    RegisterForm,
    SupplierMaterialForm,
    SupplierProfileForm,
    SupplierResponseForm,
)
from .models import (
    Calculation,
    SavedWholeEstimate,
    WholeSupplierOffer,
    MasterProfile,
    MasterResponse,
    ServiceRequest,
    SupplierMaterial,
    SupplierProfile,
    SupplierResponse,
    UserProfile,
)


OPEN_REQUEST_STATUSES = (ServiceRequest.Status.NEW, ServiceRequest.Status.VIEWED, ServiceRequest.Status.RESPONDED)

class AccountLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = EseptepAuthenticationForm

    def form_valid(self, form):
        from .whole_guest import finish_guest_save
        origin = self.request.session.session_key
        default = super().form_valid(form)
        return finish_guest_save(self.request, origin) or default

    def get_success_url(self):
        safe_next = self.get_redirect_url()
        if safe_next:
            return safe_next
        profile = getattr(self.request.user, 'profile', None)
        if profile is None:
            return reverse_lazy('core:home')
        return _dashboard_url_by_role(profile.role)


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, translate('Вы вышли из аккаунта'))
    return redirect('core:home')


def register_view(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile:
            return redirect(_dashboard_url_by_role(profile.role))
        return redirect('core:home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            from .whole_guest import finish_guest_save
            origin = request.session.session_key
            user = form.save()
            login(request, user)
            return finish_guest_save(request, origin) or redirect(_dashboard_url_by_role(user.profile.role))
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def role_required(role):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            profile = getattr(request.user, 'profile', None)
            if not profile or profile.role != role:
                return HttpResponseForbidden(translate('Недостаточно прав доступа.'))
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


@role_required(UserProfile.Role.CLIENT)
def client_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('response_action')
        response_type = request.POST.get('response_type')
        response_id = parse_positive_id(request.POST.get('response_id'))
        if response_id is None:
            return HttpResponseBadRequest(translate('Некорректный отклик.'))

        response_models = {'master': MasterResponse, 'supplier': SupplierResponse}
        if response_type not in response_models or action not in {'accept', 'reject'}:
            return HttpResponseBadRequest(translate('Некорректное действие.'))
        model = response_models[response_type]
        with transaction.atomic():
            response = get_object_or_404(
                model.objects.select_for_update(), pk=response_id,
                request__client=request.user, request__project__user=request.user, request__target_master__isnull=True,
            )
            service_request = ServiceRequest.objects.select_for_update().get(pk=response.request_id)
            if (response.status != model.Status.PENDING
                    or service_request.status not in OPEN_REQUEST_STATUSES
                    or service_request.request_type not in {response_type, ServiceRequest.RequestType.FULL_REPAIR}):
                return HttpResponseBadRequest(translate('Заявка или отклик уже недоступны для изменения.'))
            response.status = model.Status.ACCEPTED if action == 'accept' else model.Status.REJECTED
            response.save(update_fields=['status'])
            if action == 'accept':
                service_request.status = ServiceRequest.Status.ACCEPTED
                service_request.save(update_fields=['status'])
        return redirect('accounts:dashboard_client')

    profile = request.user.profile
    projects = request.user.client_projects.all()[:10]
    calculations = Calculation.objects.filter(project__user=request.user).select_related('project')[:10]
    requests = (
        ServiceRequest.objects.filter(client=request.user)
        .select_related('project', 'target_supplier')
        .annotate(master_responses_count=Count('master_responses', distinct=True), supplier_responses_count=Count('supplier_responses', distinct=True))[:10]
    )
    master_responses = MasterResponse.objects.filter(request__client=request.user,request__target_master__isnull=True).select_related('master', 'request').order_by('-created_at')[:20]
    supplier_responses = SupplierResponse.objects.filter(request__client=request.user).select_related('supplier', 'request').order_by('-created_at')[:20]
    for supplier_response in supplier_responses:
        msg = supplier_response.message or ''
        supplier_response.delivery_time_label = '—'
        if 'Срок поставки:' in msg:
            supplier_response.delivery_time_label = msg.split('Срок поставки:', 1)[1].strip() or '—'
    context = {
        'profile': profile,
        'projects': projects,
        'calculations': calculations,
        'service_requests': requests,
        'master_responses': master_responses,
        'supplier_responses': supplier_responses,
        'whole_estimates': SavedWholeEstimate.objects.filter(project__user=request.user).select_related('project').order_by('-pk'),
    }
    return render(request, 'accounts/dashboard_client.html', context)


@role_required(UserProfile.Role.CLIENT)
def client_project_create(request):
    if request.method == 'POST':
        form = ClientProjectCreateForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.user = request.user
            project.save()
            return redirect('accounts:dashboard_client')
    else:
        form = ClientProjectCreateForm(initial={'city': request.user.profile.city})
    return render(request, 'accounts/client_project_create.html', {'form': form})


@role_required(UserProfile.Role.MASTER)
def master_dashboard(request):
    master_profile, _ = MasterProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'full_name': request.user.first_name or request.user.username,
            'city': request.user.profile.city or '',
            'specialization': '',
            'experience_years': 0,
            'rating': 0,
        },
    )

    if request.method == 'POST':
        form = MasterResponseForm(request.POST)
        request_id = parse_positive_id(request.POST.get('request_id'))
        if request_id is None:
            return HttpResponseBadRequest(translate('Некорректная заявка.'))
        service_request = get_object_or_404(
            ServiceRequest.objects.filter(project__user=F('client'),target_master__isnull=True).exclude(client=request.user).select_related('project', 'calculation'),
            id=request_id,
            request_type__in=[ServiceRequest.RequestType.MASTER, ServiceRequest.RequestType.FULL_REPAIR],
            status__in=OPEN_REQUEST_STATUSES,
        )
        if form.is_valid():
            response = form.save(commit=False)
            response.request = service_request
            response.master = master_profile
            response.save()
            messages.success(request, translate('Отклик отправлен клиенту.'))
            return redirect('accounts:dashboard_master')
    else:
        form = MasterResponseForm()

    new_requests = ServiceRequest.objects.filter(
        Q(request_type=ServiceRequest.RequestType.MASTER) | Q(request_type=ServiceRequest.RequestType.FULL_REPAIR)
    ).filter(status__in=OPEN_REQUEST_STATUSES,target_master__isnull=True).select_related('project', 'calculation')[:12]

    my_responses = MasterResponse.objects.filter(master=master_profile).select_related('request', 'request__project').order_by('-created_at')[:12]

    return render(
        request,
        'accounts/dashboard_master.html',
        {
            'master_profile': master_profile,
            'turnkey_requests': ServiceRequest.objects.filter(target_master=master_profile, project__user=F('client')).order_by('-pk')[:12],

            'new_requests': new_requests,
            'response_form': form,
            'my_responses': my_responses,
        },
    )


@role_required(UserProfile.Role.MASTER)
def master_profile_edit(request):
    master_profile, _ = MasterProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'full_name': request.user.first_name or request.user.username,
            'city': request.user.profile.city or '',
            'specialization': '',
            'experience_years': 0,
            'rating': 0,
        },
    )

    if request.method == 'POST':
        form = MasterProfileForm(request.POST, request.FILES, instance=master_profile)
        if form.is_valid():
            form.save()
            messages.success(request, translate('Профиль мастера обновлен.'))
            return redirect('accounts:dashboard_master')
    else:
        form = MasterProfileForm(instance=master_profile)
    return render(request, 'accounts/master_profile_edit.html', {'form': form})




@role_required(UserProfile.Role.SUPPLIER)
def supplier_dashboard(request):
    supplier_profile, _ = SupplierProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'company_name': request.user.first_name or request.user.username,
            'city': request.user.profile.city or '',
            'address': '',
            'delivery_info': '',
        },
    )

    if request.method == 'POST':
        form = SupplierResponseForm(request.POST)
        request_id = parse_positive_id(request.POST.get('request_id'))
        if request_id is None:
            return HttpResponseBadRequest(translate('Некорректная заявка.'))
        service_request = get_object_or_404(ServiceRequest.objects.filter(Q(target_supplier__isnull=True) | Q(target_supplier=supplier_profile, target_supplier__is_active=True)).filter(project__user=F('client')).exclude(client=request.user).select_related('project', 'calculation'), id=request_id,
            request_type__in=[ServiceRequest.RequestType.SUPPLIER, ServiceRequest.RequestType.FULL_REPAIR],
            status__in=OPEN_REQUEST_STATUSES)
        if service_request.whole_estimate_id:
            return redirect('accounts:whole_request',pk=service_request.pk)
        if form.is_valid():
            response = form.save(commit=False)
            response.supplier = supplier_profile
            response.request = service_request
            delivery_time = form.cleaned_data.get('delivery_time')
            msg = response.message or ''
            if delivery_time:
                msg = f"{msg}\nСрок поставки: {delivery_time}".strip()
            response.message = msg
            response.save()
            messages.success(request, translate('Ответ поставщика отправлен.'))
            return redirect('accounts:dashboard_supplier')
    else:
        form = SupplierResponseForm()

    materials = SupplierMaterial.objects.filter(supplier=supplier_profile).order_by('-id')
    requests = ServiceRequest.objects.filter(
        Q(request_type=ServiceRequest.RequestType.SUPPLIER) | Q(request_type=ServiceRequest.RequestType.FULL_REPAIR)
    ).filter(Q(target_supplier__isnull=True) | Q(target_supplier=supplier_profile, target_supplier__is_active=True)).filter(project__user=F('client')).exclude(client=request.user).filter(status__in=OPEN_REQUEST_STATUSES).select_related('project', 'calculation', 'target_supplier')[:12]
    my_responses = SupplierResponse.objects.filter(supplier=supplier_profile).select_related('request', 'request__project').order_by('-created_at')[:12]

    return render(request, 'accounts/dashboard_supplier.html', {
        'supplier_profile': supplier_profile,
        'materials': materials,
        'supplier_requests': requests,
        'response_form': form,
        'my_responses': my_responses,
        'whole_offers': WholeSupplierOffer.objects.filter(supplier=supplier_profile).select_related('request').order_by('-pk'),
    })


@role_required(UserProfile.Role.SUPPLIER)
def supplier_material_create(request, material_id=None):
    supplier_profile = get_object_or_404(SupplierProfile, user=request.user)
    material = get_object_or_404(SupplierMaterial, pk=material_id, supplier=supplier_profile) if material_id else None
    if request.method == 'POST':
        form = SupplierMaterialForm(request.POST, instance=material)
        if form.is_valid():
            material = form.save(commit=False)
            material.supplier = supplier_profile
            material.save()
            return redirect('accounts:dashboard_supplier')
    else:
        form = SupplierMaterialForm(instance=material)
    return render(request, 'accounts/supplier_material_create.html', {'form': form})


@role_required(UserProfile.Role.SUPPLIER)
def supplier_profile_edit(request):
    supplier_profile, _ = SupplierProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'company_name': request.user.first_name or request.user.username,
            'city': request.user.profile.city or '',
            'address': '',
            'delivery_info': '',
        },
    )

    if request.method == 'POST':
        form = SupplierProfileForm(request.POST, instance=supplier_profile)
        if form.is_valid():
            form.save()
            messages.success(request, translate('Профиль поставщика обновлен.'))
            return redirect('accounts:dashboard_supplier')
    else:
        form = SupplierProfileForm(instance=supplier_profile)
    return render(request, 'accounts/supplier_profile_edit.html', {'form': form})


def _dashboard_url_by_role(role):
    if role == UserProfile.Role.ADMIN:
        return reverse_lazy('repairs:review_queue')
    if role == UserProfile.Role.MASTER:
        return reverse_lazy('accounts:dashboard_master')
    if role == UserProfile.Role.SUPPLIER:
        return reverse_lazy('accounts:dashboard_supplier')
    return reverse_lazy('accounts:dashboard_client')


@role_required(UserProfile.Role.CLIENT)
def calculation_detail(request, calculation_id):
    from calculators.definitions import CALCULATORS_BY_SLUG
    pk = parse_positive_id(calculation_id)
    if pk is None:
        raise Http404(translate('Расчёт не найден'))
    calculation = get_object_or_404(
        Calculation.objects.select_related('project'), pk=pk, project__user=request.user)
    definition = CALCULATORS_BY_SLUG.get(calculation.calculator_slug, {})
    data = calculation.result_data
    inputs = data.get('input', {})
    parameters = []
    for field in definition.get('fields', []):
        value = inputs.get(field['name'])
        if value is not None:
            value = next((option['label'] for option in field.get('options', []) if option['value'] == value), value)
            parameters.append({'label': field['label'], 'value': value, 'unit': field.get('unit', '')})
    from calculators.offers import material_offers
    return render(request, 'accounts/calculation_detail.html', {
        'meeting_supplier_available': _meeting_supplier() is not None and _meeting_estimate_supported(calculation),
        'targeted_requests': calculation.service_requests.filter(client=request.user, target_supplier__isnull=False).select_related('target_supplier'),
        'material_offers': material_offers(data.get('materials', [])),
        'ai_explanation': calculation.ai_explanations.filter(language='kk' if request.LANGUAGE_CODE == 'kk' else 'ru').first(),
        'calculation': calculation, 'title': definition.get('title', calculation.calculator_slug),
        'parameters': parameters,
        'variant_label': data.get('selected_variant_label') or data.get('selected_variant') or data.get('segment_label'),
    })


def _meeting_supplier():
    from django.conf import settings
    if getattr(settings, 'ESEPTEP_CLOSED_PILOT', False):
        from core.closed_pilot import INVITED_GROUP
        username = getattr(settings, 'ESEPTEP_PILOT_SUPPLIER_USERNAME', '')
        if not username:
            return None
        access = {'user__groups__name': INVITED_GROUP}
    elif getattr(settings, 'ESEPTEP_DEMO_MODE', False) and not getattr(settings, 'PRODUCTION', False):
        username, access = 'demo-supplier@example.test', {}
    else:
        return None
    return SupplierProfile.objects.filter(
        user__username=username, user__is_active=True,
        user__profile__role=UserProfile.Role.SUPPLIER, is_active=True, **access,
    ).first()


def _meeting_estimate_supported(calculation):
    data = calculation.result_data
    return (calculation.calculator_slug == 'plitka-keramogranit'
            and data.get('input', {}).get('zone') == 'floor'
            and bool(data.get('materials')))


def _request_snapshot(calculation, supplier):
    from copy import deepcopy
    return {
        'schema': 1, 'demo': True, 'calculation_id': calculation.pk,
        'project_title': calculation.project.title, 'city': calculation.project.city,
        'area': str(calculation.area_m2), 'calculator_slug': calculation.calculator_slug,
        'supplier_name': supplier.company_name,
        'reference_total': str(calculation.grand_total),
        'result': deepcopy(calculation.result_data),
    }


def _request_digest(snapshot):
    import hashlib
    import json
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


@role_required(UserProfile.Role.CLIENT)
def supplier_request_preview(request, calculation_id):
    """GET is a preview only; explicit POST creates one local targeted request."""
    from django.core import signing
    if request.method not in {'GET', 'POST'}:
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'POST'])
    calculation = get_object_or_404(Calculation.objects.select_related('project'),
        pk=calculation_id, project__user=request.user)
    supplier = _meeting_supplier()
    if supplier is None or not _meeting_estimate_supported(calculation):
        raise Http404
    snapshot = _request_snapshot(calculation, supplier)
    payload = {'user': request.user.pk, 'calculation': calculation.pk,
               'supplier': supplier.pk, 'digest': _request_digest(snapshot)}
    token = signing.dumps(payload, salt='meeting-supplier-request.v1')
    error = ''
    if request.method == 'POST':
        try:
            signed = signing.loads(request.POST.get('request_token', ''), salt='meeting-supplier-request.v1')
            if signed != payload or request.POST.get('confirm') != 'yes':
                raise ValueError
        except (signing.BadSignature, ValueError, TypeError):
            error = translate('Проверьте состав запроса и подтвердите отправку ещё раз.')
        else:
            with transaction.atomic():
                # SQLite writer lock before SELECT; PostgreSQL also serializes this estimate.
                Calculation.objects.filter(pk=calculation.pk).update(grand_total=F('grand_total'))
                # Snapshot and owner are rechecked under lock, not trusted from POST.
                locked = get_object_or_404(Calculation.objects.select_related('project'), pk=calculation.pk,
                                          project__user=request.user)
                if _request_digest(_request_snapshot(locked, supplier)) != payload['digest']:
                    return HttpResponseBadRequest(translate('Смета изменилась. Откройте запрос заново.'))
                service_request, created = ServiceRequest.objects.get_or_create(
                    calculation=locked, target_supplier=supplier, request_type=ServiceRequest.RequestType.SUPPLIER,
                    defaults={'client': request.user, 'project': locked.project,
                              'request_snapshot': snapshot, 'comment': 'Demo meeting request'},
                )
            if created:
                messages.success(request, translate('Тестовая заявка отправлена в кабинет поставщика. Внешних уведомлений нет.'))
            return redirect('accounts:supplier_request_detail', request_id=service_request.pk)
    return render(request, 'accounts/supplier_request_preview.html', {
        'calculation': calculation, 'supplier': supplier, 'snapshot': snapshot,
        'request_token': token, 'request_error': error,
    })


@login_required
def supplier_request_detail(request, request_id):
    """A private immutable request snapshot; unrelated suppliers get 404."""
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else None
    requests = ServiceRequest.objects.filter(target_supplier__isnull=False,
        request_type=ServiceRequest.RequestType.SUPPLIER, project__user=F('client')).select_related('target_supplier', 'calculation', 'project')
    if role == UserProfile.Role.CLIENT:
        requests = requests.filter(client=request.user)
    elif role == UserProfile.Role.SUPPLIER:
        requests = requests.filter(target_supplier__user=request.user, target_supplier__is_active=True)
    else:
        return HttpResponseForbidden(translate('Недостаточно прав доступа.'))
    service_request = get_object_or_404(requests, pk=request_id)
    if service_request.whole_estimate_id:
        return redirect('accounts:whole_request',pk=service_request.pk)
    if request.method == 'POST':
        if role != UserProfile.Role.SUPPLIER or request.POST.get('action') != 'mark_viewed':
            return HttpResponseForbidden(translate('Недостаточно прав доступа.'))
        requests.filter(pk=request_id, status=ServiceRequest.Status.NEW).update(status=ServiceRequest.Status.VIEWED)
        return redirect('accounts:supplier_request_detail', request_id=request_id)
    if request.method != 'GET':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'POST'])
    return render(request, 'accounts/supplier_request_detail.html', {
        'service_request': service_request, 'snapshot': service_request.request_snapshot,
        'is_recipient': role == UserProfile.Role.SUPPLIER,
    })
