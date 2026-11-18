"""Synthetic fixtures only; selecting an example never analyzes or sends it."""
from pathlib import Path
from django.conf import settings
from django.core.files.base import ContentFile
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from .models import ProjectUpload
from .views import accessible_uploads

SAMPLES={'clear':'apartment-explication.pdf','unreadable':'apartment-unreadable-area.pdf'}

@require_POST
def choose_sample(request):
    key=request.POST.get('sample')
    if not settings.ESEPTEP_DEMO_MODE or key not in SAMPLES:
        raise Http404
    if not request.user.is_authenticated and not request.session.session_key:
        request.session.create()
    marker='MEETING_SAMPLE:'+key
    upload=accessible_uploads(request).filter(comment=marker).first()
    if upload is None:
        raw=Path(settings.BASE_DIR,'tests','fixtures','plans',SAMPLES[key]).read_bytes()
        upload=ProjectUpload(user=request.user if request.user.is_authenticated else None,
            guest_session_key='' if request.user.is_authenticated else request.session.session_key,
            comment=marker,ai_status='not_started',ai_summary={})
        upload.file.save(SAMPLES[key],ContentFile(raw),save=True)
    return redirect('projects:plan_review',pk=upload.pk)
