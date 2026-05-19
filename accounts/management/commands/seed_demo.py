from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import (
    Calculation,
    ClientProject,
    MasterProfile,
    MasterResponse,
    ServiceRequest,
    SupplierMaterial,
    SupplierProfile,
    SupplierResponse,
    UserProfile,
)


class Command(BaseCommand):
    help = 'Seed demo data for ESEPTEP dashboards and admin.'

    def handle(self, *args, **options):
        client_user, _ = self._ensure_user(
            email='client@eseptep.demo',
            first_name='Демо Клиент',
            role=UserProfile.Role.CLIENT,
            phone='+77010000001',
            city='Астана',
        )

        masters = [
            ('master1@eseptep.demo', 'Азамат Рахимов', 'Черновые работы', 'Алматы', 9, Decimal('4.9')),
            ('master2@eseptep.demo', 'Айдана Сеитова', 'Плитка и санузлы', 'Астана', 7, Decimal('5.0')),
            ('master3@eseptep.demo', 'Руслан Темир', 'Электрика', 'Шымкент', 8, Decimal('4.8')),
        ]
        master_profiles = []
        for email, name, spec, city, exp, rating in masters:
            user, _ = self._ensure_user(email=email, first_name=name, role=UserProfile.Role.MASTER, phone='+77010000002', city=city)
            profile, _ = MasterProfile.objects.get_or_create(
                user=user,
                defaults={
                    'full_name': name,
                    'city': city,
                    'specialization': spec,
                    'experience_years': exp,
                    'rating': rating,
                    'is_available': True,
                    'whatsapp': '+77070000000',
                    'description': f'Демо мастер: {spec}',
                },
            )
            master_profiles.append(profile)

        suppliers = [
            ('supplier1@eseptep.demo', 'СтройМарт Astana', 'Астана', 'пр. Кабанбай Батыра, 48'),
            ('supplier2@eseptep.demo', 'Keruen Build Market', 'Астана', 'ул. Сыганак, 16/5'),
            ('supplier3@eseptep.demo', 'ДомСтрой склад', 'Астана', 'ул. Алаш, 29'),
        ]
        supplier_profiles = []
        for email, company, city, address in suppliers:
            user, _ = self._ensure_user(email=email, first_name=company, role=UserProfile.Role.SUPPLIER, phone='+77010000003', city=city)
            profile, _ = SupplierProfile.objects.get_or_create(
                user=user,
                defaults={
                    'company_name': company,
                    'city': city,
                    'address': address,
                    'whatsapp': '+77070000001',
                    'delivery_info': 'Доставка в течение 1-2 дней',
                    'description': f'Демо поставщик: {company}',
                    'is_active': True,
                },
            )
            supplier_profiles.append(profile)

        materials_data = [
            ('Штукатурка гипсовая', 'Смеси', 'мешок', Decimal('3200.00'), 'В наличии', '1 день'),
            ('Грунтовка глубокого проникновения', 'Грунтовки', 'канистра', Decimal('2900.00'), 'В наличии', '1 день'),
            ('Гипсокартон 12.5 мм', 'ГКЛ', 'лист', Decimal('5400.00'), 'В наличии', '2 дня'),
            ('Профиль CD 60', 'Металлопрофиль', 'шт', Decimal('1800.00'), 'В наличии', '1 день'),
            ('Плиточный клей', 'Клеи', 'мешок', Decimal('3700.00'), 'В наличии', '1 день'),
            ('Плитка керамогранит', 'Плитка', 'м²', Decimal('8900.00'), 'Под заказ', '3 дня'),
            ('Кабель ВВГ 3x2.5', 'Электрика', 'м', Decimal('420.00'), 'В наличии', '1 день'),
            ('Автомат 16А', 'Электрика', 'шт', Decimal('1600.00'), 'В наличии', '1 день'),
            ('Труба PPR 25', 'Сантехника', 'м', Decimal('650.00'), 'В наличии', '2 дня'),
            ('Ламинат 33 класс', 'Напольные покрытия', 'м²', Decimal('7200.00'), 'Под заказ', '4 дня'),
        ]
        for i, material in enumerate(materials_data):
            supplier = supplier_profiles[i % len(supplier_profiles)]
            SupplierMaterial.objects.get_or_create(
                supplier=supplier,
                name=material[0],
                defaults={
                    'category': material[1],
                    'unit': material[2],
                    'price': material[3],
                    'stock_status': material[4],
                    'delivery_time': material[5],
                },
            )

        project_1, _ = ClientProject.objects.get_or_create(
            user=client_user,
            title='ЖК GreenLine — 2к квартира',
            defaults={
                'city': 'Астана',
                'area_m2': Decimal('62.50'),
                'rooms': 2,
                'repair_segment': ClientProject.RepairSegment.COMFORT,
                'status': ClientProject.Status.CALCULATED,
            },
        )
        project_2, _ = ClientProject.objects.get_or_create(
            user=client_user,
            title='ЖК Expo Plaza — 1к квартира',
            defaults={
                'city': 'Астана',
                'area_m2': Decimal('44.00'),
                'rooms': 1,
                'repair_segment': ClientProject.RepairSegment.ECONOMY,
                'status': ClientProject.Status.SUBMITTED,
            },
        )

        calc_1, _ = Calculation.objects.get_or_create(
            project=project_1,
            calculator_slug='shtukaturka',
            defaults={
                'area_m2': Decimal('62.50'),
                'rooms': 2,
                'thickness': Decimal('3.00'),
                'segment': ClientProject.RepairSegment.COMFORT,
                'materials_total': Decimal('380000.00'),
                'works_total': Decimal('245000.00'),
                'grand_total': Decimal('625000.00'),
                'result_data': {'materials': ['Штукатурка', 'Грунтовка'], 'note': 'Демо смета 1'},
            },
        )
        calc_2, _ = Calculation.objects.get_or_create(
            project=project_2,
            calculator_slug='gipsokarton',
            defaults={
                'area_m2': Decimal('44.00'),
                'rooms': 1,
                'thickness': Decimal('2.00'),
                'segment': ClientProject.RepairSegment.ECONOMY,
                'materials_total': Decimal('220000.00'),
                'works_total': Decimal('150000.00'),
                'grand_total': Decimal('370000.00'),
                'result_data': {'materials': ['ГКЛ', 'Профиль'], 'note': 'Демо смета 2'},
            },
        )

        req_1, _ = ServiceRequest.objects.get_or_create(
            client=client_user,
            project=project_1,
            calculation=calc_1,
            request_type=ServiceRequest.RequestType.MASTER,
            defaults={'status': ServiceRequest.Status.RESPONDED, 'comment': 'Нужна бригада для черновых работ.'},
        )
        req_2, _ = ServiceRequest.objects.get_or_create(
            client=client_user,
            project=project_2,
            calculation=calc_2,
            request_type=ServiceRequest.RequestType.SUPPLIER,
            defaults={'status': ServiceRequest.Status.RESPONDED, 'comment': 'Нужны материалы с доставкой.'},
        )

        for i, master in enumerate(master_profiles[:2], start=1):
            MasterResponse.objects.get_or_create(
                request=req_1,
                master=master,
                defaults={
                    'price_from': Decimal('590000.00') + i * Decimal('25000.00'),
                    'message': f'Готовы начать через {i} дня. Опыт в похожих проектах.',
                    'status': MasterResponse.Status.PENDING,
                },
            )

        for i, supplier in enumerate(supplier_profiles[:2], start=1):
            SupplierResponse.objects.get_or_create(
                request=req_2,
                supplier=supplier,
                defaults={
                    'total_price': Decimal('345000.00') + i * Decimal('15000.00'),
                    'message': f'Комплектация в наличии. Срок поставки: {i+1} дня.',
                    'status': SupplierResponse.Status.PENDING,
                },
            )

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))

    def _ensure_user(self, email, first_name, role, phone, city):
        user, created = User.objects.get_or_create(
            username=email,
            defaults={
                'email': email,
                'first_name': first_name,
            },
        )
        if created:
            user.set_password('DemoPass123!')
            user.save(update_fields=['password'])

        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': role,
                'phone': phone,
                'city': city,
            },
        )
        changed = False
        if profile.role != role:
            profile.role = role
            changed = True
        if city and profile.city != city:
            profile.city = city
            changed = True
        if phone and profile.phone != phone:
            profile.phone = phone
            changed = True
        if changed:
            profile.save(update_fields=['role', 'city', 'phone'])
        return user, profile
