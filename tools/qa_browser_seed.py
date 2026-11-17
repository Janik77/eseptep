"""Create only synthetic data in an explicitly separate browser QA database."""
import os
from pathlib import Path
if os.environ.get('ESEPTEP_BROWSER_QA') != '1' or 'browser-qa' not in os.environ.get('DJANGO_DB_PATH', ''):
    raise SystemExit('Explicit isolated browser-qa DB required')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.contrib.auth.models import User
from accounts.models import UserProfile, ClientProject
user = User.objects.create_user(username='browser-qa@example.test', email='browser-qa@example.test', password='Synthetic-QA-Only-815!')
UserProfile.objects.create(user=user, role='client')
ClientProject.objects.create(user=user, title='QA project Ә Ғ Қ Ң Ө Ұ Ү Һ І', city='Шымкент', area_m2=60, rooms=2)

for role in ('master', 'supplier'):
    member = User.objects.create_user(username=f'{role}@example.test', email=f'{role}@example.test', password='Synthetic-QA-Only-815!')
    UserProfile.objects.create(user=member, role=role)

# Isolated price-admin scenarios only. Never production prices or real stores.
from datetime import date
from decimal import Decimal
from calculators.models import PriceBook, MaterialPrice
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.views import _get_form_data
from calculators.services import calculate_materials
from calculators.material_keys import material_key
User.objects.create_superuser(username='price-admin@example.test',email='price-admin@example.test',password='Synthetic-Price-Admin-815!')
definition=CALCULATORS_BY_SLUG['plitka-keramogranit']
result=calculate_materials(definition,_get_form_data(definition,None))
for version in ['qa-full','qa-partial']:
    book=PriceBook.objects.create(store_name='SYNTHETIC QA STORE',version=version,source_note='Synthetic browser fixture, not market prices',price_date=date(2026,1,1))
    for variant in result['variants']:
        rows=variant['materials'] if version=='qa-full' else variant['materials'][:1]
        for row in rows:
            MaterialPrice.objects.get_or_create(book=book,calculator_slug=definition['slug'],variant_key=variant['key'],material_key=material_key(row['title'],row['unit']),unit=row['unit'],defaults={'price':Decimal('12.34')})

from calculators.models import RenovationRateEdition
from projects.models import ProjectUpload
from django.core.files.base import ContentFile
import base64
for version,standard in [('qa-rates-v1','222.00'),('qa-rates-v2','444.00')]:
    RenovationRateEdition.objects.create(version=version,source_note='SYNTHETIC typed rate fixture, not market prices',effective_date=date(2026,1,1),economy_rate=Decimal('111.00'),standard_rate=Decimal(standard),premium_rate=Decimal('333.00'))
from projects.views import DEMO_AI_SUMMARY
legacy=ProjectUpload(user=user,comment='typed-pricing-legacy',area=Decimal('36.50'),repair_level='standard',ai_summary=DEMO_AI_SUMMARY)
legacy.file.save('synthetic-typed-legacy.png',ContentFile(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lErZAAAAAElFTkSuQmCC')),save=False)
legacy.save()

from calculators.models import SelfLevelMixEdition
for version,consumption in [('qa-mix-v1','15.00'),('qa-mix-v2','30.00')]:
    SelfLevelMixEdition.objects.create(version=version,consumption=Decimal(consumption),source_note='SYNTHETIC QA consumption, not a manufacturer recommendation',source_date=date(2026,1,1))
