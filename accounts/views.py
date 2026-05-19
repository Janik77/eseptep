from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import EseptepAuthenticationForm, RegisterForm
from .models import UserProfile


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


@login_required
def client_dashboard(request):
    return render(request, 'accounts/dashboard_client.html')


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
