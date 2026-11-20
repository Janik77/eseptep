"""Synthetic fixtures only; deliberately labeled and no external analysis."""
import json
from pathlib import Path
from django.conf import settings
from django.core.files.base import ContentFile
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from .models import ProjectUpload, PlanAnalysis
from .plan_analysis import analysis_identity, area

from .views import accessible_uploads

SAMPLES={'clear':'apartment-explication.pdf','unreadable':'apartment-unreadable-area.pdf',
         'studio':'typical-studio.pdf','two-room':'typical-two-room.pdf','three-room':'typical-three-room.pdf'}

def _catalog():
    return json.loads(Path(settings.BASE_DIR,'tests','fixtures','plans','typical-manifest.json').read_text(encoding='utf-8'))


def typical_plans():
    # The catalog describes example files; seeded result is labeled separately.
    return [{k:item[k] for k in ('key','title','rooms','area','preview')} for item in _catalog()]

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
    sample = next((item for item in _catalog() if item['key'] == key), None)
    if sample:
        # Use only repository-owned example bytes, not user-controlled uploads.
        raw = Path(settings.BASE_DIR, 'tests', 'fixtures', 'plans', SAMPLES[key]).read_bytes()
        preview = sample['ground_truth']
        rooms = [dict(name=row['name'], kind=row['kind'], area=area(row['area']), page=row['page'],
            source='stated', visual_evidence='', evidence='', finish=None) for row in preview]
        identity = analysis_identity(f'demo-sample:{upload.pk}', raw)
        PlanAnalysis.objects.get_or_create(identity=identity, defaults={
            'upload': upload, 'status': 'completed', 'model': 'offline-fixture', 'rooms': rooms})
        return redirect('projects:whole_plan', pk=upload.pk)
    return redirect('projects:plan_review',pk=upload.pk)
