"""Report pilot attempts without logging documents, room names or credentials."""
import json
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from projects.models import PlanAnalysis, PlanAnalysisBudget
from accounts.models import EstimateExplanation

class Command(BaseCommand):
    help = 'Report persistent anonymized-plan pilot usage (token-based estimate, not invoice).'

    def handle(self, *args, **options):
        rows = []
        for item in list(PlanAnalysis.objects.all())+list(EstimateExplanation.objects.all()):
            usage = item.usage
            prices={'gpt-6.1-sol':('2','10'),'gpt-4.1-mini-2025-04-14':('.4','1.6'),'gpt-5.4-mini-2026-03-17':('.75','4.5')}.get(item.model)
            estimate=((Decimal(usage.get('input_tokens',0))*Decimal(prices[0])+Decimal(usage.get('output_tokens',0))*Decimal(prices[1]))/1_000_000) if usage and prices else None
            rows.append({'id':item.pk,'model':item.model,'status':item.status,'error':item.error_code,'elapsed_ms':getattr(item,'elapsed_ms',None),'operation':type(item).__name__,
                         'usage':usage,'estimated_usd':str(estimate) if estimate is not None else None})
        budget = PlanAnalysisBudget.objects.filter(pk=1).first()
        self.stdout.write(json.dumps({'reserved_cents':budget.reserved_cents if budget else None,'ceiling_cents':settings.OPENAI_PILOT_MAX_RESERVED_CENTS,
                                     'attempts':rows,'note':'Reservations are pessimistic, not billed cost. Missing ledger means unknown prior spend. Token estimates exclude discounts and are not invoices. Unknown attempts remain reserved.'}, indent=2))
