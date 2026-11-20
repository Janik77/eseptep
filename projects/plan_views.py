from urllib.parse import urlencode
from django.core import signing
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods
from .models import PlanAnalysis, PlanConfirmation
from .plan_analysis import PlanError, analyze, area, pages, analysis_identity, read_raw, scoped_analysis
from .plan_messages import plan_message
from .views import accessible_uploads


def current_analysis(upload):
    try:
        raw = read_raw(upload)
    except PlanError:
        return None
    if upload.comment.startswith('MEETING_SAMPLE:'):
        fixture = PlanAnalysis.objects.filter(
            identity=analysis_identity(f'demo-sample:{upload.pk}', raw),
            upload=upload, model='offline-fixture').first()
        if fixture:
            return fixture
    try:
        return scoped_analysis(upload, raw)
    except PlanError:
        return None


@require_GET
def plan_image(request, pk, page):
    upload = get_object_or_404(accessible_uploads(request), pk=pk)
    try:
        _, frames = pages(upload)
        if not 1 <= page <= len(frames):
            raise Http404
        response = HttpResponse(frames[page-1][0], content_type='image/jpeg')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except PlanError:
        raise Http404


@require_http_methods(['GET', 'POST'])
def plan_review(request, pk):
    upload = get_object_or_404(accessible_uploads(request), pk=pk)
    analysis = current_analysis(upload)
    error = ''
    if request.method == 'POST' and request.POST.get('action') == 'analyze':
        try:
            analyze(upload)
            return redirect('projects:plan_review', pk=pk)
        except PlanError as exc:
            error = str(exc)
    rooms = analysis.rooms if analysis and analysis.status == 'completed' else []
    if request.method == 'POST' and request.POST.get('action') == 'confirm':
        number = area(request.POST.get('area'))
        name = request.POST.get('name', '').strip()[:100]
        if not number or Decimal(number) < 1 or not name:
            error = 'invalid_area'
        else:
            try:
                index = int(request.POST.get('room', '-1'))
            except ValueError:
                index = -1
            original = rooms[index] if 0 <= index < len(rooms) else {}
            snapshot = {'name': name, 'area': number, 'surface': 'floor', 'upload_id': upload.pk,
                        'analysis_id': analysis.pk if analysis else None, 'original': original,
                        'method': original.get('source', 'manual'),
                        'manually_corrected': original.get('area') != number,
                        'confirmed': True}
            confirmation = PlanConfirmation.objects.create(upload=upload, snapshot=snapshot)
            token = signing.dumps(confirmation.pk, salt='plan-confirmation.v1')
            return redirect(reverse('calculators:detail', args=['plitka-keramogranit']) + '?' + urlencode({
                '_preview': '0', 'area': number, 'zone': 'floor', 'tile_format': '60x60', 'plan_token': token}))
    messages = {
        'unreadable_file': _('Не удалось прочитать файл. Укажите площадь вручную или загрузите другой план.'),
        'not_configured': _('ИИ пока не подключён. Можно указать площадь вручную.'),
        'file_limit': plan_message('file_limit'), 'page_limit': plan_message('page_limit'),
        'invalid_area': _('Укажите название и площадь от 1 до 10 000 м².'),
        'pilot_only': _('Анализ доступен только на тестовом стенде.'),
    }
    previous = PlanConfirmation.objects.filter(upload=upload).order_by('-pk').first()
    previous_data = previous.snapshot if previous else {}
    return render(request, 'projects/plan_review.html', {'upload': upload, 'analysis': analysis,
        'analysis_notice': plan_message(analysis.error_code) if analysis and analysis.error_code else '', 'rooms': rooms, 'has_bathroom': any(r.get('kind')=='bathroom' for r in rooms), 'error': messages.get(error, plan_message(error) if error else ''), 'previous_confirmation': previous_data,
        'entered_name': request.POST.get('name', previous_data.get('name', _('Ванная'))),
        'entered_area': request.POST.get('area', previous_data.get('area', ''))})


from decimal import Decimal

def confirmed_source(request, token, slug, data):
    if not token:
        return None
    try:
        pk = signing.loads(token, salt='plan-confirmation.v1')
        record = PlanConfirmation.objects.get(pk=pk, upload__in=accessible_uploads(request))
    except (signing.BadSignature, PlanConfirmation.DoesNotExist, ValueError, TypeError):
        raise Http404
    if slug != 'plitka-keramogranit' or data.get('zone') != 'floor' or area(data.get('area')) != record.snapshot['area']:
        from django.core.exceptions import ValidationError
        raise ValidationError(_('Площадь отличается от подтверждённого плана. Вернитесь к плану и подтвердите изменение.'))
    return {**record.snapshot, 'confirmation_id': record.pk, 'confirmed_at': record.created_at.isoformat()}
