from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _, get_language
from core.openai_client import AIConfigurationError
from .models import Calculation
from .ai_explanation import explain

@login_required
@require_POST
def explain_estimate(request, calculation_id):
    calculation = get_object_or_404(Calculation, pk=calculation_id, project__user=request.user)
    try:
        explain(calculation, get_language())
    except AIConfigurationError:
        messages.error(request, _('ИИ пока не подключён. Расчёт и сохранённая смета продолжают работать.'))
    return redirect('accounts:calculation_detail', calculation_id=calculation.pk)
