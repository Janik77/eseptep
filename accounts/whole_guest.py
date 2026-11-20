"""Claim one explicitly saved private floor estimate after first-party authentication."""
from copy import deepcopy
from hashlib import sha256
from time import time

from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import get_language
from django.views.decorators.http import require_POST

from projects.models import ProjectUpload, WholePlanEstimate
from projects.plan_views import current_analysis
from projects.plan_analysis import read_raw, PlanError

from .models import ClientProject, SavedWholeEstimate, UserProfile

PENDING_WHOLE = 'pending_whole_save_v1'


def tr(ru, kk):
    return kk if (get_language() or '').startswith('kk') else ru


@require_POST
def guest_save(request, estimate_id):
    if request.user.is_authenticated or not request.session.session_key:
        raise Http404
    source = get_object_or_404(
        WholePlanEstimate.objects.select_related('upload'), pk=estimate_id,
        upload__user__isnull=True, upload__guest_session_key=request.session.session_key,
    )
    if source.upload.ai_summary.get('whole_estimate_id') != source.pk:
        return HttpResponseBadRequest(tr('Расчёт изменился. Вернитесь к новой версии.', 'Есеп өзгерді. Жаңа нұсқаға оралыңыз.'))
    request.session[PENDING_WHOLE] = {
        'upload': source.upload_id, 'estimate': source.pk,
        'action': 'quote' if request.POST.get('next') == 'quote' else 'save',
        'saved_at': int(time()),
    }
    return redirect('accounts:login')


def new_floor_project(user, source):
    snapshot = source.snapshot
    return ClientProject.objects.create(
        user=user, title=tr('Расчёт по плану', 'Жоспар бойынша есеп') + f' #{source.upload_id}',
        city=user.profile.city, area_m2=snapshot['known_area'], rooms=len(snapshot['rooms']),
    )


def finish_guest_save(request, origin_key):
    """Runs inside successful login/registration POST, not in a GET or bearer URL."""
    pending = request.session.pop(PENDING_WHOLE, None)
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    if not pending or not origin_key or role != UserProfile.Role.CLIENT:
        return None
    if time() - pending['saved_at'] > 3600:
        messages.warning(request, tr('Срок сохранения гостевого расчёта истёк.', 'Қонақ есебін сақтау мерзімі өтті.'))
        return None
    expected = ProjectUpload.objects.filter(pk=pending['upload'], user__isnull=True, guest_session_key=origin_key)
    with transaction.atomic():
        # One request can transfer the private upload, even with parallel login POSTs.
        if expected.update(guest_session_key=origin_key) != 1:
            return None
        upload = expected.get()
        source = WholePlanEstimate.objects.filter(pk=upload.ai_summary.get('whole_estimate_id'), upload=upload).first()
        if not source:
            return None
        summary = dict(upload.ai_summary)
        analysis = current_analysis(upload)
        if analysis:
            # Keep the original recorded attempt, including failures; never re-charge the claimed upload.
            summary['claimed_plan_analysis'] = analysis.pk
            try:
                summary['claimed_plan_digest'] = sha256(read_raw(upload)).hexdigest()
            except PlanError:
                pass
        upload.ai_summary = summary
        upload.user = request.user
        upload.guest_session_key = ''
        upload.save(update_fields=['ai_summary', 'user', 'guest_session_key'])
        project = new_floor_project(request.user, source)
        saved = SavedWholeEstimate.objects.create(project=project, source=source, snapshot=deepcopy(source.snapshot))
    if source.pk != pending['estimate']:
        messages.info(request, tr('Сохранена последняя версия расчёта.', 'Есептің соңғы нұсқасы сақталды.'))
    if pending['action'] == 'quote':
        from .views import _meeting_supplier
        if _meeting_supplier() is not None:
            return redirect('accounts:whole_preview', pk=saved.pk)
    return redirect('accounts:whole_saved', pk=saved.pk)
