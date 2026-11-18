from django.conf import settings
from django.core.management.base import BaseCommand
from core.openai_client import ALLOWED_MODELS
from projects.models import PlanAnalysisBudget

class Command(BaseCommand):
    help='Offline redacted API configuration check. Never contacts OpenAI.'
    def handle(self,*args,**options):
        key=settings.OPENAI_API_KEY.strip()
        self.stdout.write('Key configured: '+str(bool(key) and not key.startswith(('PASTE_','REPLACE_'))))
        self.stdout.write('Model: '+settings.OPENAI_MODEL+'; allowlisted: '+str(settings.OPENAI_MODEL in ALLOWED_MODELS))
        self.stdout.write('Live confirmation: '+str(settings.OPENAI_LIVE_CONFIRMED))
        self.stdout.write('Plan enabled: '+str(settings.PLAN_AI_ENABLED)+'; estimate explanation enabled: '+str(settings.ESTIMATE_AI_ENABLED))
        try:budget=PlanAnalysisBudget.objects.filter(pk=1).first()
        except Exception:budget=None
        self.stdout.write('This database reserved cents: '+(str(budget.reserved_cents) if budget else 'ledger absent; previous spend unknown'))
        self.stdout.write('Offline only. No API request was sent.')
