from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .models import ProjectUpload

AI_ANALYSIS_MODE = 'demo'
ALLOWED_UPLOAD_EXTENSIONS = '.pdf,.jpg,.jpeg,.png,.webp,.dwg'
DEMO_AI_SUMMARY = {
    'object_type': 'квартира',
    'status': 'требуется подтверждение площади',
    'sections': ['Демонтаж', 'Электрика', 'Сантехника', 'Полы', 'Стены', 'Потолок', 'Двери'],
    'next_step': 'Укажите площадь и желаемый уровень ремонта, чтобы получить предварительную смету.',
}
REPAIR_LEVEL_RATES = {
    ProjectUpload.RepairLevel.ECONOMY: 120000,
    ProjectUpload.RepairLevel.STANDARD: 170000,
    ProjectUpload.RepairLevel.PREMIUM: 250000,
}


def projects_home(request):
    return redirect('projects:upload')


def project_upload(request):
    upload = None
    estimate = None

    if request.method == 'POST' and request.POST.get('action') == 'estimate':
        upload = get_object_or_404(ProjectUpload, pk=request.POST.get('upload_id'))
        area_raw = request.POST.get('area', '')
        repair_level = request.POST.get('repair_level') or ProjectUpload.RepairLevel.STANDARD
        try:
            area = Decimal(str(area_raw).replace(',', '.'))
        except (InvalidOperation, TypeError):
            area = None

        if area and area > 0:
            upload.area = area
            upload.repair_level = repair_level
            upload.save(update_fields=['area', 'repair_level'])
            estimate = {
                'area': area,
                'repair_level': upload.get_repair_level_display(),
                'total': round(float(area) * REPAIR_LEVEL_RATES[repair_level]),
            }
            messages.success(request, 'Предварительный расчёт готов.')
        else:
            messages.error(request, 'Укажите корректную площадь квартиры.')

    elif request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        if uploaded_file:
            upload = ProjectUpload.objects.create(
                user=request.user if request.user.is_authenticated else None,
                file=uploaded_file,
                comment=request.POST.get('comment', ''),
                ai_status=AI_ANALYSIS_MODE,
                ai_summary=DEMO_AI_SUMMARY,
            )
            messages.success(request, 'Файл принят для demo-анализа.')
        else:
            messages.error(request, 'Выберите файл проекта.')

    return render(
        request,
        'projects/upload.html',
        {
            'upload': upload,
            'estimate': estimate,
            'ai_summary': upload.ai_summary if upload else None,
            'ai_analysis_mode': AI_ANALYSIS_MODE,
            'allowed_upload_extensions': ALLOWED_UPLOAD_EXTENSIONS,
            'repair_levels': ProjectUpload.RepairLevel.choices,
            'show_auth_save_cta': not request.user.is_authenticated,
        },
    )
