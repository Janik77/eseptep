"""Server-side calculator services for ESEPTEP."""

from math import ceil, sqrt

from accounts.models import Calculation, ClientProject

from .definitions import SEGMENTS

SEGMENT_ALIASES = {'econom': 'economy'}
PLAIN_REFERENCE = {'label': 'Предварительно', 'material': 1.0, 'labor': 0}


def to_float(value, default):
    """Convert form values to float while supporting comma decimals."""
    try:
        return float(str(value).replace(',', '.'))
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
    selected_variant = form_data.get('selected_variant', 'optimal')
    price_sets = {
        'base': {'water': 450, 'sewer50': 650, 'sewer110': 1800, 'fittings': 350, 'valves': 2500, 'collector': 12000, 'toilet': 35000, 'sink': 25000, 'mixer': 18000, 'shower': 45000, 'siphon': 2500, 'insulation': 250},
        'optimal': {'water': 700, 'sewer50': 900, 'sewer110': 2500, 'fittings': 600, 'valves': 4500, 'collector': 25000, 'toilet': 70000, 'sink': 50000, 'mixer': 35000, 'shower': 90000, 'siphon': 4500, 'insulation': 350},
        'maximum': {'water': 1100, 'sewer50': 1400, 'sewer110': 3500, 'fittings': 1000, 'valves': 8000, 'collector': 50000, 'toilet': 150000, 'sink': 100000, 'mixer': 80000, 'shower': 180000, 'siphon': 8000, 'insulation': 500},
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
        'base': plumbing_variant('base', 'Базовый', 'Базовая разводка: трубы, канализация, простая сантехника и смесители.', {
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
        'optimal': plumbing_variant('optimal', 'Оптимальный', 'Оптимальная разводка: коллектор, хорошие краны, нормальная сантехника.', {
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
        'maximum': plumbing_variant('maximum', 'Максимальный', 'Скрытая разводка, качественная сантехника, коллекторы, запас под технику.', {
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
    thickness = to_float(form_data.get('thickness'), 2)
    thickness_factor = max(thickness, 0.5) / 2
    materials = [
        _row_by_title(calculator, 'Штукатурка гипсовая 30 кг', area * 0.95 * thickness_factor),
        _row_by_title(calculator, 'Грунтовка 10 кг', max(1, area * 0.018)),
        _row_by_title(calculator, 'Бетоноконтакт 15 кг', max(1, area * 0.012)),
        _row_by_title(calculator, 'Армировочная сетка', area * 1.05),
        _row_by_title(calculator, 'Маяк железный 3 м', area * 0.22),
        _row_by_title(calculator, 'Алюминиевый уголок 90°', max(4, area * 0.08)),
        _row_by_title(calculator, 'Правило 1,5 м', 1),
        _row_by_title(calculator, 'Правило 3 м', 1),
        _row_by_title(calculator, 'Шпатель 15 см', 2),
        _row_by_title(calculator, 'Валик', 1),
        _row_by_title(calculator, 'Ведро строительное', max(2, area / 40)),
        _row_by_title(calculator, 'Бумажный малярный скотч', max(1, area / 25)),
        _row_by_title(calculator, 'Плёнка защитная', area * 1.05),
        _row_by_title(calculator, 'Монтажная пена', max(1, area / 50)),
        _row_by_title(calculator, 'Мусорные мешки', area / 5),
    ]
    return _build_result(calculator, materials, form_data, area, 1, thickness, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {thickness:g} см")


def _calculate_gipsokarton(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    construction_type = form_data.get('construction_type', 'ceiling')
    room_factor = 1 + max(rooms - 1, 0) * 0.08
    ceiling = construction_type == 'ceiling'
    partition = construction_type == 'partition'
    box = construction_type == 'box'
    sheet_factor = 0.38 if ceiling else 0.76 if partition else 0.55
    materials = [
        _row_by_title(calculator, 'Гипсокартон стеновой 12.5 мм', 0 if ceiling else area * sheet_factor),
        _row_by_title(calculator, 'Гипсокартон потолочный 9.5 мм', area * sheet_factor if ceiling else 0),
        _row_by_title(calculator, 'Гипсокартон влагостойкий', area * 0.12 if partition else 0),
        _row_by_title(calculator, 'Профиль CD 60×27', area * (1.4 if ceiling or box else 0.4) * room_factor),
        _row_by_title(calculator, 'Профиль UD 27×28', area * (0.45 if ceiling or box else 0.15) * room_factor),
        _row_by_title(calculator, 'Профиль UW 50×40', area * (0.5 if partition else 0)),
        _row_by_title(calculator, 'Профиль CW 50×50', area * (1.2 if partition else 0)),
        _row_by_title(calculator, 'Профиль UW 75×40', area * (0.25 if partition else 0)),
        _row_by_title(calculator, 'Профиль CW 75×50', area * (0.6 if partition else 0)),
        _row_by_title(calculator, 'Подвес прямой', area * (0.8 if ceiling else 0.35) * room_factor),
        _row_by_title(calculator, 'Краб одноуровневый', area * (0.45 if ceiling else 0.15)),
        _row_by_title(calculator, 'Соединитель CD профиля', area * 0.18),
        _row_by_title(calculator, 'Соединитель двухуровневый CD 60×27', area * (0.12 if ceiling else 0.04)),
        _row_by_title(calculator, 'Дюбель-гвоздь', area * 1.8 * room_factor),
        _row_by_title(calculator, 'Саморезы ГКЛ', area * 18 * room_factor),
        _row_by_title(calculator, 'Саморезы-клопы', area * 8 * room_factor),
        _row_by_title(calculator, 'Шумоизоляция', area if partition else 0),
        _row_by_title(calculator, 'Демпферная лента', max(1, area * 0.45 * room_factor)),
    ]
    return _build_result(calculator, materials, form_data, area, rooms, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {rooms} комн. · {construction_type}")


def _calculate_nalivnoy_pol(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    thickness = to_float(form_data.get('thickness'), 5)
    mixture_bags = area * max(thickness, 1) * 1.7 / 25
    perimeter = 4 * sqrt(area) if area > 0 else 0
    materials = [
        _row_by_title(calculator, 'Наливной пол 25 кг', mixture_bags),
        _row_by_title(calculator, 'Грунтовка', area * 0.12),
        _row_by_title(calculator, 'Демпферная лента', perimeter),
        _row_by_title(calculator, 'Маяк-фиксатор', max(4, area * 0.35)),
        _row_by_title(calculator, 'Ведро строительное', max(1, area / 40)),
        _row_by_title(calculator, 'Валик', 1),
        _row_by_title(calculator, 'Игольчатый валик', max(1, area / 35)),
        _row_by_title(calculator, 'Обувь шиповая', 1),
        _row_by_title(calculator, 'Степлер строительный', 1),
        _row_by_title(calculator, 'Скобы для степлера', max(1, area / 20)),
        _row_by_title(calculator, 'Мусорные мешки', area / 5),
    ]
    return _build_result(calculator, materials, form_data, area, 1, thickness, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {thickness:g} мм")


def _calculate_plitka(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    zone_type = form_data.get('zone_type', 'floor')
    tile_format = form_data.get('tile_format', '60x60')
    reserve_factor = {'floor': 1.07, 'walls': 1.1, 'bathroom': 1.12, 'backsplash': 1.15}.get(zone_type, 1.08)
    is_large_format = tile_format == '120x120'
    tile_area = area * reserve_factor
    edge_length = 4 * sqrt(area) if area > 0 else 0
    wet_zone = zone_type == 'bathroom'
    backsplash = zone_type == 'backsplash'
    materials = [
        _row_by_title(calculator, 'Плитка / кафель', 0 if is_large_format else tile_area),
        _row_by_title(calculator, 'Керамогранит', tile_area if is_large_format else 0),
        _row_by_title(calculator, 'Гидроизоляция', area * 1.05 if wet_zone else 0),
        _row_by_title(calculator, 'Клей плиточный 25 кг', 0 if is_large_format else area * 0.32),
        _row_by_title(calculator, 'Клей для крупного формата 25 кг', area * 0.38 if is_large_format else 0),
        _row_by_title(calculator, 'Грунтовка', area * 0.12),
        _row_by_title(calculator, 'Фуга', 0 if wet_zone else area * (0.06 if backsplash else 0.08)),
        _row_by_title(calculator, 'Эпоксидная фуга', area * 0.08 if wet_zone else 0),
        _row_by_title(calculator, 'СВП', max(1, area * (0.08 if is_large_format else 0.04))),
        _row_by_title(calculator, 'Крестики', 0 if is_large_format else max(1, area * 0.04)),
        _row_by_title(calculator, 'Профиль / уголок для плитки', max(1, edge_length * (0.35 if backsplash else 0.2))),
        _row_by_title(calculator, 'Силикон санитарный', max(1, area / 20) if wet_zone or backsplash else 1),
        _row_by_title(calculator, 'Плиткорезный диск', max(1, area / 35)),
        _row_by_title(calculator, 'Губка / ведро / мелкие расходники', max(1, area / 30)),
        _row_by_title(calculator, 'Мусорные мешки', area / 5),
    ]
    return _build_result(calculator, materials, form_data, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {zone_type} · {tile_format}")


def _calculate_laminat_spc_parket(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    flooring_type = form_data.get('type', 'laminate')
    layout = form_data.get('layout', 'straight')
    reserve_area = {'straight': area * 1.05, 'diagonal': area * 1.12, 'herringbone': area * 1.18}.get(layout, area * 1.05)
    perimeter = 4 * sqrt(area) if area > 0 else 0
    materials = []
    if flooring_type == 'spc':
        materials.append(_row_by_title(calculator, 'SPC покрытие', reserve_area))
    elif flooring_type == 'parquet':
        materials.append(_row_by_title(calculator, 'Паркет / инженерная доска', reserve_area))
    else:
        materials.append(_row_by_title(calculator, 'Ламинат', reserve_area))
    materials.extend([
        _row_by_title(calculator, 'Подложка', area * 1.05),
        _row_by_title(calculator, 'Плинтус', perimeter * 1.05),
        _row_by_title(calculator, 'Угол внутренний', max(1, perimeter / 18)),
        _row_by_title(calculator, 'Угол наружный', max(1, perimeter / 24)),
        _row_by_title(calculator, 'Соединитель плинтуса', max(1, perimeter / 16)),
        _row_by_title(calculator, 'Заглушка плинтуса', max(2, perimeter / 18)),
        _row_by_title(calculator, 'Порог', max(1, area / 30)),
        _row_by_title(calculator, 'Плёнка защитная', area * 1.05),
        _row_by_title(calculator, 'Мусорные мешки', area / 5),
    ])
    if flooring_type == 'parquet':
        materials.extend([_row_by_title(calculator, 'Клей для паркета', area * 0.25), _row_by_title(calculator, 'Грунтовка', area * 0.12)])
    return _build_result(calculator, materials, {**form_data, 'reserve_area': reserve_area}, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {flooring_type} / {layout}")


def _calculate_malyarka(calculator, form_data):
    floor_area = to_float(form_data.get('floor_area'), 0)
    finish_type = form_data.get('type', 'paint')
    wall_area = floor_area * 3 * 0.9
    materials = [
        _row_by_title(calculator, 'Базовая шпаклёвка 25 кг', wall_area * 0.12),
        _row_by_title(calculator, 'Финишная шпаклёвка 20 кг', wall_area * 0.08),
        _row_by_title(calculator, 'Финишная полимерная шпаклёвка 25 кг', wall_area * 0.06),
        _row_by_title(calculator, 'Грунтовка', wall_area * 0.16),
        _row_by_title(calculator, 'Бумажный малярный скотч', max(1, wall_area / 25)),
        _row_by_title(calculator, 'Шкурка / сетка P80', max(1, wall_area / 45)),
        _row_by_title(calculator, 'Шкурка / сетка P120', max(1, wall_area / 45)),
        _row_by_title(calculator, 'Шкурка / сетка P180', max(1, wall_area / 45)),
        _row_by_title(calculator, 'Валик', 1),
        _row_by_title(calculator, 'Кисть', 1),
        _row_by_title(calculator, 'Лоток для краски', 1),
        _row_by_title(calculator, 'Плёнка защитная', floor_area * 1.05),
        _row_by_title(calculator, 'Мусорные мешки', floor_area / 5),
    ]
    if finish_type == 'wallpaper':
        materials.extend([
            _row_by_title(calculator, 'Обои', wall_area / 5),
            _row_by_title(calculator, 'Обойный клей', max(1, wall_area / 25)),
        ])
    else:
        materials.extend([
            _row_by_title(calculator, 'Стеклохолст 1×50 м', wall_area * 1.05),
            _row_by_title(calculator, 'Клей для стеклохолста', wall_area * 0.18),
            _row_by_title(calculator, 'Краска', wall_area * 0.22),
            _row_by_title(calculator, 'Грунт-краска', wall_area * 0.18),
        ])
    return _build_result(calculator, materials, {**form_data, 'wall_area': wall_area, 'ceiling_included': False}, floor_area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · стены {wall_area:g} м² · потолок не включён")


def _calculate_natyazhnoy_potolok(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    perimeter = 4 * sqrt(area) if area > 0 else 0
    light_points = max(rooms, round(area / 7))
    profile_factor = 1 + max(rooms - 1, 0) * 0.08
    materials = [
        _row_by_title(calculator, 'ПВХ полотно', area),
        _row_by_title(calculator, 'Тканевый потолок', 0),
        _row_by_title(calculator, 'ПВХ багет / профиль', perimeter * profile_factor),
        _row_by_title(calculator, 'Алюминиевый профиль', perimeter * 0.25 * profile_factor),
        _row_by_title(calculator, 'Теневой профиль', perimeter * 0.12),
        _row_by_title(calculator, 'Парящий профиль', perimeter * 0.08),
        _row_by_title(calculator, 'Декоративная вставка', perimeter * profile_factor),
        _row_by_title(calculator, 'Термокольца', light_points),
        _row_by_title(calculator, 'Платформы под светильники', light_points),
        _row_by_title(calculator, 'Точечные светильники', light_points),
        _row_by_title(calculator, 'Кабель для освещения', max(10, area * 1.5)),
        _row_by_title(calculator, 'Световая линия / LED-профиль', max(0, area / 12)),
        _row_by_title(calculator, 'LED-лента', max(0, area / 12)),
        _row_by_title(calculator, 'Блок питания LED', max(1, area / 40)),
        _row_by_title(calculator, 'Магнитный трек', max(0, rooms * 0.5)),
        _row_by_title(calculator, 'Трековые светильники', max(0, rooms * 2)),
        _row_by_title(calculator, 'Скрытый карниз / ниша', max(0, rooms * 1.5)),
    ]
    return _build_result(calculator, materials, form_data, area, rooms, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {rooms} комн.")


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


def _calculate_teplyy_pol(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    floor_type = form_data.get('type', 'mat')
    if floor_type == 'cable':
        materials = [
            _row_by_title(calculator, 'Нагревательный кабель', area * 9),
            _row_by_title(calculator, 'Монтажная лента для кабеля', area * 1.5),
            _row_by_title(calculator, 'Терморегулятор', 1),
            _row_by_title(calculator, 'Wi-Fi терморегулятор', 1),
            _row_by_title(calculator, 'Датчик температуры пола', 1),
            _row_by_title(calculator, 'Гофра под датчик', max(2, area * 0.25)),
            _row_by_title(calculator, 'Теплоизоляция под тёплый пол', area * 1.05),
        ]
    elif floor_type == 'water':
        contours = max(1, area / 15)
        materials = [
            _row_by_title(calculator, 'Труба PE-RT / PEX 16 мм', area * 6),
            _row_by_title(calculator, 'Теплоизоляция под тёплый пол', area * 1.05),
            _row_by_title(calculator, 'Демпферная лента', area * 0.8),
            _row_by_title(calculator, 'Скобы / крепёж трубы', area * 4),
            _row_by_title(calculator, 'Коллектор', contours),
            _row_by_title(calculator, 'Коллекторный шкаф', 1),
            _row_by_title(calculator, 'Фитинги и соединители', contours),
            _row_by_title(calculator, 'Смесительный узел', 1),
        ]
    else:
        materials = [
            _row_by_title(calculator, 'Нагревательный мат', area * 1.05),
            _row_by_title(calculator, 'Терморегулятор', 1),
            _row_by_title(calculator, 'Wi-Fi терморегулятор', 1),
            _row_by_title(calculator, 'Датчик температуры пола', 1),
            _row_by_title(calculator, 'Гофра под датчик', max(2, area * 0.25)),
            _row_by_title(calculator, 'Теплоизоляция под тёплый пол', area * 1.05),
        ]
    return _build_result(
        calculator,
        materials,
        form_data,
        area,
        1,
        1,
        'comfort',
        _plain_segment(),
        f"{calculator['title']} · {area:g} м² · {floor_type}",
    )



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
