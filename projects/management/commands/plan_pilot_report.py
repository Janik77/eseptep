"""Report pilot attempts without logging documents, room names or credentials."""
import json
from decimal import Decimal
from django.core.management.base import BaseCommand
from projects.models import PlanAnalysis, PlanAnalysisBudget

class Command(BaseCommand):
    help = 'Report persistent anonymized-plan pilot usage (token-based estimate, not invoice).'

    def handle(self, *args, **options):
        rows = []
        for item in PlanAnalysis.objects.all():
            usage = item.usage
            estimate = ((Decimal(usage.get('input_tokens', 0)) * Decimal('.40') + Decimal(usage.get('output_tokens', 0)) * Decimal('1.60')) / 1_000_000) if usage else None
            rows.append({'id':item.pk,'model':item.model,'status':item.status,'error':item.error_code,'elapsed_ms':item.elapsed_ms,
                         'usage':usage,'estimated_usd':str(estimate) if estimate is not None else None})
        budget = PlanAnalysisBudget.objects.filter(pk=1).first()
        self.stdout.write(json.dumps({'reserved_cents':budget.reserved_cents if budget else 0,'ceiling_cents':200,
                                     'attempts':rows,'note':'Reservations are pessimistic, not billed cost. Unknown attempts remain reserved.'}, indent=2))
