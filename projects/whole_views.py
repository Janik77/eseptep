from decimal import Decimal
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
from .whole_plan import initial_rooms, persist_estimate, FINISHES


@require_http_methods(['GET', 'POST'])
def whole_plan(request, pk):
    upload = get_object_or_404(accessible_uploads(request), pk=pk)
    analysis = current_analysis(upload)
    estimates = WholePlanEstimate.objects.filter(upload=upload, snapshot__version=PARSER_VERSION)
    current_id = (upload.ai_summary or {}).get('whole_estimate_id')
    estimate = estimates.filter(pk=current_id).first() if isinstance(current_id, int) else estimates.order_by('-pk').first()
    error = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'analyze':
            try:
                analysis = analyze(upload)
                if analysis.status == 'completed':
                    persist_estimate(upload, initial_rooms(analysis), analysis.pk)
                else:
                    error = analysis.error_code or analysis.status
            except PlanError as exc:
                error = str(exc)
            if not error:
                return redirect('projects:whole_plan', pk=pk)
        elif action in ('update', 'save', 'supplier_simulate'):
            if not estimate or str(estimate.pk) != request.POST.get('estimate_id'):
                return HttpResponseBadRequest('Estimate changed. Reload this upload before editing.')
            if action == 'update':
                rows = [dict(r) for r in estimate.snapshot['rooms']]
                try:
                    index = int(request.POST.get('room', '-1'))
                    row = next(r for r in rows if r['index'] == index)
                    finish = request.POST.get('finish', row['finish'])
                    if finish not in FINISHES:
                        raise ValueError
                    row['finish'], row['finish_proposed'] = finish, False
                    if request.POST.get('area'):
                        number = area(request.POST['area'])
                        if number is None or Decimal(number) < 1:
                            raise ValueError
                        row['area'], row['source'] = number, 'manual'
                        row['visual_evidence'] = ''
                    persist_estimate(upload, rows, estimate.snapshot['analysis_id'])
                except (ValueError, StopIteration):
                    return HttpResponseBadRequest('Invalid room, finish or missing area.')
            elif action == 'supplier_simulate':
                if not settings.ESEPTEP_DEMO_MODE:
                    return HttpResponseBadRequest('Supplier simulation is available only in demo mode.')
                WholePlanEstimate.objects.filter(pk=estimate.pk, supplier_simulated_at__isnull=True).update(supplier_simulated_at=timezone.now())
            if action == 'save':
                messages.success(request, 'Смета сохранена. Эта версия доступна в PDF.' if not (get_language() or '').startswith('kk') else 'Смета сақталды. Бұл нұсқа PDF форматында қолжетімді.')
            return redirect('projects:whole_plan', pk=pk)
        else:
            return HttpResponseBadRequest('Unknown action.')
    if not estimate and analysis and analysis.status == 'completed':
        estimate = persist_estimate(upload, initial_rooms(analysis), analysis.pk)
    from .plan_messages import plan_message
    if not error and analysis and analysis.status in ('failed', 'unknown'):
        error = analysis.error_code or 'api_failed'
    if error:error = plan_message(error)
    return render(request, 'projects/whole_plan.html', {
        'upload': upload, 'analysis': analysis, 'estimate': estimate,
        'snapshot': estimate.snapshot if estimate else None, 'error': error,
        'local_ai_enabled': bool(getattr(settings, 'LOCAL_AI_BUDGET_PATH', '')),
        'preview_page': next((r['page'] for r in (analysis.rooms if analysis else []) if r.get('area') and r.get('page')), 1),
    })


@require_GET
def whole_pdf(request, pk, estimate_id):
    upload = get_object_or_404(accessible_uploads(request), pk=pk)
    estimate = get_object_or_404(WholePlanEstimate, pk=estimate_id, upload=upload)
    from .whole_pdf import build_pdf
    response = HttpResponse(build_pdf(estimate), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="floor-estimate-{estimate.pk}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response
