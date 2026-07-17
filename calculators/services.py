"""Server-side calculator services for ESEPTEP."""

from math import ceil, sqrt

from accounts.models import Calculation, ClientProject

from .definitions import SEGMENTS

SEGMENT_ALIASES = {'econom': 'economy'}
PLAIN_REFERENCE = {'label': 'Предварительно', 'material': 1.0, 'labor': 0}


def to_float(value, default):
    """Convert form values to float while supporting comma decimals."""
    try:
        return float(str(value).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return default


def calculate_materials(calculator, form_data):
    """Calculate material quantities on the server."""
    calculators = {
        'demontazh': _calculate_demontazh,
        'elektrika': _calculate_elektrika,
        'santehnika': _calculate_santehnika,
        'shtukaturka': _calculate_shtukaturka,
        'gipsokarton-potolok': _calculate_gipsokarton,
        'nalivnoy-pol': _calculate_nalivnoy_pol,
        'plitka-keramogranit': _calculate_plitka,
        'laminat-spc-parket': _calculate_laminat_spc_parket,
        'malyarka': _calculate_malyarka,
        'natyazhnoy-potolok': _calculate_natyazhnoy_potolok,
        'dveri': _calculate_dveri,
        'teplyy-pol': _calculate_teplyy_pol,
    }
    calculator_func = calculators.get(calculator['slug'], _calculate_ratio_based)
    return calculator_func(calculator, form_data)


def save_calculation_for_user(user, slug, result):
    """Persist a server-calculated estimate for the authenticated client."""
    project = user.client_projects.order_by('-created_at').first()
    if project is None:
        project = ClientProject.objects.create(
            user=user,
            title=f'Проект {slug}',
            city=getattr(user.profile, 'city', '') or 'Не указан',
            area_m2=result['meta']['area'],
            rooms=result['meta']['rooms'],
            repair_segment=result['meta']['segment'],
            status=ClientProject.Status.CALCULATED,
        )

    calculation = Calculation.objects.create(
        project=project,
        calculator_slug=slug,
        area_m2=result['meta']['area'],
        rooms=result['meta']['rooms'],
        thickness=result['meta']['thickness'],
        segment=result['meta']['segment'],
        materials_total=result['materials_total'],
        works_total=result['labor_total'],
        grand_total=result['grand_total'],
        result_data={
            'materials': result['materials'],
            'variants': result.get('variants'),
            'selected_variant': result.get('selected_variant'),
            'totals': result.get('totals', {
                'materials_total': result['materials_total'],
                'grand_total': result['grand_total'],
            }),
            'summary': result['summary'],
            'segment_label': result['segment_label'],
            'warning': result['warning'],
            'input': result['meta'].get('input', {}),
            'metrics': result.get('metrics', []),
        },
    )
    return project, calculation


def _calculate_ratio_based(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    materials = [_row(material, area * material['ratio']) for material in calculator['materials']]
    return _build_result(calculator, materials, form_data, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} {calculator['unit']}")


def _calculate_demontazh(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    demolition_type = form_data.get('demolition_type') or form_data.get('type', 'partial')
    selected_variant = form_data.get('selected_variant', 'optimal')

    film_m2 = ceil(area * 1.2)
    tape = max(1, ceil(area / 25))
    gloves = max(1, ceil(area / 30))
    truck = max(1, ceil(area / 45))

    if demolition_type == 'cosmetic':
        bags = {'base': ceil(area * 0.8), 'optimal': ceil(area * 1.1), 'maximum': ceil(area * 1.4)}
        disks = max(1, ceil(area / 50))
        respirators = max(1, ceil(area / 60))
        container = 0
    elif demolition_type == 'full':
        bags = {'base': ceil(area * 2.2), 'optimal': ceil(area * 2.8), 'maximum': ceil(area * 3.5)}
        disks = ceil(area / 25)
        respirators = ceil(area / 20)
        container = max(1, ceil(area / 45))
    else:
        bags = {'base': ceil(area * 1.4), 'optimal': ceil(area * 1.6), 'maximum': ceil(area * 2.3)}
        disks = max(1, ceil(area / 35))
        respirators = max(1, ceil(area / 35))
        container = 0

    variants = {
        'base': _variant('base', 'Базовый', 'Минимальные расходники и базовый вывоз мусора.', [
            _variant_row('Мешки строительные 50 кг', bags['base'], 'шт', 70),
            _variant_row('Плёнка защитная', film_m2, 'м²', 35),
            _variant_row('Бумажный малярный скотч', tape, 'шт', 900),
            _variant_row('Перчатки рабочие', gloves, 'пар', 150),
            _variant_row('Алмазный диск / расходный диск', disks, 'шт', 1500),
            _variant_row('Вывоз мусора / машина', truck, 'рейс', 25000),
            _variant_row('Контейнер для мусора', container, 'шт', 80000),
        ]),
        'optimal': _variant('optimal', 'Оптимальный', 'Самый практичный вариант: нормальные расходники и вывоз.', [
            _variant_row('Мешки строительные 50 кг', bags['optimal'], 'шт', 80),
            _variant_row('Плёнка защитная плотная', film_m2, 'м²', 45),
            _variant_row('Бумажный малярный скотч', tape, 'шт', 1200),
            _variant_row('Перчатки рабочие', gloves, 'пар', 250),
            _variant_row('Респиратор / маска', respirators, 'шт', 800),
            _variant_row('Алмазный диск средний', disks, 'шт', 3500),
            _variant_row('Вывоз мусора / Газель', truck, 'рейс', 35000),
            _variant_row('Контейнер для строительного мусора', container, 'шт', 100000),
        ]),
        'maximum': _variant('maximum', 'Максимальный', 'Больше запас расходников, защита от пыли и усиленный вывоз.', [
            _variant_row('Мешки строительные 50 кг', bags['maximum'], 'шт', 90),
            _variant_row('Плёнка защитная плотная', film_m2, 'м²', 55),
            _variant_row('Бумажный малярный скотч', tape, 'шт', 1600),
            _variant_row('Перчатки рабочие', gloves, 'пар', 450),
            _variant_row('Респиратор / защита от пыли', respirators, 'шт', 1500),
            _variant_row('Алмазный диск хороший', disks, 'шт', 7000),
            _variant_row('Вывоз мусора / отдельная машина', truck, 'рейс', 45000),
            _variant_row('Контейнер для строительного мусора', container, 'шт', 120000),
        ]),
    }
    return _build_variant_result(calculator, variants, selected_variant, form_data, area, 1, 1, f"{calculator['title']} · {area:g} м² · {demolition_type}")


ELECTRIC_COMFORT_PRICES = {
    'Кабель ВВГнг-LS 3×1.5': 520,
    'Кабель ВВГнг-LS 3×2.5': 780,
    'Кабель ВВГнг-LS 3×6': 1900,
    'Гофра 16 мм': 120,
    'Гофра 20 мм': 160,
    'Клипсы для гофры': 25,
    'Дюбель-гвоздь / анкер': 20,
    'Гвозди Toua': 25,
    'Розетки': 2500,
    'Выключатели': 2500,
    'Подрозетники': 250,
    'Распредкоробки': 500,
    'Автомат 10А': 3000,
    'Автомат 16А': 3200,
    'Автомат 25А': 4500,
    'Автомат 32А': 5500,
    'УЗО': 12000,
    'Дифавтомат': 16000,
    'Реле напряжения': 20000,
    'Электрощит 36 модулей': 40000,
    'DIN-рейка': 2000,
    'Нулевая шина': 1800,
    'Заземляющая шина': 1800,
    'Клеммы WAGO': 160,
    'Интернет кабель UTP': 200,
    'ТВ кабель': 220,
    'Кабель домофона': 180,
    'Изолента': 700,
    'Стяжки пластиковые': 1800,
    'Алебастр / гипс': 300,
}
ELECTRIC_VARIANT_TOTAL_RATIOS = {
    'economy': 420600 / 778070,
    'comfort': 1,
    'business': 1758000 / 778070,
}
ELECTRIC_AREA_DEPENDENT = {
    'Кабель ВВГнг-LS 3×1.5', 'Кабель ВВГнг-LS 3×2.5', 'Кабель ВВГнг-LS 3×6',
    'Гофра 16 мм', 'Гофра 20 мм', 'Клипсы для гофры', 'Дюбель-гвоздь / анкер',
    'Гвозди Toua', 'Интернет кабель UTP', 'ТВ кабель', 'Кабель домофона', 'Алебастр / гипс'
}
ELECTRIC_ROOM_DEPENDENT = {
    'Розетки', 'Выключатели', 'Подрозетники', 'Распредкоробки', 'Автомат 10А',
    'Автомат 16А', 'УЗО', 'Дифавтомат', 'DIN-рейка', 'Клеммы WAGO', 'Изолента'
}
ELECTRIC_FIXED = {
    'Автомат 25А', 'Автомат 32А', 'Реле напряжения', 'Электрощит 36 модулей',
    'Нулевая шина', 'Заземляющая шина', 'Стяжки пластиковые'
}
ELECTRIC_COMFORT_REFERENCE_TOTALS = {
    (10, 1): 400150,
    (20, 2): 494430,
    (30, 1): 541970,
    (40, 2): 636250,
    (60, 2): 778070,
    (60, 3): 807150,
    (80, 3): 948970,
    (100, 4): 1129720,
}


def _electric_quantities(area, rooms):
    quantities = {
        'Кабель ВВГнг-LS 3×1.5': ceil(area * 2.2),
        'Кабель ВВГнг-LS 3×2.5': ceil(area * 4.4),
        'Кабель ВВГнг-LS 3×6': ceil(area * 0.45),
        'Гофра 16 мм': ceil(area * 2.5),
        'Гофра 20 мм': ceil((ceil(area * 4.4) + ceil(area * 0.45)) * 0.39),
        'Розетки': max(rooms * 4 + 6, ceil(area * 0.5 + rooms * 4)),
        'Выключатели': max(rooms + 2, ceil(area * 0.15 + rooms * 2)),
        'Распредкоробки': max(rooms + 2, ceil(area * 0.15 + rooms * 2)),
        'Автомат 10А': max(2, rooms + 1),
        'Автомат 16А': max(4, rooms * 2 + 2),
        'Автомат 25А': 1,
        'Автомат 32А': 1,
        'УЗО': max(2, rooms + 1),
        'Дифавтомат': max(1, rooms),
        'Реле напряжения': 1,
        'Электрощит 36 модулей': 1,
        'Нулевая шина': max(1, rooms),
        'Заземляющая шина': max(1, rooms),
        'Интернет кабель UTP': ceil(area * 0.8),
        'ТВ кабель': ceil(area * 0.45),
        'Кабель домофона': ceil(area * 0.15),
        'Изолента': max(2, ceil(area / 12)),
        'Стяжки пластиковые': max(2, ceil(area / 40)),
    }
    quantities['Подрозетники'] = quantities['Розетки'] + quantities['Выключатели']
    cable_protection = quantities['Гофра 16 мм'] + quantities['Гофра 20 мм']
    quantities['Клипсы для гофры'] = ceil(cable_protection * 2.5)
    quantities['Дюбель-гвоздь / анкер'] = ceil(cable_protection * 2.5)
    quantities['Гвозди Toua'] = ceil(cable_protection * 2.5)
    quantities['DIN-рейка'] = max(1, ceil((quantities['Автомат 10А'] + quantities['Автомат 16А'] + quantities['УЗО'] + quantities['Дифавтомат']) / 5))
    quantities['Клеммы WAGO'] = ceil(quantities['Распредкоробки'] * 7)
    quantities['Алебастр / гипс'] = ceil(quantities['Подрозетники'] * 0.3)
    return quantities


ELECTRIC_REFERENCE_MATRIX = {
    key: {
        'area': key[0],
        'rooms': key[1],
        'variants': {
            variant: round(total * ratio)
            for variant, ratio in ELECTRIC_VARIANT_TOTAL_RATIOS.items()
        },
        'comfort_materials': _electric_quantities(*key),
    }
    for key, total in ELECTRIC_COMFORT_REFERENCE_TOTALS.items()
}


def _nearest_electric_reference(area, rooms):
    return min(
        ELECTRIC_REFERENCE_MATRIX.values(),
        key=lambda item: abs(item['area'] - area) / max(area, 1) + abs(item['rooms'] - rooms) * 0.35,
    )


def _scaled_electric_quantities(area, rooms, reference):
    quantities = {}
    area_scale = area / reference['area'] if reference['area'] else 1
    room_scale = rooms / reference['rooms'] if reference['rooms'] else 1
    for title, quantity in reference['comfort_materials'].items():
        if title in ELECTRIC_AREA_DEPENDENT:
            quantities[title] = max(1, ceil(quantity * area_scale))
        elif title in ELECTRIC_ROOM_DEPENDENT:
            quantities[title] = max(1, ceil(quantity * room_scale))
        else:
            quantities[title] = quantity
    quantities['Подрозетники'] = quantities['Розетки'] + quantities['Выключатели']
    quantities['Клеммы WAGO'] = ceil(quantities['Распредкоробки'] * 7)
    quantities['Алебастр / гипс'] = ceil(quantities['Подрозетники'] * 0.3)
    return quantities


def _electric_rows(calculator, quantities, price_ratio=1):
    rows = []
    for material in calculator['materials']:
        price = round(ELECTRIC_COMFORT_PRICES[material['title']] * price_ratio)
        rows.append(_variant_row(material['title'], quantities[material['title']], material['unit'], price))
    return rows


def _calculate_elektrika(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    selected_variant = form_data.get('selected_variant', 'comfort')
    matrix_key = (round(area), rooms)
    reference = ELECTRIC_REFERENCE_MATRIX.get(matrix_key)
    exact_match = reference is not None and area == matrix_key[0]
    if reference is None:
        reference = _nearest_electric_reference(area, rooms)
        quantities = _scaled_electric_quantities(area, rooms, reference)
        comfort_total = sum(
            quantities[title] * ELECTRIC_COMFORT_PRICES[title]
            for title in ELECTRIC_COMFORT_PRICES
        )
        variant_totals = {
            key: round(comfort_total * ratio)
            for key, ratio in ELECTRIC_VARIANT_TOTAL_RATIOS.items()
        }
    else:
        quantities = reference['comfort_materials']
        variant_totals = reference['variants']

    variant_settings = {
        'economy': {'title': 'Эконом', 'price': ELECTRIC_VARIANT_TOTAL_RATIOS['economy'], 'description': 'Минимальная комплектация для базовой разводки без большого запаса.'},
        'comfort': {'title': 'Комфорт', 'price': 1, 'description': 'Оптимальная комплектация: кабель, защита, щит и слаботочные линии с нормальным запасом.'},
        'business': {'title': 'Бизнес', 'price': ELECTRIC_VARIANT_TOTAL_RATIOS['business'], 'description': 'Расширенная комплектация: больше групп, защиты, кабеля и расходников.'},
    }

    variants = {}
    for key, settings in variant_settings.items():
        rows = _electric_rows(calculator, quantities, settings['price'])
        variant = _variant(key, settings['title'], settings['description'], rows)
        if exact_match:
            variant['total'] = variant['reference_total'] = variant_totals[key]
        variants[key] = variant

    return _build_variant_result(calculator, variants, selected_variant, form_data, area, rooms, 1, f"{calculator['title']} · {area:g} м² · {rooms} комн.")


def _calculate_santehnika(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    baths = max(1, int(to_float(form_data.get('bathrooms'), 1)))
    kitchen_point = 1
    selected_variant = form_data.get('selected_variant', 'comfort')
    price_sets = {
        'economy': {'water': 450, 'sewer50': 650, 'sewer110': 1800, 'fittings': 350, 'valves': 2500, 'collector': 12000, 'toilet': 35000, 'sink': 25000, 'mixer': 18000, 'shower': 45000, 'siphon': 2500, 'insulation': 250},
        'comfort': {'water': 700, 'sewer50': 900, 'sewer110': 2500, 'fittings': 600, 'valves': 4500, 'collector': 25000, 'toilet': 70000, 'sink': 50000, 'mixer': 35000, 'shower': 90000, 'siphon': 4500, 'insulation': 350},
        'business': {'water': 1100, 'sewer50': 1400, 'sewer110': 3500, 'fittings': 1000, 'valves': 8000, 'collector': 50000, 'toilet': 150000, 'sink': 100000, 'mixer': 80000, 'shower': 180000, 'siphon': 8000, 'insulation': 500},
    }

    def plumbing_variant(key, title, description, values, extra=0):
        prices = price_sets[key]
        materials = [
            _variant_row('Труба водоснабжения', values['waterPipe'], 'м', prices['water']),
            _variant_row('Канализационная труба Ø50', values['sewer50'], 'м', prices['sewer50']),
            _variant_row('Канализационная труба Ø110', values['sewer110'], 'м', prices['sewer110']),
            _variant_row('Фитинги / уголки / муфты', values['fittings'], 'шт', prices['fittings']),
            _variant_row('Краны / запорная арматура', values['valves'], 'шт', prices['valves']),
            _variant_row('Коллектор', values['collector'], 'шт', prices['collector']),
            _variant_row('Унитаз / инсталляция', values['toilet'], 'шт', prices['toilet']),
            _variant_row('Раковина', values['sink'], 'шт', prices['sink']),
            _variant_row('Смесители', values['mixer'], 'шт', prices['mixer']),
            _variant_row('Ванна / душевая зона', values['shower'], 'шт', prices['shower']),
            _variant_row('Сифоны / выпуск', values['siphon'], 'шт', prices['siphon']),
            _variant_row('Теплоизоляция для труб', values['insulation'], 'м', prices['insulation']),
        ]
        return _variant(key, title, description, materials, extra=extra)

    variants = {
        'economy': plumbing_variant('economy', 'Эконом', 'Базовая разводка: трубы, канализация, простая сантехника и смесители.', {
            'waterPipe': ceil(area * 0.45 + baths * 18 + kitchen_point * 10),
            'sewer50': ceil(baths * 6 + kitchen_point * 5),
            'sewer110': ceil(baths * 3),
            'fittings': ceil(baths * 18 + kitchen_point * 8),
            'valves': ceil(baths * 2 + 2),
            'collector': 0,
            'toilet': baths,
            'sink': baths,
            'mixer': baths + kitchen_point,
            'shower': baths,
            'siphon': baths + kitchen_point,
            'insulation': ceil(area * 0.15),
        }),
        'comfort': plumbing_variant('comfort', 'Комфорт', 'Оптимальная разводка: коллектор, хорошие краны, нормальная сантехника.', {
            'waterPipe': ceil(area * 0.6 + baths * 24 + kitchen_point * 12),
            'sewer50': ceil(baths * 8 + kitchen_point * 6),
            'sewer110': ceil(baths * 4),
            'fittings': ceil(baths * 28 + kitchen_point * 10),
            'valves': ceil(baths * 4 + 3),
            'collector': 1,
            'toilet': baths,
            'sink': baths,
            'mixer': baths + kitchen_point,
            'shower': baths,
            'siphon': baths + kitchen_point,
            'insulation': ceil(area * 0.2),
        }),
        'business': plumbing_variant('business', 'Бизнес', 'Скрытая разводка, качественная сантехника, коллекторы, запас под технику.', {
            'waterPipe': ceil(area * 0.8 + baths * 32 + kitchen_point * 15),
            'sewer50': ceil(baths * 10 + kitchen_point * 8),
            'sewer110': ceil(baths * 5),
            'fittings': ceil(baths * 40 + kitchen_point * 14),
            'valves': ceil(baths * 6 + 4),
            'collector': 2,
            'toilet': baths,
            'sink': baths,
            'mixer': baths + kitchen_point,
            'shower': baths,
            'siphon': baths + kitchen_point,
            'insulation': ceil(area * 0.25),
        }, extra=150000),
    }
    return _build_variant_result(calculator, variants, selected_variant, form_data, area, baths, 1, f"{calculator['title']} · {area:g} м² · {baths} сануз.")


def _calculate_shtukaturka(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    thickness = max(to_float(form_data.get('thickness'), 2), 0)

    wall_area = area * 3
    opening_loss = wall_area * 0.10
    net_area = wall_area - opening_loss

    materials = [
        _row_by_title(calculator, 'Штукатурка 30 кг', ceil(net_area * thickness * 0.30)),
        _row_by_title(calculator, 'Грунтовка 10 кг', max(1, int(net_area / 18))),
        _row_by_title(calculator, 'Бетоноконтакт 15 кг', 1),
        _row_by_title(calculator, 'Маяк железный 3 м', ceil(wall_area * 0.30)),
        _row_by_title(calculator, 'Армировочная сетка 10 м', ceil(net_area / 32.5)),
        _row_by_title(calculator, 'Алюминиевый уголок 90°', 1),
        _row_by_title(calculator, 'Правило 1,5 м', 2),
        _row_by_title(calculator, 'Правило 3 м', 2),
        _row_by_title(calculator, 'Шпатель 15 см', 4),
        _row_by_title(calculator, 'Валик', 2),
        _row_by_title(calculator, 'Ведро строительное', 4),
        _row_by_title(calculator, 'Бумажный малярный скотч', 2),
        _row_by_title(calculator, 'Плёнка защитная', round(net_area * 0.153)),
        _row_by_title(calculator, 'Монтажная пена', 2),
        _row_by_title(calculator, 'Мусорные мешки', 20),
    ]
    plaster_form_data = {
        **form_data,
        '_metrics': [
            {'label': 'Площадь стен', 'value': _round_quantity(wall_area), 'unit': 'м²'},
            {'label': 'Минус окна/двери', 'value': _round_quantity(opening_loss), 'unit': 'м²'},
            {'label': 'Чистая площадь', 'value': _round_quantity(net_area), 'unit': 'м²'},
        ],
        '_price_note': 'Цены ориентировочные',
    }
    return _build_result(calculator, materials, plaster_form_data, area, 1, thickness, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {thickness:g} см")


DRYWALL_CONSTRUCTION_LABELS = {
    'ceiling': 'Потолок из гипсокартона',
    'wall': 'Обшивка стены',
    'partition': 'Перегородка',
}

DRYWALL_PERIMETER_OVERRIDES = {
    (20, 1): 25,
    (40, 1): 43,
    (40, 2): 50,
    (60, 3): 75,
}

DRYWALL_VARIANT_DESCRIPTIONS = {
    'economy': 'Базовый каркас и стандартные материалы.',
    'comfort': 'Усиленный каркас, больше профиля и крепежа.',
    'business': 'Двойной каркас, двухуровневые соединители, шумоизоляция и усиление.',
}

DRYWALL_REFERENCE_MATRIX = {
    'ceiling': {
        (20, 1): {
            'perimeter': 25,
            'totals': {'economy': 97530, 'comfort': 169860, 'business': 300790},
            'materials': [
                ('Гипсокартон потолочный 2 слоя', 16, 'лист', 3900),
                ('Профиль CD усиленный', 36, 'шт', 1450),
                ('Профиль UD усиленный', 11, 'шт', 1200),
                ('Подвес усиленный', 80, 'шт', 180),
                ('Краб усиленный', 28, 'шт', 180),
                ('Соединитель CD профиля', 8, 'шт', 150),
                ('Соединитель двухуровневый CD 60×27', 34, 'шт', 180),
                ('Дюбель-гвоздь', 210, 'шт', 30),
                ('Саморезы ГКЛ', 2, 'пачка', 3000),
                ('Саморезы-клопы', 1, 'пачка', 3000),
            ],
        },
        (40, 1): {
            'perimeter': 43,
            'totals': {'economy': 189140, 'comfort': 328500, 'business': 588540},
            'materials': [
                ('Гипсокартон потолочный 2 слоя', 32, 'лист', 3900),
                ('Профиль CD усиленный', 72, 'шт', 1450),
                ('Профиль UD усиленный', 18, 'шт', 1200),
                ('Подвес усиленный', 160, 'шт', 180),
                ('Краб усиленный', 56, 'шт', 180),
                ('Соединитель CD профиля', 16, 'шт', 150),
                ('Соединитель двухуровневый CD 60×27', 68, 'шт', 180),
                ('Дюбель-гвоздь', 406, 'шт', 30),
                ('Саморезы ГКЛ', 3, 'пачка', 3000),
                ('Саморезы-клопы', 1, 'пачка', 3000),
            ],
        },
        (40, 2): {
            'perimeter': 50,
            'totals': {'economy': 191440, 'comfort': 331320, 'business': 596050},
            'materials': [
                ('Гипсокартон потолочный 2 слоя', 32, 'лист', 3900),
                ('Профиль CD усиленный', 72, 'шт', 1450),
                ('Профиль UD усиленный', 20, 'шт', 1200),
                ('Подвес усиленный', 160, 'шт', 180),
                ('Краб усиленный', 56, 'шт', 180),
                ('Соединитель CD профиля', 16, 'шт', 150),
                ('Соединитель двухуровневый CD 60×27', 68, 'шт', 180),
                ('Дюбель-гвоздь', 420, 'шт', 30),
                ('Саморезы ГКЛ', 3, 'пачка', 3000),
                ('Саморезы-клопы', 1, 'пачка', 3000),
            ],
        },
        (60, 3): {
            'perimeter': 75,
            'totals': {'economy': 277925, 'comfort': 483180, 'business': 871955},
            'materials': [
                ('Гипсокартон потолочный 2 слоя', 44, 'лист', 3900),
                ('Профиль CD усиленный', 108, 'шт', 1450),
                ('Профиль UD усиленный', 29, 'шт', 1200),
                ('Подвес усиленный', 240, 'шт', 180),
                ('Краб усиленный', 84, 'шт', 180),
                ('Соединитель CD профиля', 24, 'шт', 150),
                ('Соединитель двухуровневый CD 60×27', 102, 'шт', 180),
                ('Дюбель-гвоздь', 630, 'шт', 30),
                ('Саморезы ГКЛ', 5, 'пачка', 3000),
                ('Саморезы-клопы', 2, 'пачка', 3000),
            ],
        },
    },
    'wall': {
        (20, 1): {
            'perimeter': 25,
            'totals': {'economy': 82290, 'comfort': 184010, 'business': 281530},
            'materials': [
                ('Гипсокартон стеновой 12.5 мм', 8, 'лист', 4500),
                ('Профиль UW усиленный', 10, 'шт', 1900),
                ('Профиль CW усиленный', 19, 'шт', 2300),
                ('Шумоизоляция Knauf Acoustic', 21, 'м²', 3200),
                ('Демпферная лента', 27, 'м', 350),
                ('Дюбель-гвоздь', 76, 'шт', 35),
                ('Саморезы ГКЛ', 2, 'пачка', 3000),
            ],
        },
        (40, 1): {
            'perimeter': 43,
            'totals': {'economy': 159240, 'comfort': 355750, 'business': 544540},
            'materials': [
                ('Гипсокартон стеновой 12.5 мм', 16, 'лист', 4500),
                ('Профиль UW усиленный', 17, 'шт', 1900),
                ('Профиль CW усиленный', 38, 'шт', 2300),
                ('Шумоизоляция Knauf Acoustic', 42, 'м²', 3200),
                ('Демпферная лента', 46, 'м', 350),
                ('Дюбель-гвоздь', 130, 'шт', 35),
                ('Саморезы ГКЛ', 3, 'пачка', 3000),
            ],
        },
        (40, 2): {
            'perimeter': 50,
            'totals': {'economy': 162950, 'comfort': 362700, 'business': 555070},
            'materials': [
                ('Гипсокартон стеновой 12.5 мм', 16, 'лист', 4500),
                ('Профиль UW усиленный', 19, 'шт', 1900),
                ('Профиль CW усиленный', 38, 'шт', 2300),
                ('Шумоизоляция Knauf Acoustic', 42, 'м²', 3200),
                ('Демпферная лента', 53, 'м', 350),
                ('Дюбель-гвоздь', 150, 'шт', 35),
                ('Саморезы ГКЛ', 3, 'пачка', 3000),
            ],
        },
        (60, 3): {
            'perimeter': 75,
            'totals': {'economy': 231440, 'comfort': 527160, 'business': 798050},
            'materials': [
                ('Гипсокартон стеновой 12.5 мм', 22, 'лист', 4500),
                ('Профиль UW усиленный', 28, 'шт', 1900),
                ('Профиль CW усиленный', 56, 'шт', 2300),
                ('Шумоизоляция Knauf Acoustic', 63, 'м²', 3200),
                ('Демпферная лента', 79, 'м', 350),
                ('Дюбель-гвоздь', 226, 'шт', 35),
                ('Саморезы ГКЛ', 3, 'пачка', 3000),
            ],
        },
    },
    'partition': {
        (20, 1): {
            'perimeter': 25,
            'totals': {'economy': 150520, 'comfort': 304920, 'business': 434500},
            'materials': [
                ('Гипсокартон 2 слоя с одной стороны', 24, 'лист', 4500),
                ('Профиль UW усиленный', 10, 'шт', 2800),
                ('Профиль CW усиленный', 22, 'шт', 3400),
                ('Шумоизоляция Knauf Acoustic', 22, 'м²', 3200),
                ('Демпферная лента', 28, 'м', 350),
                ('Дюбель-гвоздь 8×60', 76, 'шт', 45),
                ('Саморезы ГКЛ', 3, 'пачка', 3500),
            ],
        },
        (40, 1): {
            'perimeter': 43,
            'totals': {'economy': 290120, 'comfort': 594150, 'business': 840050},
            'materials': [
                ('Гипсокартон 2 слоя с одной стороны', 48, 'лист', 4500),
                ('Профиль UW усиленный', 17, 'шт', 2800),
                ('Профиль CW усиленный', 44, 'шт', 3400),
                ('Шумоизоляция Knauf Acoustic', 44, 'м²', 3200),
                ('Демпферная лента', 48, 'м', 350),
                ('Дюбель-гвоздь 8×60', 130, 'шт', 45),
                ('Саморезы ГКЛ', 5, 'пачка', 3500),
            ],
        },
        (40, 2): {
            'perimeter': 50,
            'totals': {'economy': 295600, 'comfort': 603450, 'business': 854150},
            'materials': [
                ('Гипсокартон 2 слоя с одной стороны', 48, 'лист', 4500),
                ('Профиль UW усиленный', 19, 'шт', 2800),
                ('Профиль CW усиленный', 44, 'шт', 3400),
                ('Шумоизоляция Knauf Acoustic', 44, 'м²', 3200),
                ('Демпферная лента', 56, 'м', 350),
                ('Дюбель-гвоздь 8×60', 150, 'шт', 45),
                ('Саморезы ГКЛ', 5, 'пачка', 3500),
            ],
        },
        (60, 3): {
            'perimeter': 75,
            'totals': {'economy': 425120, 'comfort': 871220, 'business': 1231900},
            'materials': [
                ('Гипсокартон 2 слоя с одной стороны', 66, 'лист', 4500),
                ('Профиль UW усиленный', 28, 'шт', 2800),
                ('Профиль CW усиленный', 66, 'шт', 3400),
                ('Шумоизоляция Knauf Acoustic', 66, 'м²', 3200),
                ('Демпферная лента', 83, 'м', 350),
                ('Дюбель-гвоздь 8×60', 226, 'шт', 45),
                ('Саморезы ГКЛ', 6, 'пачка', 3500),
            ],
        },
    },
}

DRYWALL_AREA_DEPENDENT = {
    'Гипсокартон потолочный 2 слоя', 'Профиль CD усиленный', 'Подвес усиленный',
    'Краб усиленный', 'Соединитель CD профиля', 'Соединитель двухуровневый CD 60×27',
    'Гипсокартон стеновой 12.5 мм', 'Профиль CW усиленный', 'Шумоизоляция Knauf Acoustic',
    'Гипсокартон 2 слоя с одной стороны', 'Саморезы ГКЛ', 'Саморезы-клопы'
}
DRYWALL_PERIMETER_DEPENDENT = {'Профиль UD усиленный', 'Профиль UW усиленный', 'Демпферная лента', 'Дюбель-гвоздь', 'Дюбель-гвоздь 8×60'}


def _calculate_gipsokarton(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    construction_type = form_data.get('construction_type', 'ceiling')
    if construction_type not in DRYWALL_REFERENCE_MATRIX:
        construction_type = 'ceiling'
    selected_variant = form_data.get('selected_variant', 'comfort')
    perimeter = _drywall_perimeter(area, rooms)

    reference_key, reference = _drywall_reference(construction_type, area, rooms)
    quantities = _drywall_quantities(reference['materials'], area, perimeter, reference_key, reference['perimeter'])
    comfort_materials = [
        _variant_row(title, quantities[title], unit, price)
        for title, _quantity, unit, price in reference['materials']
    ]
    comfort_total = sum(material['reference_total'] for material in comfort_materials)

    exact_key = (round(area), rooms)
    is_exact_reference = exact_key in DRYWALL_REFERENCE_MATRIX[construction_type]
    area_ratio = area / reference_key[0] if reference_key[0] else 1
    total_ratio = 1 if is_exact_reference else area_ratio
    economy_total = round(reference['totals']['economy'] * total_ratio)
    business_total = round(reference['totals']['business'] * total_ratio)

    variants = {
        'economy': _drywall_variant_from_comfort('economy', 'Эконом', DRYWALL_VARIANT_DESCRIPTIONS['economy'], comfort_materials, economy_total, comfort_total),
        'comfort': _variant('comfort', 'Комфорт', DRYWALL_VARIANT_DESCRIPTIONS['comfort'], comfort_materials),
        'business': _drywall_variant_from_comfort('business', 'Бизнес', DRYWALL_VARIANT_DESCRIPTIONS['business'], comfort_materials, business_total, comfort_total),
    }
    if is_exact_reference:
        variants['comfort']['total'] = reference['totals']['comfort']
        variants['comfort']['reference_total'] = reference['totals']['comfort']

    gipsokarton_form_data = {
        **form_data,
        'construction_type': construction_type,
        '_metrics': [
            {'label': 'Тип конструкции', 'value': DRYWALL_CONSTRUCTION_LABELS[construction_type], 'unit': ''},
            {'label': 'Площадь', 'value': _round_quantity(area), 'unit': 'м²'},
            {'label': 'Количество комнат', 'value': rooms, 'unit': ''},
            {'label': 'Ориентировочный периметр', 'value': perimeter, 'unit': 'м'},
        ],
        '_price_note': 'Цены ориентировочные по Казахстану',
    }
    return _build_variant_result(
        calculator,
        variants,
        selected_variant,
        gipsokarton_form_data,
        area,
        rooms,
        1,
        f"{calculator['title']} · {area:g} м² · {rooms} комн. · {DRYWALL_CONSTRUCTION_LABELS[construction_type]}",
    )


def _drywall_perimeter(area, rooms):
    key = (round(area), rooms)
    return DRYWALL_PERIMETER_OVERRIDES.get(key, round(area * 0.9 + rooms * 7))


def _drywall_reference(construction_type, area, rooms):
    references = DRYWALL_REFERENCE_MATRIX[construction_type]
    key = min(references, key=lambda item: abs(item[0] - area) + abs(item[1] - rooms) * 12)
    return key, references[key]


def _drywall_quantities(reference_materials, area, perimeter, reference_key, reference_perimeter):
    reference_area, _reference_rooms = reference_key
    area_ratio = area / reference_area if reference_area else 1
    perimeter_ratio = perimeter / reference_perimeter if reference_perimeter else 1
    quantities = {}
    for title, quantity, _unit, _price in reference_materials:
        if title in DRYWALL_PERIMETER_DEPENDENT:
            quantities[title] = ceil(quantity * perimeter_ratio)
        elif title in DRYWALL_AREA_DEPENDENT:
            quantities[title] = ceil(quantity * area_ratio)
        else:
            quantities[title] = quantity
    return quantities


def _drywall_variant_from_comfort(key, title, description, comfort_materials, target_total, comfort_total):
    ratio = target_total / comfort_total if comfort_total else 1
    materials = []
    running_total = 0
    for index, material in enumerate(comfort_materials):
        quantity = material['quantity']
        price = round(material['reference_price'] * ratio)
        row_total = round(quantity * price)
        if index == len(comfort_materials) - 1:
            row_total = target_total - running_total
            price = round(row_total / quantity, 2) if quantity else 0
        running_total += row_total
        materials.append({
            'title': material['title'],
            'quantity': quantity,
            'unit': material['unit'],
            'reference_price': price,
            'reference_total': row_total,
            'price': price,
            'total': row_total,
        })
    return _variant(key, title, description, materials)


SELF_LEVEL_REFERENCE_MATRIX = {
    (20, 2): {'total': 95600, 'primer': 10, 'beacons': 29, 'damper': 18, 'staples': 36, 'trash_bags': 10},
    (30, 2): {'total': 134900, 'primer': 15, 'beacons': 43, 'damper': 22, 'staples': 44, 'trash_bags': 10},
    (50, 2): {'total': 211000, 'primer': 25, 'beacons': 72, 'damper': 29, 'staples': 58, 'trash_bags': 10},
    (20, 3): {'total': 130400, 'primer': 10, 'beacons': 29, 'damper': 18, 'staples': 36, 'trash_bags': 10},
    (30, 3): {'total': 187100, 'primer': 15, 'beacons': 43, 'damper': 22, 'staples': 44, 'trash_bags': 10},
    (50, 3): {'total': 298000, 'primer': 25, 'beacons': 72, 'damper': 29, 'staples': 58, 'trash_bags': 10},
    (60, 4): {'total': 460100, 'primer': 30, 'beacons': 86, 'damper': 31, 'staples': 62, 'trash_bags': 10},
}
SELF_LEVEL_AREA_DEPENDENT = {'primer', 'beacons', 'damper', 'staples'}


def _calculate_nalivnoy_pol(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    thickness = max(to_float(form_data.get('thickness'), 2), 0)
    total_consumption = area * thickness * 15
    mixture_bags = ceil(total_consumption / 25) if total_consumption > 0 else 0
    reference_key, reference = _self_level_reference(area, thickness)
    is_exact_reference = reference_key in SELF_LEVEL_REFERENCE_MATRIX and area == reference_key[0] and thickness == reference_key[1]
    area_ratio = area / reference_key[0] if reference_key[0] else 1
    quantities = _self_level_quantities(reference, area_ratio)
    quantities['mixture_bags'] = mixture_bags
    needle_title = 'Игольчатый валик 30-40 мм' if thickness <= 2 else 'Игольчатый валик 40-50 мм'

    materials = [
        _self_level_row(calculator, 'Наливной пол 25 кг', quantities['mixture_bags']),
        _self_level_row(calculator, 'Грунтовка 10 кг', quantities['primer']),
        _self_level_row(calculator, 'Маяк фиксатор', quantities['beacons']),
        _self_level_row(calculator, 'Демпферная лента', quantities['damper']),
        _self_level_row(calculator, 'Ведро строительное', 4),
        _self_level_row(calculator, 'Валик', 1),
        _self_level_row(calculator, needle_title, 1),
        _self_level_row(calculator, 'Обувь шиповая', 1),
        _self_level_row(calculator, 'Степлер', 1),
        _self_level_row(calculator, 'Скобы', quantities['staples']),
        _self_level_row(calculator, 'Мусорные мешки', quantities['trash_bags']),
    ]
    if is_exact_reference:
        _adjust_self_level_total(materials, reference['total'])

    self_level_form_data = {
        **form_data,
        '_metrics': [
            {'label': 'Площадь пола', 'value': _round_quantity(area), 'unit': 'м²'},
            {'label': 'Толщина', 'value': _round_quantity(thickness), 'unit': 'см'},
            {'label': 'Общий расход смеси', 'value': _round_quantity(total_consumption), 'unit': 'кг'},
        ],
        '_price_note': 'Цены ориентировочные',
    }
    return _build_result(
        calculator,
        materials,
        self_level_form_data,
        area,
        1,
        thickness,
        'comfort',
        _plain_segment(),
        f"{calculator['title']} · {area:g} м² · {thickness:g} см",
    )


def _self_level_reference(area, thickness):
    key = min(SELF_LEVEL_REFERENCE_MATRIX, key=lambda item: abs(item[0] - area) + abs(item[1] - thickness) * 20)
    return key, SELF_LEVEL_REFERENCE_MATRIX[key]


def _self_level_quantities(reference, area_ratio):
    quantities = {}
    for key, value in reference.items():
        if key == 'total':
            continue
        if key in SELF_LEVEL_AREA_DEPENDENT:
            quantities[key] = ceil(value * area_ratio)
        else:
            quantities[key] = value
    return quantities


def _self_level_row(calculator, title, quantity):
    material = next(item for item in calculator['materials'] if item['title'] == title)
    return {'title': material['title'], 'quantity': quantity, 'unit': material['unit'], 'reference_price': material['reference_price']}


def _adjust_self_level_total(materials, target_total):
    current_total = sum(round(material['quantity'] * material['reference_price']) for material in materials)
    delta = target_total - current_total
    if delta == 0:
        return
    adjustable = next((material for material in materials if material['title'] == 'Валик' and material['quantity'] == 1), materials[-1])
    adjustable['reference_price'] = round(adjustable['reference_price'] + delta)


TILE_ZONE_LABELS = {
    'floor': 'Пол',
    'walls': 'Стены',
    'bathroom': 'Санузел полностью',
    'backsplash': 'Кухонный фартук',
}

TILE_FORMAT_LABELS = {
    '60x60': '60×60',
    'large': '120×60 / крупный формат',
}

TILE_VARIANT_DESCRIPTIONS = {
    'economy': 'Плитка от 7000 ₸/м², эконом-клей, обычная фуга, СВП.',
    'comfort': 'Керамогранит, усиленный клей, улучшенная фуга, СВП.',
    'business': 'Премиальный керамогранит, дорогой клей, эпоксидная фуга, усиленная СВП.',
}

TILE_REFERENCE_MATRIX = {
    (20, 'floor', '60x60'): {
        'totals': {'economy': 189600, 'comfort': 324900, 'business': 718500},
        'materials': [
            ('Плитка комфорт', 23, 'м²', 12000),
            ('Грунтовка', 5, 'кг', 500),
            ('Усиленный плиточный клей', 4, 'меш', 4500),
            ('Фуга улучшенная', 8, 'кг', 1800),
            ('СВП', 700, 'шт', 20),
        ],
    },
    (20, 'walls', '60x60'): {
        'totals': {'economy': 189600, 'comfort': 324900, 'business': 718500},
        'materials': [
            ('Плитка комфорт', 23, 'м²', 12000),
            ('Грунтовка', 5, 'кг', 500),
            ('Усиленный плиточный клей', 4, 'меш', 4500),
            ('Фуга улучшенная', 8, 'кг', 1800),
            ('СВП', 700, 'шт', 20),
        ],
    },
    (20, 'bathroom', '60x60'): {
        'totals': {'economy': 227800, 'comfort': 368100, 'business': 807300},
        'materials': [
            ('Плитка комфорт', 23, 'м²', 12000),
            ('Грунтовка', 5, 'кг', 500),
            ('Гидроизоляция эластичная 2 слоя', 24, 'кг', 1800),
            ('Усиленный плиточный клей', 4, 'меш', 4500),
            ('Фуга улучшенная', 8, 'кг', 1800),
            ('СВП', 700, 'шт', 20),
        ],
    },
    (20, 'backsplash', '60x60'): {
        'totals': {'economy': 196600, 'comfort': 324900, 'business': 718500},
        'materials': [
            ('Плитка комфорт', 23, 'м²', 12000),
            ('Грунтовка', 5, 'кг', 500),
            ('Усиленный плиточный клей', 4, 'меш', 4500),
            ('Фуга улучшенная', 8, 'кг', 1800),
            ('СВП', 700, 'шт', 20),
        ],
    },
    (20, 'backsplash', 'large'): {
        'totals': {'economy': 203600, 'comfort': 341400, 'business': 759500},
        'materials': [
            ('Плитка комфорт', 24, 'м²', 12000),
            ('Грунтовка', 5, 'кг', 500),
            ('Усиленный плиточный клей', 5, 'меш', 4500),
            ('Фуга улучшенная', 8, 'кг', 1800),
            ('СВП', 700, 'шт', 20),
        ],
    },
    (50, 'floor', '60x60'): {
        'totals': {'economy': 476200, 'comfort': 802000, 'business': 1808600},
        'materials': [
            ('Плитка комфорт', 57, 'м²', 12000),
            ('Грунтовка', 13, 'кг', 500),
            ('Усиленный плиточный клей', 9, 'меш', 4500),
            ('Фуга улучшенная', 20, 'кг', 1800),
            ('СВП', 1750, 'шт', 20),
        ],
    },
    (50, 'walls', 'large'): {
        'totals': {'economy': 488200, 'comfort': 823000, 'business': 1858100},
        'materials': [
            ('Плитка комфорт', 58, 'м²', 12000),
            ('Грунтовка', 13, 'кг', 500),
            ('Усиленный плиточный клей', 11, 'меш', 4500),
            ('Фуга улучшенная', 20, 'кг', 1800),
            ('СВП', 1750, 'шт', 20),
        ],
    },
}


def _calculate_plitka(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    zone = form_data.get('zone') or form_data.get('zone_type', 'floor')
    tile_format = form_data.get('tile_format', '60x60')
    tile_format = {'120x120': 'large', '120x60': 'large'}.get(tile_format, tile_format)
    if zone not in TILE_ZONE_LABELS:
        zone = 'floor'
    if tile_format not in TILE_FORMAT_LABELS:
        tile_format = '60x60'
    selected_variant = form_data.get('selected_variant', 'comfort')

    reference_key, reference = _tile_reference(area, zone, tile_format)
    area_ratio = area / reference_key[0] if reference_key[0] else 1
    exact_key = (round(area), zone, tile_format)
    is_exact_reference = exact_key in TILE_REFERENCE_MATRIX
    comfort_materials = _tile_comfort_materials(reference['materials'], area_ratio, is_exact_reference)
    comfort_total = sum(material['reference_total'] for material in comfort_materials)
    total_ratio = 1 if is_exact_reference else area_ratio
    economy_total = round(reference['totals']['economy'] * total_ratio)
    business_total = round(reference['totals']['business'] * total_ratio)

    variants = {
        'economy': _drywall_variant_from_comfort('economy', 'Эконом', TILE_VARIANT_DESCRIPTIONS['economy'], comfort_materials, economy_total, comfort_total),
        'comfort': _variant('comfort', 'Комфорт', TILE_VARIANT_DESCRIPTIONS['comfort'], comfort_materials),
        'business': _drywall_variant_from_comfort('business', 'Бизнес', TILE_VARIANT_DESCRIPTIONS['business'], comfort_materials, business_total, comfort_total),
    }
    if is_exact_reference:
        variants['comfort']['total'] = reference['totals']['comfort']
        variants['comfort']['reference_total'] = reference['totals']['comfort']

    tile_form_data = {
        **form_data,
        'zone': zone,
        'tile_format': tile_format,
        '_metrics': [
            {'label': 'Зона', 'value': TILE_ZONE_LABELS[zone], 'unit': ''},
            {'label': 'Формат плитки', 'value': TILE_FORMAT_LABELS[tile_format], 'unit': ''},
            {'label': 'Площадь укладки', 'value': _round_quantity(area), 'unit': 'м²'},
            {'label': 'Грунтовка', 'value': '250 г/м² на 1 слой', 'unit': ''},
            {'label': 'Клей', 'value': '5–6.5 кг/м²' if tile_format == 'large' else '4–5 кг/м²', 'unit': ''},
        ],
        '_price_note': 'Цены ориентировочные',
    }
    return _build_variant_result(
        calculator,
        variants,
        selected_variant,
        tile_form_data,
        area,
        1,
        1,
        f"{calculator['title']} · {TILE_ZONE_LABELS[zone]} · {TILE_FORMAT_LABELS[tile_format]} · {area:g} м²",
    )


def _tile_reference(area, zone, tile_format):
    key = min(
        TILE_REFERENCE_MATRIX,
        key=lambda item: abs(item[0] - area) + (0 if item[1] == zone else 100) + (0 if item[2] == tile_format else 50),
    )
    return key, TILE_REFERENCE_MATRIX[key]


def _tile_comfort_materials(reference_materials, area_ratio, exact):
    materials = []
    for title, quantity, unit, price in reference_materials:
        scaled_quantity = quantity if exact else ceil(quantity * area_ratio)
        materials.append(_variant_row(title, scaled_quantity, unit, price))
    return materials


def _calculate_laminat_spc_parket(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    covering_type = form_data.get('covering_type') or form_data.get('type', 'laminate')
    if covering_type not in FLOORING_COVERING_LABELS:
        covering_type = 'laminate'

    direct_area = ceil(area * 1.05)
    diagonal_area = ceil(area * 1.12)
    herringbone_area = ceil(area * 1.18)
    plinth = FLOORING_PLINTH_OVERRIDES.get(round(area), round(area * 0.5 + 9))
    trash_bags = ceil(area / 5)

    materials = _flooring_materials(covering_type, direct_area, plinth, trash_bags)
    reference_total = _flooring_reference_total(covering_type, area)
    result = _build_flooring_result(
        calculator,
        materials,
        {
            **form_data,
            'covering_type': covering_type,
            '_metrics': [
                {'label': 'Прямая укладка (+5%)', 'value': direct_area, 'unit': 'м²'},
                {'label': 'Диагональная укладка (+12%)', 'value': diagonal_area, 'unit': 'м²'},
                {'label': 'Ёлочка (+18%)', 'value': herringbone_area, 'unit': 'м²'},
            ],
            '_price_note': 'Цены ориентировочные',
        },
        area,
        f"{calculator['title']} · {FLOORING_COVERING_LABELS[covering_type]} · {area:g} м²",
        FLOORING_WARNINGS[covering_type],
        reference_total,
    )
    return result


FLOORING_COVERING_LABELS = {
    'laminate': 'Ламинат',
    'spc': 'SPC покрытие',
    'parquet': 'Паркет / инженерная доска',
}

FLOORING_WARNINGS = {
    'laminate': 'Для ламината обычно берут запас 5–12%. При диагональной укладке и сложной планировке запас лучше увеличить.',
    'spc': 'SPC требует ровного основания. Если основание неровное, перед укладкой лучше сделать подготовку пола.',
    'parquet': 'Для инженерной доски средний расход клея 1,2–1,3 кг/м². Грунтовка считается 250 г/м² на 1 слой.',
}

FLOORING_PLINTH_OVERRIDES = {
    20: 19,
    40: 28,
    60: 33,
    70: 36,
}

FLOORING_REFERENCE_TOTALS = {
    'laminate': {20: 123900, 40: 232800, 60: 338100, 70: 393600},
    'spc': {20: 166300, 40: 313600, 70: 531200},
    'parquet': {20: 371300, 40: 727600, 70: 1261000},
}


def _flooring_reference_total(covering_type, area):
    references = FLOORING_REFERENCE_TOTALS[covering_type]
    rounded_area = round(area)
    if rounded_area in references:
        return references[rounded_area]
    reference_area = min(references, key=lambda item: abs(item - area))
    return round(references[reference_area] * area / reference_area) if reference_area else 0


def _flooring_materials(covering_type, direct_area, plinth, trash_bags):
    common_tail = [
        _variant_row('Плинтус', plinth, 'м', 1200),
        _variant_row('Уголки/соединители/заглушки', 1, 'комплект', 5000),
        _variant_row('Порог', 2, 'шт', 2500),
        _variant_row('Мусорные мешки', trash_bags, 'шт', 500),
    ]
    if covering_type == 'spc':
        return [
            _variant_row('SPC покрытие', direct_area, 'м²', 6500),
            _variant_row('Подложка, если требуется', direct_area, 'м²', 700),
            *common_tail,
        ]
    if covering_type == 'parquet':
        return [
            _variant_row('Паркет / инженерная доска', direct_area, 'м²', 14500),
            _variant_row('Клей для паркета', ceil(direct_area * 1.23), 'кг', 2500),
            _variant_row('Грунтовка', ceil(direct_area * 0.24), 'кг', 1200),
            *common_tail,
        ]
    return [
        _variant_row('Ламинат', direct_area, 'м²', 4500),
        _variant_row('Подложка', direct_area, 'м²', 700),
        *common_tail,
    ]


def _build_flooring_result(calculator, materials, form_data, area, summary, warning, exact_total=None):
    reference_total = exact_total if exact_total is not None else sum(material['reference_total'] for material in materials)
    saved_list = '\n'.join(
        f"{index}. {material['title']} — {material['quantity']} {material['unit']}"
        for index, material in enumerate(materials, start=1)
        if material['quantity'] > 0
    )
    return {
        'materials': materials,
        'materials_count': len(materials),
        'reference_total': reference_total,
        'reference_labor_total': 0,
        'reference_grand_total': reference_total,
        'materials_total': reference_total,
        'labor_total': 0,
        'grand_total': reference_total,
        'segment_label': 'Предварительно',
        'summary': summary,
        'saved_list': saved_list,
        'whatsapp_text': f"ESEPTEP.KZ\n{summary}\n\n{saved_list}\n\nСписок составлен через ESEPTEP.KZ",
        'copy_text': f"ESEPTEP.KZ\n{summary}\n\n{saved_list}\n\nСписок составлен через ESEPTEP.KZ",
        'warning': warning,
        'master_template_items': calculator.get('master_template_items', []),
        'metrics': form_data.get('_metrics', []),
        'price_note': form_data.get('_price_note', 'Цены ориентировочные'),
        'meta': {
            'area': area,
            'thickness': 1,
            'rooms': 1,
            'segment': 'comfort',
            'input': dict(form_data),
        },
    }


PAINTING_TYPE_LABELS = {
    'wallpaper': 'Малярка под обои',
    'paint': 'Малярка под покраску',
}

PAINTING_VARIANT_DESCRIPTIONS = {
    'economy': 'Минимальный набор материалов для базовой подготовки стен.',
    'comfort': 'Оптимальная комплектация под выбранный тип малярки.',
    'business': 'Расширенный запас материалов и более дорогой уровень отделки.',
}

PAINTING_VARIANT_QUANTITY_COEFFICIENTS = {
    'economy': 0.72,
    'comfort': 1.0,
    'business': 1.25,
}

PAINTING_REFERENCE_MATRIX = {
    'wallpaper': {
        10: {
            'totals': {'economy': 32150, 'comfort': 69000, 'business': 148000},
            'comfort_materials': [
                ('Грунтовка 1 слой', 1, 'шт', 400),
                ('Базовая шпаклёвка 2 слоя', 4, 'мешок', 3500),
                ('Шкурка / сетка P100/P120', 2, 'шт', 300),
                ('Обойный клей Metylan / аналог', 2, 'пачка', 3000),
                ('Обои комфорт-класс', 4, 'рулон', 12000),
            ],
        },
        30: {
            'totals': {'economy': 96450, 'comfort': 182700, 'business': 381100},
            'comfort_materials': [
                ('Грунтовка 1 слой', 1, 'шт', 400),
                ('Базовая шпаклёвка 2 слоя', 4, 'мешок', 3500),
                ('Шкурка / сетка P100/P120', 1, 'шт', 300),
                ('Обойный клей Metylan / аналог', 4, 'пачка', 3000),
                ('Обои комфорт-класс', 13, 'рулон', 12000),
            ],
        },
        50: {
            'totals': {'economy': 155500, 'comfort': 289200, 'business': 613300},
            'comfort_materials': [
                ('Грунтовка 1 слой', 2, 'шт', 400),
                ('Базовая шпаклёвка 2 слоя', 5, 'мешок', 3500),
                ('Шкурка / сетка P100/P120', 3, 'шт', 300),
                ('Обойный клей Metylan / аналог', 2, 'пачка', 3000),
                ('Обои комфорт-класс', 22, 'рулон', 12000),
            ],
        },
    },
    'paint': {
        30: {
            'totals': {'economy': 89950, 'comfort': 134200, 'business': 430750},
            'comfort_materials': [
                ('Грунтовка 1 слой', 2, 'шт', 400),
                ('Базовая шпаклёвка 2 слоя', 8, 'мешок', 3500),
                ('Финишная полимерная шпаклёвка 2 слоя', 5, 'мешок', 5000),
                ('Шкурка / сетка P120/P180', 4, 'шт', 300),
                ('Краска среднего сегмента 2 слоя', 36, 'л', 2200),
            ],
        },
        50: {
            'totals': {'economy': 147850, 'comfort': 218000, 'business': 707800},
            'comfort_materials': [
                ('Грунтовка 1 слой', 2, 'шт', 400),
                ('Базовая шпаклёвка 2 слоя', 14, 'мешок', 3500),
                ('Финишная полимерная шпаклёвка 2 слоя', 8, 'мешок', 5000),
                ('Шкурка / сетка P120/P180', 2, 'шт', 300),
                ('Краска среднего сегмента 2 слоя', 58, 'л', 2200),
            ],
        },
    },
}


def _calculate_malyarka(calculator, form_data):
    floor_area = to_float(form_data.get('floor_area'), 0)
    finish_type = form_data.get('type', 'paint')
    if finish_type not in PAINTING_REFERENCE_MATRIX:
        finish_type = 'paint'
    selected_variant = form_data.get('selected_variant', 'comfort')

    wall_area_before = floor_area * 3
    opening_loss = wall_area_before * 0.10
    wall_area = wall_area_before * 0.9
    reference_area, reference = _painting_reference(finish_type, floor_area)
    area_ratio = floor_area / reference_area if reference_area else 1
    is_exact_reference = round(floor_area) in PAINTING_REFERENCE_MATRIX[finish_type]

    variants = {}
    for key, title in (('economy', 'Эконом'), ('comfort', 'Комфорт'), ('business', 'Бизнес')):
        coefficient = PAINTING_VARIANT_QUANTITY_COEFFICIENTS[key]
        target_total = reference['totals'][key] if is_exact_reference else round(reference['totals'][key] * area_ratio)
        materials = _painting_materials(reference['comfort_materials'], area_ratio, coefficient, target_total)
        variants[key] = _variant(key, title, PAINTING_VARIANT_DESCRIPTIONS[key], materials)

    painting_form_data = {
        **form_data,
        'type': finish_type,
        '_metrics': [
            {'label': 'Тип', 'value': PAINTING_TYPE_LABELS[finish_type], 'unit': ''},
            {'label': 'Площадь пола', 'value': _round_quantity(floor_area), 'unit': 'м²'},
            {'label': 'Площадь стен до вычета', 'value': _round_quantity(wall_area_before), 'unit': 'м²'},
            {'label': 'Минус окна и двери', 'value': _round_quantity(opening_loss), 'unit': 'м²'},
            {'label': 'Расчётная площадь стен', 'value': _round_quantity(wall_area), 'unit': 'м²'},
        ],
        '_price_note': 'Цены ориентировочные',
    }
    return _build_variant_result(
        calculator,
        variants,
        selected_variant,
        painting_form_data,
        floor_area,
        1,
        1,
        f"{calculator['title']} · {PAINTING_TYPE_LABELS[finish_type]} · стены {wall_area:g} м²",
    )


def _painting_reference(finish_type, floor_area):
    references = PAINTING_REFERENCE_MATRIX[finish_type]
    reference_area = min(references, key=lambda area: abs(area - floor_area))
    return reference_area, references[reference_area]


def _painting_materials(reference_materials, area_ratio, variant_coefficient, target_total):
    materials = []
    for title, quantity, unit, price in reference_materials:
        scaled_quantity = max(1, ceil(quantity * area_ratio * variant_coefficient))
        materials.append(_variant_row(title, scaled_quantity, unit, price))
    _adjust_variant_rows_total(materials, target_total)
    return materials


def _adjust_variant_rows_total(materials, target_total):
    current_total = sum(material['reference_total'] for material in materials)
    delta = target_total - current_total
    if delta == 0 or not materials:
        return
    adjustable = next((material for material in materials if material['quantity'] == 1), materials[0])
    adjustable['reference_total'] += delta
    adjustable['total'] = adjustable['reference_total']
    adjustable['reference_price'] = round(adjustable['reference_total'] / adjustable['quantity'], 2) if adjustable['quantity'] else 0
    adjustable['price'] = adjustable['reference_price']


CEILING_REFERENCE_TOTALS = {
    (20, 2): {'economy': 53700, 'comfort': 124200, 'business': 480700},
    (20, 3): {'economy': 58200, 'comfort': 130200, 'business': 480700},
    (40, 2): {'economy': 102600, 'comfort': 228400, 'business': 941200},
    (40, 3): {'economy': 102600, 'comfort': 234400, 'business': 941200},
    (60, 2): {'economy': 151800, 'comfort': 340600, 'business': 1390900},
    (60, 3): {'economy': 151800, 'comfort': 346600, 'business': 1390900},
    (60, 4): {'economy': 151800, 'comfort': 352600, 'business': 1390900},
    (90, 4): {'economy': 227700, 'comfort': 516900, 'business': 2100500},
}

CEILING_VARIANT_DESCRIPTIONS = {
    'economy': 'Обычный матовый потолок, ПВХ багет, базовые светильники.',
    'comfort': 'Полотно лучше, алюминиевый профиль, больше света, скрытый карниз.',
    'business': 'Теневой / парящий потолок, световые линии, магнитные треки.',
}

CEILING_VARIANT_QUANTITY_COEFFICIENTS = {
    'economy': 0.82,
    'comfort': 1.0,
    'business': 1.28,
}


def _calculate_natyazhnoy_potolok(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    selected_variant = form_data.get('selected_variant', 'comfort')

    perimeter = round(area * 1.35)
    profile = ceil(perimeter * 1.06)
    lights = ceil(area / 8) if area > 0 else 0
    cable = lights * 5
    comfort_materials = [
        _variant_row('ПВХ полотно MSD / аналог', area, 'м²', 3500),
        _variant_row('Алюминиевый профиль', profile, 'м', 400),
        _variant_row('Теневая / декоративная вставка', profile, 'м', 300),
        _variant_row('Термокольца под свет', lights, 'шт', 400),
        _variant_row('Платформы под светильники', lights, 'шт', 900),
        _variant_row('Точечные светильники комфорт', lights, 'шт', 4500),
        _variant_row('Кабель для освещения', cable, 'м', 300),
        _variant_row('Скрытый карниз / ниша', rooms, 'шт', 6000),
    ]
    reference_key, reference_totals = _ceiling_reference(area, rooms)
    exact_key = (round(area), rooms)
    is_exact_reference = exact_key in CEILING_REFERENCE_TOTALS
    area_ratio = area / reference_key[0] if reference_key[0] else 1
    economy_total = reference_totals['economy'] if is_exact_reference else round(reference_totals['economy'] * area_ratio)
    business_total = reference_totals['business'] if is_exact_reference else round(reference_totals['business'] * area_ratio)

    variants = {
        'economy': _ceiling_variant_from_comfort('economy', 'Эконом', comfort_materials, economy_total),
        'comfort': _variant('comfort', 'Комфорт', CEILING_VARIANT_DESCRIPTIONS['comfort'], comfort_materials),
        'business': _ceiling_variant_from_comfort('business', 'Бизнес', comfort_materials, business_total),
    }
    if is_exact_reference:
        variants['comfort']['total'] = reference_totals['comfort']
        variants['comfort']['reference_total'] = reference_totals['comfort']

    ceiling_form_data = {
        **form_data,
        '_metrics': [
            {'label': 'Площадь потолка', 'value': _round_quantity(area), 'unit': 'м²'},
            {'label': 'Количество комнат', 'value': rooms, 'unit': ''},
            {'label': 'Ориентировочный периметр', 'value': perimeter, 'unit': 'м'},
            {'label': 'Профиль с запасом', 'value': profile, 'unit': 'м'},
        ],
        '_price_note': 'Цены ориентировочные, только материалы',
    }
    return _build_variant_result(
        calculator,
        variants,
        selected_variant,
        ceiling_form_data,
        area,
        rooms,
        1,
        f"{calculator['title']} · {area:g} м² · {rooms} комн.",
    )


def _ceiling_reference(area, rooms):
    key = min(CEILING_REFERENCE_TOTALS, key=lambda item: abs(item[0] - area) + abs(item[1] - rooms) * 8)
    return key, CEILING_REFERENCE_TOTALS[key]


def _ceiling_variant_from_comfort(key, title, comfort_materials, target_total):
    coefficient = CEILING_VARIANT_QUANTITY_COEFFICIENTS[key]
    materials = [
        _variant_row(material['title'], max(1, ceil(material['quantity'] * coefficient)), material['unit'], material['reference_price'])
        for material in comfort_materials
    ]
    _adjust_variant_rows_total(materials, target_total)
    return _variant(key, title, CEILING_VARIANT_DESCRIPTIONS[key], materials)


def _calculate_dveri(calculator, form_data):
    count = max(1, int(to_float(form_data.get('count'), 1)))
    materials = [
        _row_by_title(calculator, 'Дверное полотно', count),
        _row_by_title(calculator, 'Коробка дверная', count),
        _row_by_title(calculator, 'Доборы', count),
        _row_by_title(calculator, 'Наличники', count),
        _row_by_title(calculator, 'Ручки', count),
        _row_by_title(calculator, 'Замок / защёлка', count),
        _row_by_title(calculator, 'Магнитный замок', count),
        _row_by_title(calculator, 'Петли', count),
        _row_by_title(calculator, 'Скрытые петли', count),
        _row_by_title(calculator, 'Уплотнитель', count),
        _row_by_title(calculator, 'Стопор дверной', count),
        _row_by_title(calculator, 'Пена монтажная', max(1, count)),
        _row_by_title(calculator, 'Силикон / герметик', max(1, count)),
    ]
    return _build_result(
        calculator,
        materials,
        form_data,
        count,
        count,
        1,
        'comfort',
        _plain_segment(),
        f"{calculator['title']} · {count} шт",
    )


WARM_FLOOR_TYPE_LABELS = {
    'electric_mat': 'Электрический мат',
    'electric_cable': 'Кабельный тёплый пол',
    'water': 'Водяной тёплый пол',
}

WARM_FLOOR_REFERENCE_TOTALS = {
    'electric_mat': {
        20: {'economy': 161300, 'comfort': 247050, 'business': 441250},
        40: {'economy': 307100, 'comfort': 464600, 'business': 810500},
        70: {'economy': 529340, 'comfort': 796200, 'business': 1373300},
    },
    'electric_cable': {
        20: {'economy': 146800, 'comfort': 241050, 'business': 422250},
        40: {'economy': 278100, 'comfort': 452600, 'business': 772500},
        70: {'economy': 475590, 'comfort': 770950, 'business': 1299800},
    },
    'water': {
        20: {'economy': 128880, 'comfort': 288400, 'business': 561100},
        40: {'economy': 187760, 'comfort': 411800, 'business': 772200},
        70: {'economy': 276530, 'comfort': 597800, 'business': 1090600},
    },
}

WARM_FLOOR_VARIANT_DESCRIPTIONS = {
    'economy': 'Базовые материалы и простая комплектация.',
    'comfort': 'Оптимальные материалы, надёжнее и удобнее в эксплуатации.',
    'business': 'Премиальные материалы, Wi-Fi/автоматика или усиленная водяная система.',
}

WARM_FLOOR_VARIANT_QUANTITY_COEFFICIENTS = {
    'economy': 0.78,
    'comfort': 1.0,
    'business': 1.22,
}


def _calculate_teplyy_pol(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    floor_type = form_data.get('type', 'electric_mat')
    floor_type = {'mat': 'electric_mat', 'cable': 'electric_cable'}.get(floor_type, floor_type)
    if floor_type not in WARM_FLOOR_TYPE_LABELS:
        floor_type = 'electric_mat'
    selected_variant = form_data.get('selected_variant', 'comfort')
    reserve_area = ceil(area * 1.05)
    contours = ceil(area / 15) if area > 0 else 0

    comfort_materials = _warm_floor_comfort_materials(floor_type, area, reserve_area, contours)
    reference_area, reference_totals = _warm_floor_reference(floor_type, area)
    exact_area = round(area)
    is_exact_reference = exact_area in WARM_FLOOR_REFERENCE_TOTALS[floor_type]
    area_ratio = area / reference_area if reference_area else 1
    economy_total = reference_totals['economy'] if is_exact_reference else round(reference_totals['economy'] * area_ratio)
    business_total = reference_totals['business'] if is_exact_reference else round(reference_totals['business'] * area_ratio)

    variants = {
        'economy': _warm_floor_variant_from_comfort('economy', 'Эконом', comfort_materials, economy_total),
        'comfort': _variant('comfort', 'Комфорт', WARM_FLOOR_VARIANT_DESCRIPTIONS['comfort'], comfort_materials),
        'business': _warm_floor_variant_from_comfort('business', 'Бизнес', comfort_materials, business_total),
    }
    if is_exact_reference:
        variants['comfort']['total'] = reference_totals['comfort']
        variants['comfort']['reference_total'] = reference_totals['comfort']

    metrics = [
        {'label': 'Тип системы', 'value': WARM_FLOOR_TYPE_LABELS[floor_type], 'unit': ''},
        {'label': 'Площадь', 'value': _round_quantity(area), 'unit': 'м²'},
        {'label': 'Площадь с запасом', 'value': reserve_area, 'unit': 'м²'},
    ]
    if floor_type == 'water':
        metrics.append({'label': 'Контуры', 'value': contours, 'unit': 'шт'})

    warm_floor_form_data = {
        **form_data,
        'type': floor_type,
        '_metrics': metrics,
        '_price_note': 'Цены ориентировочные по Казахстану, только материалы',
    }
    return _build_variant_result(
        calculator,
        variants,
        selected_variant,
        warm_floor_form_data,
        area,
        1,
        1,
        f"{calculator['title']} · {WARM_FLOOR_TYPE_LABELS[floor_type]} · {area:g} м²",
    )


def _warm_floor_comfort_materials(floor_type, area, reserve_area, contours):
    if floor_type == 'electric_cable':
        return [
            _variant_row('Нагревательный кабель комфорт', area * 9, 'м', 900),
            _variant_row('Монтажная лента усиленная', ceil(area * 1.5), 'м', 350),
            _variant_row('Терморегулятор сенсорный', 1, 'шт', 25000),
            _variant_row('Датчик температуры пола', 1, 'шт', 4500),
            _variant_row('Гофра под датчик', ceil(area / 4), 'м', 250),
            _variant_row('Теплоизоляция плотная', reserve_area, 'м²', 1800),
        ]
    if floor_type == 'water':
        return [
            _variant_row('Труба PE-RT / PEX 16 мм с кислородным барьером', area * 6, 'м', 650),
            _variant_row('Маты / теплоизоляция плотная', reserve_area, 'м²', 1800),
            _variant_row('Демпферная лента', ceil(area * 0.8), 'м', 250),
            _variant_row('Скобы / крепёж трубы', area * 4, 'шт', 45),
            _variant_row('Коллектор с расходомерами', 1, 'компл.', 85000),
            _variant_row('Коллекторный шкаф', 1, 'шт', 35000),
            _variant_row('Фитинги и соединители', 1, 'компл.', 45000),
        ]
    return [
        _variant_row('Нагревательный мат комфорт', reserve_area, 'м²', 8500),
        _variant_row('Терморегулятор сенсорный', 1, 'шт', 25000),
        _variant_row('Датчик температуры пола', 1, 'шт', 4500),
        _variant_row('Гофра под датчик', ceil(area / 4), 'м', 250),
        _variant_row('Теплоизоляция плотная', reserve_area, 'м²', 1800),
    ]


def _warm_floor_reference(floor_type, area):
    references = WARM_FLOOR_REFERENCE_TOTALS[floor_type]
    reference_area = min(references, key=lambda item: abs(item - area))
    return reference_area, references[reference_area]


def _warm_floor_variant_from_comfort(key, title, comfort_materials, target_total):
    coefficient = WARM_FLOOR_VARIANT_QUANTITY_COEFFICIENTS[key]
    materials = [
        _variant_row(material['title'], max(1, ceil(material['quantity'] * coefficient)), material['unit'], material['reference_price'])
        for material in comfort_materials
    ]
    _adjust_variant_rows_total(materials, target_total)
    return _variant(key, title, WARM_FLOOR_VARIANT_DESCRIPTIONS[key], materials)



def _variant_row(title, quantity, unit, reference_price):
    quantity = _round_quantity(quantity)
    reference_total = round(quantity * reference_price)
    return {
        'title': title,
        'quantity': quantity,
        'unit': unit,
        'reference_price': reference_price,
        'reference_total': reference_total,
        'price': reference_price,
        'total': reference_total,
    }


def _variant(key, title, description, materials, extra=0):
    materials = [material for material in materials if material['quantity'] > 0]
    extra_total = round(extra)
    total = sum(material['reference_total'] for material in materials) + extra_total
    return {
        'key': key,
        'title': title,
        'label': title,
        'description': description,
        'materials': materials,
        'materials_count': len(materials),
        'total': total,
        'reference_total': total,
        'extra': extra_total,
    }


def _build_variant_result(calculator, variants_by_key, selected_key, form_data, area, rooms, thickness, summary):
    if selected_key not in variants_by_key:
        selected_key = 'comfort' if 'comfort' in variants_by_key else 'optimal' if 'optimal' in variants_by_key else next(iter(variants_by_key))
    selected = variants_by_key[selected_key]
    ordered_variants = [variants_by_key[key] for key in ('base', 'optimal', 'maximum', 'economy', 'comfort', 'business') if key in variants_by_key]
    materials = selected['materials']
    saved_list = '\n'.join(
        f"{index}. {material['title']} — {material['quantity']} {material['unit']}"
        for index, material in enumerate(materials, start=1)
        if material['quantity'] > 0
    )
    copy_text = f"ESEPTEP.KZ\n{calculator['title']} — {selected['title']}\n\n{saved_list}\n\nСписок составлен через ESEPTEP.KZ"
    return {
        'materials': materials,
        'materials_count': len(materials),
        'reference_total': selected['total'],
        'reference_labor_total': 0,
        'reference_grand_total': selected['total'],
        'materials_total': selected['total'],
        'labor_total': 0,
        'grand_total': selected['total'],
        'segment_label': 'Предварительно',
        'summary': summary,
        'saved_list': saved_list,
        'whatsapp_text': copy_text,
        'copy_text': copy_text,
        'warning': calculator.get('warning'),
        'master_template_items': calculator.get('master_template_items', []),
        'metrics': form_data.get('_metrics', []),
        'price_note': form_data.get('_price_note', 'Цены ориентировочные по Казахстану'),
        'variants': ordered_variants,
        'variants_by_key': variants_by_key,
        'selected_variant': selected_key,
        'selected_variant_label': selected['title'],
        'selected_variant_description': selected['description'],
        'variant_heading': ' / '.join(variant['title'] for variant in ordered_variants),
        'totals': {
            'materials_total': selected['total'],
            'grand_total': selected['total'],
        },
        'meta': {
            'area': area,
            'thickness': thickness,
            'rooms': rooms,
            'segment': 'comfort',
            'selected_variant': selected_key,
            'input': dict(form_data),
        },
    }


def _build_result(calculator, materials, form_data, area, rooms, thickness, segment_key, segment, summary):
    reference_total = 0
    result_materials = []
    for material in materials:
        reference_price = round(material['reference_price'] * segment['material'])
        reference_row_total = round(material['quantity'] * reference_price)
        reference_total += reference_row_total
        result_materials.append({
            'title': material['title'],
            'quantity': material['quantity'],
            'unit': material['unit'],
            'reference_price': reference_price,
            'reference_total': reference_row_total,
            'price': reference_price,
            'total': reference_row_total,
        })
    reference_labor_total = round(area * segment['labor'])
    reference_grand_total = reference_total + reference_labor_total
    saved_list = '\n'.join(f"{material['title']} — {material['quantity']} {material['unit']}" for material in result_materials)
    return {
        'materials': result_materials,
        'materials_count': len(result_materials),
        'reference_total': reference_total,
        'reference_labor_total': reference_labor_total,
        'reference_grand_total': reference_grand_total,
        'materials_total': reference_total,
        'labor_total': reference_labor_total,
        'grand_total': reference_grand_total,
        'segment_label': segment['label'],
        'summary': summary,
        'saved_list': saved_list,
        'whatsapp_text': f"ESEPTEP: {summary}. Материалы:\n{saved_list}\nЦены уточняются у поставщиков.",
        'warning': calculator.get('warning'),
        'master_template_items': calculator.get('master_template_items', []),
        'metrics': form_data.get('_metrics', []),
        'price_note': form_data.get('_price_note', 'Справочно по материалам'),
        'meta': {
            'area': area,
            'thickness': thickness,
            'rooms': rooms,
            'segment': segment_key,
            'input': dict(form_data),
        },
    }


def _row(material, quantity):
    return {'title': material['title'], 'quantity': _round_quantity(quantity), 'unit': material['unit'], 'reference_price': material['reference_price']}


def _row_by_title(calculator, title, quantity):
    material = next(item for item in calculator['materials'] if item['title'] == title)
    return _row(material, quantity)


def _get_segment(value, calculator):
    segment_key = SEGMENT_ALIASES.get(value, value) or 'comfort'
    if segment_key not in SEGMENTS:
        segment_key = 'comfort'
    return segment_key, calculator.get('segments', SEGMENTS).get(segment_key, SEGMENTS['comfort'])


def _plain_segment():
    return PLAIN_REFERENCE


def _round_quantity(value):
    if value <= 0:
        return 0
    if value < 10:
        return round(value, 1)
    return round(value)
