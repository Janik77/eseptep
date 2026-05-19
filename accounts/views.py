from functools import wraps

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import ClientProjectCreateForm, EseptepAuthenticationForm, RegisterForm
from .models import Calculation, ClientProject, ServiceRequest, UserProfile


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


def client_role_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != UserProfile.Role.CLIENT:
            return HttpResponseForbidden('Доступ только для клиентов.')
        return view_func(request, *args, **kwargs)

    return _wrapped


@client_role_required
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


@client_role_required
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


@login_required
def master_dashboard(request):
    return render(request, 'accounts/dashboard_master.html')


@login_required
def supplier_dashboard(request):
    return render(request, 'accounts/dashboard_supplier.html')


def _dashboard_url_by_role(role):
    if role == UserProfile.Role.MASTER:
        return reverse_lazy('accounts:dashboard_master')
    if role == UserProfile.Role.SUPPLIER:
        return reverse_lazy('accounts:dashboard_supplier')
    return reverse_lazy('accounts:dashboard_client')
