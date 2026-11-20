from decimal import Decimal
from copy import deepcopy
from django.conf import settings
from django.contrib import messages
from django.utils.translation import get_language
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from .views import accessible_uploads
from .models import WholePlanEstimate
from .plan_views import current_analysis
from .plan_analysis import analyze, PlanError, area, PARSER_VERSION
from .whole_plan import initial_rooms, persist_estimate, FINISHES, EstimateChanged


@require_http_methods(['GET', 'POST'])
def whole_plan(request, pk):
    upload = get_object_or_404(accessible_uploads(request), pk=pk)
    analysis = current_analysis(upload)
    estimates = WholePlanEstimate.objects.filter(upload=upload, snapshot__version=PARSER_VERSION)
    current_id = (upload.ai_summary or {}).get('whole_estimate_id')
    estimate = estimates.filter(pk=current_id).first() if isinstance(current_id, int) else estimates.order_by('-pk').first()
    error = ''
    manual_input = {}
    kk = (get_language() or '').startswith('kk')
    manual_error = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'analyze':
            if estimate:
                # Reopening/retrying analysis must not replace reviewed room edits.
                return redirect('projects:whole_plan', pk=pk)
            try:
                analysis = analysis or analyze(upload)
                if analysis.status == 'completed' and analysis.rooms:
                    try:
                        persist_estimate(upload, initial_rooms(analysis), analysis.pk, initialize=True)
                    except EstimateChanged:
                        pass
                else:
                    error = analysis.error_code or ('no_rooms' if analysis.status == 'completed' else analysis.status)
            except PlanError as exc:
                error = str(exc)
            if not error:
                return redirect('projects:whole_plan', pk=pk)
        elif action == 'add_room':
            name = request.POST.get('name', '').strip()
            number = area(request.POST.get('area'))
            finish = request.POST.get('finish')
            manual_input = {'name': name, 'area': request.POST.get('area', ''), 'finish': finish}
            expected = request.POST.get('estimate_id', '')
            rows = [dict(r) for r in estimate.snapshot['rooms']] if estimate else initial_rooms(analysis) if analysis and analysis.status == 'completed' else []
            if expected != (str(estimate.pk) if estimate else ''):
                manual_error = 'Расчёт изменился. Откройте актуальную версию.' if not kk else 'Есеп өзгерді. Ағымдағы нұсқаны ашыңыз.'
            elif not name or len(name) > 100 or any(ord(c)<32 for c in name) or number is None or Decimal(number)<1 or finish not in FINISHES or len(rows)>=20:
                manual_error = ('Укажите название, покрытие и площадь от 1 м². До 20 помещений.' if not kk
                    else 'Атауын, жабынды және 1 м²-ден басталатын ауданды көрсетіңіз. 20 бөлмеге дейін.')
            else:
                rows.append(dict(index=max((r['index'] for r in rows), default=-1)+1, name=name, area=number,
                    source='manual', finish=finish, finish_source='user', finish_proposed=False))
                try:
                    persist_estimate(upload, rows, estimate.snapshot['analysis_id'] if estimate else analysis.pk if analysis else None,
                        expected_id=estimate.pk if estimate else None, initialize=not estimate)
                except EstimateChanged:
                    manual_error = 'Расчёт изменился. Откройте актуальную версию.' if not kk else 'Есеп өзгерді. Ағымдағы нұсқаны ашыңыз.'
                else:
                    return redirect('projects:whole_plan', pk=pk)
        elif action in ('update', 'save', 'supplier_simulate'):
            if not estimate or str(estimate.pk) != request.POST.get('estimate_id'):
                return HttpResponseBadRequest('Есеп өзгерді. Бетті жаңартыңыз.' if (get_language() or '').startswith('kk') else 'Расчёт уже изменился. Обновите страницу перед следующей правкой.')
            if action == 'update':
                rows = [dict(r) for r in estimate.snapshot['rooms']]
                try:
                    index = int(request.POST.get('room', '-1'))
                    row = next(r for r in rows if r['index'] == index)
                    finish = request.POST.get('finish', row['finish'])
                    if finish not in FINISHES:
                        raise ValueError
                    if 'finish' in request.POST and (finish != row['finish'] or request.POST.get('edit_finish') == 'yes'):
                        row['finish'], row['finish_proposed'], row['finish_source'] = finish, False, 'user'
                    if 'name' in request.POST:
                        name = request.POST['name'].strip()
                        if not name or len(name) > 100 or any(ord(c) < 32 for c in name):
                            raise ValueError
                        row['name'] = name
                    if request.POST.get('area'):
                        number = area(request.POST['area'])
                        if number is None or Decimal(number) < 1:
                            raise ValueError
                        if number != area(row.get('area')):
                            row['area'], row['source'] = number, 'manual'
                            row['visual_evidence'] = ''
                    persist_estimate(upload, rows, estimate.snapshot['analysis_id'], expected_id=estimate.pk)
                except EstimateChanged:
                    return HttpResponseBadRequest('Есеп өзгерді. Бетті жаңартып, қайталаңыз.' if (get_language() or '').startswith('kk') else 'Расчёт изменился. Обновите страницу и повторите изменение.')
                except (ValueError, StopIteration):
                    return HttpResponseBadRequest('Бөлмені, жабынды және ауданды тексеріңіз (кемінде 1 м²).' if (get_language() or '').startswith('kk') else 'Проверьте комнату, покрытие и площадь (не менее 1 м²).')
            elif action == 'supplier_simulate':
                if not settings.ESEPTEP_DEMO_MODE:
                    return HttpResponseBadRequest('Supplier simulation is available only in demo mode.')
                WholePlanEstimate.objects.filter(pk=estimate.pk, supplier_simulated_at__isnull=True).update(supplier_simulated_at=timezone.now())
            if action == 'save':
                messages.success(request, 'Смета сохранена. Эта версия доступна в PDF.' if not (get_language() or '').startswith('kk') else 'Смета сақталды. Бұл нұсқа PDF форматында қолжетімді.')
            return redirect('projects:whole_plan', pk=pk)
        else:
            return HttpResponseBadRequest('Unknown action.')
    if not estimate and analysis and analysis.status == 'completed' and analysis.rooms and not manual_error:
        try:
            estimate = persist_estimate(upload, initial_rooms(analysis), analysis.pk, initialize=True)
        except EstimateChanged:
            upload.refresh_from_db(fields=['ai_summary'])
            estimate = estimates.filter(pk=upload.ai_summary.get('whole_estimate_id')).first()
    from .plan_messages import plan_message
    if not error and analysis and analysis.status in ('failed', 'unknown', 'running'):
        error = analysis.error_code or ('running' if analysis.status == 'running' else 'api_failed')
    if not error and not estimate and analysis and analysis.status == 'completed' and not analysis.rooms:
        error = 'no_rooms'
    if error:error = plan_message(error)
    display_snapshot = deepcopy(estimate.snapshot) if estimate else None
    kk = (get_language() or '').startswith('kk')
    room_labels = {'гостиная': 'Қонақ бөлме', 'кухня': 'Асүй', 'ванная': 'Жуынатын бөлме',
                   'санузел': 'Санторап', 'коридор': 'Дәліз', 'прихожая': 'Кіреберіс',
                   'спальня': 'Жатын бөлме', 'детская': 'Балалар бөлмесі', 'комната': 'Бөлме'}
    if display_snapshot:
        for room in display_snapshot['rooms']:
            name = room.get('name', '')
            translated = name
            if kk:
                for ru, kz in room_labels.items():
                    if name.casefold() == ru or name.casefold().startswith(ru + ' '):
                        translated = kz + name[len(ru):]
                        break
            room['display_name'] = translated
    return render(request, 'projects/whole_plan.html', {
        'upload': upload, 'analysis': analysis, 'estimate': estimate,
        'snapshot': display_snapshot, 'error': error, 'manual_input': manual_input, 'manual_error': manual_error,
        'analysis_available': bool(settings.PLAN_AI_ENABLED and getattr(settings, 'OPENAI_API_KEY', '')),

        'unresolved_positions': sum(r.get('line_total') is None for r in estimate.snapshot['procurement']) if estimate else 0,
        'local_ai_enabled': bool(getattr(settings, 'LOCAL_AI_BUDGET_PATH', '')),
        'calculated_rooms': sum(bool(r.get('known')) for r in estimate.snapshot['rooms']) if estimate else 0,
        'priced_positions': sum(r.get('line_total') is not None for r in estimate.snapshot['procurement']) if estimate else 0,
        'total_positions': len(estimate.snapshot['procurement']) if estimate else 0,
        'preview_page': next((r['page'] for r in (analysis.rooms if analysis else []) if r.get('area') and r.get('page')), 1),
    }, status=400 if manual_error else 200)


@require_GET
def whole_pdf(request, pk, estimate_id):
    upload = get_object_or_404(accessible_uploads(request), pk=pk)
    estimate = get_object_or_404(WholePlanEstimate, pk=estimate_id, upload=upload)
    from .whole_pdf import build_pdf
    response = HttpResponse(build_pdf(estimate), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="floor-estimate-{estimate.pk}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response
