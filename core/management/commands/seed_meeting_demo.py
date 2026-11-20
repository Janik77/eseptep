"""Idempotent synthetic presentation dataset. Never resets data or AI reservations."""
from datetime import date
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from accounts.models import UserProfile, SupplierProfile, MasterProfile, ClientProject
from calculators.models import PriceBook, MaterialPrice, RenovationRateEdition
from calculators.definitions import CALCULATORS_BY_SLUG
from calculators.services import calculate_materials
from calculators.material_keys import material_key

DEMO_PASSWORD = 'Demo-Meeting-2026!'
USERNAMES = ('demo-client@example.test', 'demo-supplier@example.test', 'demo-master@example.test')

class Command(BaseCommand):
    help = 'Prepare repeatable synthetic meeting data only in a separate demo database.'

    def add_arguments(self, parser):
        parser.add_argument('--confirm-isolated', action='store_true')
        parser.add_argument('--price-version', choices=('v1','v2'), default='v1')

    @transaction.atomic
    def handle(self, *args, **options):
        if settings.PRODUCTION or not settings.ESEPTEP_DEMO_MODE or not options['confirm_isolated']:
            raise CommandError('Explicit non-production ESEPTEP_DEMO_MODE and --confirm-isolated required.')
        if (User.objects.exclude(username__in=USERNAMES).exists()
                or PriceBook.objects.exclude(version__startswith='meeting-demo-').exists()
                or RenovationRateEdition.objects.exclude(version__startswith='meeting-demo-').exists()):
            raise CommandError('Database contains non-meeting records. Refusing to seed; choose a separate empty demo database.')
        users=[]
        for name,role in zip(USERNAMES, ('client','supplier','master')):
            user,created=User.objects.get_or_create(username=name, defaults={'email':name})
            if created:
                user.set_password(DEMO_PASSWORD);user.save(update_fields=['password'])
            profile,_=UserProfile.objects.get_or_create(user=user, defaults={'role':role,'city':'Шымкент'})
            if profile.role != role:
                raise CommandError('Existing role differs; refusing to change a profile.')
            users.append(user)
        ClientProject.objects.get_or_create(user=users[0], title='Демонстрационная квартира · 36,5 м²', defaults={
            'city':'Шымкент','area_m2':Decimal('36.50'),'rooms':2,'repair_segment':'comfort'})
        SupplierProfile.objects.get_or_create(user=users[1], defaults={'company_name':'ДЕМО-магазин ESEPTEP',
            'city':'Шымкент','address':'Учебный адрес, не реальный магазин','description':'Только демонстрационные заявки; внешние уведомления отключены.'})
        MasterProfile.objects.get_or_create(user=users[2], defaults={'full_name':'ДЕМО-мастер ESEPTEP',
            'city':'Шымкент','specialization':'Учебный ремонт под ключ','description':'Только тестовые ответы внутри кабинета.'})
        version=options['price_version']
        book,created=PriceBook.objects.get_or_create(version='meeting-demo-'+version, defaults={
            'store_name':'ДЕМО-магазин ESEPTEP','source_note':'Учебные цены. Не коммерческое предложение.',
            'price_date':date(2026,11,18)})
        if created:
            definition=CALCULATORS_BY_SLUG['plitka-keramogranit']
            result=calculate_materials(definition, {'area':'36.5','zone':'floor','tile_format':'60x60'})
            for variant in result['variants']:
                for index,row in enumerate(variant['materials'][:-1]):
                    MaterialPrice.objects.create(book=book,calculator_slug=definition['slug'],variant_key=variant['key'],
                        material_key=material_key(row['title'],row['unit']),unit=row['unit'],price=Decimal(str([6500,300,2200,1400][index])) * (2 if version == 'v2' else 1))
            # Publish only this new demo edition. A repeat never overwrites changed prices.
            if version == 'v2' or not PriceBook.objects.filter(is_active=True).exists():
                from calculators.pricing import lock_price_configuration
                lock_price_configuration()
                PriceBook.objects.filter(is_active=True).update(is_active=False)
                book.is_active=True;book.published_at=timezone.now();book.save(update_fields=['is_active','published_at'])
        if not RenovationRateEdition.objects.exists():
            RenovationRateEdition.objects.create(version='meeting-demo-rates-v1',source_note='Учебные тарифы для демонстрации.',
                effective_date=date(2026,11,18),economy_rate=Decimal('120000'),standard_rate=Decimal('170000'),premium_rate=Decimal('250000'),
                is_active=True,published_at=timezone.now())
        self.stdout.write(self.style.SUCCESS('Meeting demo prepared. Repeated execution preserves accounts, estimates, price editions and AI reservations.'))
        self.stdout.write('Synthetic client: demo-client@example.test | supplier: demo-supplier@example.test')
        # Never print a credential; fixed synthetic login is documented separately.
