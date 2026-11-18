from core.localization import render
from core.renovation_rates import rate_configuration, renovation_estimate, LEGACY_VERSION, LEGACY_RATES
from django.db import transaction
from calculators.pricing import lock_price_configuration
from django.utils.translation import gettext as _
from django.contrib import messages
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET
from .forms import ProjectUploadForm, ProjectEstimateForm
from django.shortcuts import get_object_or_404, redirect

from .models import ProjectUpload

AI_ANALYSIS_MODE = 'demo'
ALLOWED_UPLOAD_EXTENSIONS = '.pdf,.jpg,.jpeg,.png,.webp'
DEMO_AI_SUMMARY = {
    'object_type': 'квартира',
    'status': 'требуется подтверждение площади',
    'sections': ['Демонтаж', 'Электрика', 'Сантехника', 'Полы', 'Стены', 'Потолок', 'Двери'],
    'next_step': 'Укажите площадь и желаемый уровень ремонта, чтобы получить предварительную смету.',
}
REPAIR_LEVEL_RATES = {key: int(value) for key, value in LEGACY_RATES.items()}


def projects_home(request):
    return redirect('projects:upload')


def accessible_uploads(request):
    # Legacy unowned uploads have no session key and are deliberately inaccessible.
    if request.user.is_authenticated:
        return ProjectUpload.objects.filter(user=request.user)
    key = request.session.session_key
    if not key:
        return ProjectUpload.objects.none()
    return ProjectUpload.objects.filter(user__isnull=True, guest_session_key=key)


@require_GET
def project_download(request, pk):
    upload = get_object_or_404(accessible_uploads(request), pk=pk)
    try:
        stream = upload.file.open('rb')
    except (FileNotFoundError, OSError):
        raise Http404('File unavailable')
    response = FileResponse(stream, as_attachment=True, filename=upload.file.name.rsplit('/', 1)[-1], content_type='application/octet-stream')
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    return response


def project_upload(request):
    upload = None
    estimate = None
    rate_config = rate_configuration()
    upload_form = ProjectUploadForm()
    estimate_form = ProjectEstimateForm(initial={'repair_level': ProjectUpload.RepairLevel.STANDARD})
    if request.method == 'GET' and request.GET.get('upload_id'):
        try:
            pk = int(request.GET['upload_id'])
        except (ValueError, TypeError):
            raise Http404('Upload unavailable')
        upload = get_object_or_404(accessible_uploads(request), pk=pk)
        estimate_form = ProjectEstimateForm(initial={'area': upload.area, 'repair_level': upload.repair_level})
        if upload.area and upload.repair_level in LEGACY_RATES:
            estimate = dict(upload.estimate_snapshot) if upload.estimate_snapshot else renovation_estimate(upload.area, upload.repair_level, rate_configuration(historical=True))
            estimate['repair_level'] = dict(ProjectUpload.RepairLevel.choices)[estimate['repair_level_key']]
    if request.method == 'POST' and request.POST.get('action') == 'estimate':
        try:
            pk = int(request.POST.get('upload_id', ''))
        except (ValueError, TypeError):
            raise Http404('Upload unavailable')
        upload = get_object_or_404(accessible_uploads(request), pk=pk)
        data = request.POST.copy()
        data['area'] = data.get('area', '').replace(',', '.')
        estimate_form = ProjectEstimateForm(data)
        if estimate_form.is_valid():
            with transaction.atomic():
                lock_price_configuration()
                rate_config = rate_configuration()
                expected = request.POST.get('rate_version', LEGACY_VERSION)
                if expected != rate_config['version']:
                    estimate_form.add_error(None, _('Версия ставок изменилась. Проверьте условия и рассчитайте снова.'))
                    if upload.estimate_snapshot:
                        estimate = dict(upload.estimate_snapshot)
                        estimate['repair_level'] = dict(ProjectUpload.RepairLevel.choices)[estimate['repair_level_key']]
                else:
                    upload.area = estimate_form.cleaned_data['area']
                    upload.repair_level = estimate_form.cleaned_data['repair_level']
                    upload.estimate_snapshot = renovation_estimate(upload.area, upload.repair_level, rate_config)
                    upload.save(update_fields=['area', 'repair_level', 'estimate_snapshot'])
                    estimate = {**upload.estimate_snapshot, 'repair_level': upload.get_repair_level_display()}
                    messages.success(request, _('Предварительный расчёт готов.'))
    elif request.method == 'POST':
        upload_form = ProjectUploadForm(request.POST, request.FILES)
        if upload_form.is_valid():
            if not request.user.is_authenticated and not request.session.session_key:
                request.session.create()
            upload = ProjectUpload.objects.create(
                user=request.user if request.user.is_authenticated else None,
                guest_session_key='' if request.user.is_authenticated else request.session.session_key,
                file=upload_form.cleaned_data['file'], comment=upload_form.cleaned_data['comment'],
                ai_status=AI_ANALYSIS_MODE, ai_summary=DEMO_AI_SUMMARY)
            messages.success(request, _('Файл сохранён. Теперь откройте план и подтвердите площадь.'))
    return render(request, 'projects/upload.html', {
        'rate_config': rate_config,
        'upload': upload, 'estimate': estimate, 'upload_form': upload_form, 'estimate_form': estimate_form,
        'ai_summary': upload.ai_summary if upload else None, 'ai_analysis_mode': AI_ANALYSIS_MODE,
        'allowed_upload_extensions': ALLOWED_UPLOAD_EXTENSIONS,
        'repair_levels': ProjectUpload.RepairLevel.choices,
        'show_auth_save_cta': not request.user.is_authenticated,
    })
