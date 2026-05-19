from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from .forms import (
    ClientProjectCreateForm,
    EseptepAuthenticationForm,
    MasterProfileForm,
    MasterResponseForm,
    RegisterForm,
)
from .models import Calculation, MasterProfile, MasterResponse, ServiceRequest, UserProfile


class AccountLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = EseptepAuthenticationForm

    def get_success_url(self):
        profile = getattr(self.request.user, 'profile', None)
        if profile is None:
            return reverse_lazy('core:home')
        return _dashboard_url_by_role(profile.role)


class AccountLogoutView(LogoutView):
    next_page = reverse_lazy('core:home')


def register_view(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile:
            return redirect(_dashboard_url_by_role(profile.role))
        return redirect('core:home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(_dashboard_url_by_role(user.profile.role))
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
                return HttpResponseForbidden('Недостаточно прав доступа.')
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


@role_required(UserProfile.Role.CLIENT)
def client_dashboard(request):
    profile = request.user.profile
    projects = request.user.client_projects.all()[:10]
    calculations = Calculation.objects.filter(project__user=request.user).select_related('project')[:10]
    requests = (
        ServiceRequest.objects.filter(client=request.user)
        .select_related('project')
        .annotate(master_responses_count=Count('master_responses', distinct=True), supplier_responses_count=Count('supplier_responses', distinct=True))[:10]
    )
    context = {
        'profile': profile,
        'projects': projects,
        'calculations': calculations,
        'service_requests': requests,
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
            'city': request.user.profile.city or 'Не указан',
            'specialization': 'Общестроительные работы',
            'experience_years': 1,
            'rating': 5,
        },
    )

    if request.method == 'POST':
        form = MasterResponseForm(request.POST)
        request_id = request.POST.get('request_id')
        service_request = get_object_or_404(
            ServiceRequest.objects.select_related('project', 'calculation'),
            id=request_id,
        )
        if form.is_valid():
            response = form.save(commit=False)
            response.request = service_request
            response.master = master_profile
            response.save()
            messages.success(request, 'Отклик отправлен клиенту.')
            return redirect('accounts:dashboard_master')
    else:
        form = MasterResponseForm()

    new_requests = ServiceRequest.objects.filter(
        Q(request_type=ServiceRequest.RequestType.MASTER) | Q(request_type=ServiceRequest.RequestType.FULL_REPAIR)
    ).select_related('project', 'calculation')[:12]

    my_responses = MasterResponse.objects.filter(master=master_profile).select_related('request', 'request__project').order_by('-created_at')[:12]

    return render(
        request,
        'accounts/dashboard_master.html',
        {
            'master_profile': master_profile,
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
            'city': request.user.profile.city or 'Не указан',
            'specialization': 'Общестроительные работы',
            'experience_years': 1,
            'rating': 5,
        },
    )

    if request.method == 'POST':
        form = MasterProfileForm(request.POST, request.FILES, instance=master_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль мастера обновлен.')
            return redirect('accounts:dashboard_master')
    else:
        form = MasterProfileForm(instance=master_profile)
    return render(request, 'accounts/master_profile_edit.html', {'form': form})


@login_required
def supplier_dashboard(request):
    return render(request, 'accounts/dashboard_supplier.html')


def _dashboard_url_by_role(role):
    if role == UserProfile.Role.MASTER:
        return reverse_lazy('accounts:dashboard_master')
    if role == UserProfile.Role.SUPPLIER:
        return reverse_lazy('accounts:dashboard_supplier')
    return reverse_lazy('accounts:dashboard_client')
