"""Staff-only CSV confirmation, reusing the same bounded parser as the command."""
import base64
from datetime import date

from django import forms
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .price_import import MAX_BYTES, import_floor_prices

SALT = 'admin.floor-price.import.v1'


class PriceCSVForm(forms.Form):
    store = forms.CharField(label=_('Магазин'), max_length=160)
    version = forms.CharField(label=_('Версия'), max_length=60)
    source = forms.CharField(label=_('Источник и область применения'), max_length=255)
    date = forms.DateField(label=_('Дата цен'), input_formats=['%Y-%m-%d'], widget=forms.DateInput(attrs={'type':'date'}))
    file = forms.FileField(label='CSV', widget=forms.FileInput(attrs={'accept':'.csv,text/csv'}))


def can_import(admin_model, request):
    return admin_model.has_add_permission(request) and request.user.has_perm('calculators.add_materialprice')


@require_http_methods(['GET', 'POST'])
def import_view(request, admin_model):
    if not can_import(admin_model, request):
        raise PermissionDenied
    token, error, count = '', '', 0
    form = PriceCSVForm(initial={'date':date.today()})
    if request.method == 'POST':
        try:
            if request.POST.get('confirm') == 'yes':
                submitted = request.POST.get('token', '')
                if not submitted or len(submitted) > 45_000:
                    raise ValueError('Проверьте файл заново.')
                payload = signing.loads(submitted, salt=SALT, max_age=900)
                if payload['user'] != request.user.pk:
                    raise PermissionDenied
                raw = base64.b64decode(payload['file'], validate=True)
                book, imported_count = import_floor_prices(raw, **payload['metadata'], write=True)
                admin_model.message_user(request, _('Черновик импортирован. Прайс ещё не опубликован.'))
                return redirect(reverse('admin:calculators_pricebook_change', args=[book.pk]))
            form = PriceCSVForm(request.POST, request.FILES)
            if form.is_valid():
                d = form.cleaned_data
                raw = d['file'].read(MAX_BYTES + 1)
                meta = {key:d[key] for key in ('store','version','source')}
                meta['date_text'] = d['date'].isoformat()
                draft, count = import_floor_prices(raw, **meta)
                token = signing.dumps({'user':request.user.pk,'file':base64.b64encode(raw).decode('ascii'),
                    'metadata':meta}, salt=SALT)
        except (ValueError, ValidationError, signing.BadSignature) as exc:
            error = str(exc) if not isinstance(exc, signing.BadSignature) else _('Срок проверки истёк. Загрузите CSV снова.')
    return render(request, 'admin/calculators/pricebook/import_csv.html', {
        **admin_model.admin_site.each_context(request), 'opts':admin_model.model._meta,
        'title':_('Импорт прайса пола'), 'form':form, 'count':count, 'token':token, 'error':error,
    }, status=400 if error else 200)
