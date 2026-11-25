"""Whole-site invitation boundary; enabled only by explicit hosted settings."""
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

INVITED_GROUP = 'ESEPTEP closed pilot'
PAID_GROUP = 'ESEPTEP paid pilot'
BEFORE_LOGIN = frozenset({'accounts:login', 'accounts:logout', 'set_language', 'javascript-catalog'})
NEVER_HOSTED = frozenset({'accounts:register', 'accounts:whole_guest_save', 'projects:choose_sample'})


def pilot_member(user, *, paid=False):
    if not (getattr(user, 'is_authenticated', False) and user.is_active):
        return False
    groups = set(user.groups.filter(name__in=(INVITED_GROUP, PAID_GROUP)).values_list('name', flat=True))
    return INVITED_GROUP in groups and (not paid or PAID_GROUP in groups)


class ClosedPilotAccess(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        view = request.resolver_match.view_name
        if view in NEVER_HOSTED:
            raise Http404
        if view in BEFORE_LOGIN:
            return None
        if not request.user.is_authenticated:
            if request.method not in ('GET', 'HEAD'):
                raise Http404
            response = redirect_to_login(request.get_full_path(), reverse('accounts:login'))
            response['Cache-Control'] = 'private, no-store'
            return response
        if not pilot_member(request.user):
            raise Http404

    def process_response(self, request, response):
        # nginx may serve public *static code*; dynamic hosted pages never cache.
        response['Cache-Control'] = 'private, no-store'
        return response
