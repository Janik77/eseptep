"""Central calculator definitions for ESEPTEP.

Definitions describe inputs, materials, units, reference prices and master
sheet defaults. Runtime formulas live in ``calculators.services`` so Django
renders server-prepared results instead of calculating in HTML or JavaScript.
"""

SEGMENTS = {
    'economy': {'label': 'Эконом', 'material': 0.9, 'labor': 5500},
    'comfort': {'label': 'Комфорт', 'material': 1.0, 'labor': 7500},
    'business': {'label': 'Бизнес', 'material': 1.22, 'labor': 10500},
}

SEGMENT_OPTIONS = [{'value': key, 'label': segment['label']} for key, segment in SEGMENTS.items()]

ELECTRIC_FIELDS = [
    {'name': 'area', 'label': 'Площадь квартиры (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 60},
    {'name': 'rooms', 'label': 'Количество жилых комнат', 'type': 'number', 'unit': '', 'min': 1, 'step': 1, 'default': 2},
]

DEMOLITION_FIELDS = [
    {'name': 'area', 'label': 'Площадь демонтажа', 'type': 'number', 'unit': 'м²', 'min': 1, 'step': 0.1, 'default': 42},
    {
        'name': 'type',
        'label': 'Тип демонтажа',
        'type': 'select',
        'default': 'partial',
        'options': [
            {'value': 'cosmetic', 'label': 'Косметический'},
            {'value': 'partial', 'label': 'Частичный'},
            {'value': 'full', 'label': 'Полный'},
        ],
    },
]

PLUMBING_FIELDS = [
    {'name': 'area', 'label': 'Площадь квартиры', 'type': 'number', 'unit': 'м²', 'min': 1, 'step': 0.1, 'default': 60},
    {'name': 'bathrooms', 'label': 'Количество санузлов', 'type': 'number', 'unit': 'шт', 'min': 1, 'step': 1, 'default': 1},
]

PLASTER_FIELDS = [
    {'name': 'area', 'label': 'Площадь помещения (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 42},
    {'name': 'thickness', 'label': 'Толщина штукатурки (см)', 'type': 'number', 'unit': '', 'min': 0.5, 'step': 0.1, 'default': 2},
]

DRYWALL_FIELDS = [
    {'name': 'area', 'label': 'Площадь (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 30},
    {'name': 'rooms', 'label': 'Комнат', 'type': 'number', 'unit': '', 'min': 1, 'step': 1, 'default': 2},
    {
        'name': 'construction_type',
        'label': 'Тип конструкции',
        'type': 'select',
        'default': 'ceiling',
        'options': [
            {'value': 'ceiling', 'label': 'Потолок из гипсокартона'},
            {'value': 'partition', 'label': 'Перегородка'},
            {'value': 'box', 'label': 'Короб / ниша'},
        ],
    },
]

SELF_LEVEL_FIELDS = [
    {'name': 'area', 'label': 'Площадь пола', 'type': 'number', 'unit': 'м²', 'min': 1, 'step': 0.1, 'default': 42},
    {'name': 'thickness', 'label': 'Толщина слоя', 'type': 'number', 'unit': 'мм', 'min': 1, 'step': 1, 'default': 5},
]

TILE_FIELDS = [
    {'name': 'area', 'label': 'Площадь укладки (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 24},
    {
        'name': 'zone_type',
        'label': 'Зона укладки',
        'type': 'select',
        'default': 'floor',
        'options': [
            {'value': 'floor', 'label': 'Пол'},
            {'value': 'walls', 'label': 'Стены'},
            {'value': 'bathroom', 'label': 'Санузел полностью'},
            {'value': 'backsplash', 'label': 'Кухонный фартук'},
        ],
    },
    {
        'name': 'tile_format',
        'label': 'Формат плитки',
        'type': 'select',
        'default': '60x60',
        'options': [
            {'value': '60x60', 'label': '60×60'},
            {'value': '120x120', 'label': '120×120 крупный формат'},
        ],
    },
]

FLOORING_FIELDS = [
    {'name': 'area', 'label': 'Площадь пола', 'type': 'number', 'unit': 'м²', 'min': 1, 'step': 0.1, 'default': 42},
    {
        'name': 'type',
        'label': 'Тип покрытия',
        'type': 'select',
        'default': 'laminate',
        'options': [
            {'value': 'laminate', 'label': 'Ламинат'},
            {'value': 'spc', 'label': 'SPC'},
            {'value': 'parquet', 'label': 'Паркет / инженерная доска'},
        ],
    },
    {
        'name': 'layout',
        'label': 'Тип укладки',
        'type': 'select',
        'default': 'straight',
        'options': [
            {'value': 'straight', 'label': 'Прямая'},
            {'value': 'diagonal', 'label': 'Диагональная'},
            {'value': 'herringbone', 'label': 'Ёлочка'},
        ],
    },
]

PAINTING_FIELDS = [
    {'name': 'floor_area', 'label': 'Площадь пола', 'type': 'number', 'unit': 'м²', 'min': 1, 'step': 0.1, 'default': 42},
    {
        'name': 'type',
        'label': 'Тип отделки',
        'type': 'select',
        'default': 'paint',
        'options': [
            {'value': 'wallpaper', 'label': 'Обои'},
            {'value': 'paint', 'label': 'Покраска'},
        ],
    },
]

CEILING_FIELDS = [
    {'name': 'area', 'label': 'Площадь потолка (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 42},
    {'name': 'rooms', 'label': 'Количество комнат', 'type': 'number', 'unit': '', 'min': 1, 'step': 1, 'default': 2},
]

DOORS_FIELDS = [
    {'name': 'count', 'label': 'Количество дверей', 'type': 'number', 'unit': 'шт', 'min': 1, 'step': 1, 'default': 3},
]

WARM_FLOOR_FIELDS = [
    {'name': 'area', 'label': 'Площадь тёплого пола', 'type': 'number', 'unit': 'м²', 'min': 1, 'step': 0.1, 'default': 12},
    {
        'name': 'type',
        'label': 'Тип системы',
        'type': 'select',
        'default': 'mat',
        'options': [
            {'value': 'mat', 'label': 'Нагревательный мат'},
            {'value': 'cable', 'label': 'Кабель'},
            {'value': 'water', 'label': 'Водяной'},
        ],
    },
]

DEFAULT_WARNING = 'Расчёт предварительный. Количество материалов нужно уточнить по проекту и фактическим условиям.'


def _material(title, ratio, unit, reference_price):
    return {'title': title, 'ratio': ratio, 'unit': unit, 'reference_price': reference_price}


def _definition(slug, title, description, icon, unit, materials, fields, legacy_slugs=None, warning=None):
    return {
        'slug': slug,
        'legacy_slugs': legacy_slugs or [],
        'title': title,
        'description': description,
        'icon': icon,
        'fields': fields,
        'materials': materials,
        'units': {'input': unit, 'materials': {material['title']: material['unit'] for material in materials}},
        'unit': unit,
        'reference_price': {'currency': 'KZT', 'source': 'demo_reference', 'is_primary_result': False},
        'segments': SEGMENTS,
        'warning': warning or DEFAULT_WARNING,
        'master_template_items': [
            {'title': material['title'], 'default_quantity': material['ratio'], 'unit': material['unit']}
            for material in materials
        ],
        'base_materials': [(material['title'], material['ratio'], material['reference_price']) for material in materials],
    }


CALCULATORS = [
    _definition('demontazh', 'Демонтаж', 'Мешки, защита, расходники и вывоз мусора по типу демонтажа.', 'demolition', 'м²', [
        _material('Мешки строительные 50 кг', 1.2, 'шт', 120),
        _material('Плёнка защитная', 1.05, 'м²', 280),
        _material('Бумажный малярный скотч', 0.04, 'рулон', 900),
        _material('Перчатки рабочие', 0.05, 'пара', 650),
        _material('Респиратор / маска', 0.05, 'шт', 750),
        _material('Очки защитные', 0.03, 'шт', 1800),
        _material('Лом / монтажка', 0.02, 'шт', 6500),
        _material('Шпатель / скребок', 0.05, 'шт', 1200),
        _material('Алмазный диск / расходный диск', 0.04, 'шт', 3500),
        _material('Вывоз мусора / машина', 0.03, 'машина', 18000),
        _material('Контейнер для строительного мусора', 0.03, 'контейнер', 28000),
    ], DEMOLITION_FIELDS),
    _definition('elektrika', 'Электрика', 'Расчёт материалов: кабель, автоматы, розетки, выключатели, гофра, клипсы, щит и защита', 'electric', 'точка', [
        _material('Кабель ВВГнг-LS 3×2.5', 7.0, 'м', 380),
        _material('Кабель ВВГнг-LS 3×1.5', 3.5, 'м', 320),
        _material('Кабель ВВГнг-LS 3×6', 1.0, 'м', 950),
        _material('Подрозетники', 1.0, 'шт', 220),
        _material('Распредкоробки', 0.12, 'шт', 650),
        _material('Розетки', 0.7, 'шт', 2500),
        _material('Выключатели', 0.3, 'шт', 2300),
        _material('Автомат 10А', 0.04, 'шт', 4200),
        _material('Автомат 16А', 0.08, 'шт', 4200),
        _material('Автомат 25А', 0.02, 'шт', 5200),
        _material('Автомат 32А', 0.02, 'шт', 6500),
        _material('УЗО', 0.04, 'шт', 13500),
        _material('Дифавтомат', 0.02, 'шт', 16500),
        _material('Электрощит', 0.02, 'шт', 28000),
        _material('Гофра 16 мм', 0.35, 'м', 180),
        _material('Гофра 20 мм', 0.15, 'м', 240),
        _material('Клипсы для гофры', 0.5, 'шт', 35),
        _material('Дюбель-гвоздь / анкер', 0.5, 'шт', 45),
        _material('Гвозди Toua / газовый пистолет', 0.35, 'шт', 55),
        _material('Реле напряжения', 0.02, 'шт', 18500),
        _material('DIN-рейка', 0.02, 'м', 1200),
        _material('Нулевая шина', 0.02, 'шт', 950),
        _material('Заземляющая шина', 0.02, 'шт', 950),
        _material('Клеммы WAGO', 0.4, 'шт', 180),
        _material('Интернет кабель UTP', 0.6, 'м', 180),
        _material('ТВ кабель', 0.35, 'м', 220),
        _material('Кабель домофона', 0.18, 'м', 160),
        _material('Изолента', 0.03, 'рулон', 650),
        _material('Стяжки пластиковые', 0.5, 'шт', 25),
        _material('Алебастр / гипс', 0.08, 'кг', 450),
    ], ELECTRIC_FIELDS, warning='В эконом-расчёте: освещение делится на 2 автомата, розетки примерно на 5 автоматов, плита отдельно 3×6 + 32А.'),
    _definition('santehnika', 'Сантехника', 'Предварительный расчёт труб, сантехприборов и расходников с учётом кухни.', 'plumbing', 'м²', [
        _material('Труба водоснабжения', 0.35, 'м', 520),
        _material('Канализационная труба Ø50', 0.18, 'м', 780),
        _material('Канализационная труба Ø110', 0.08, 'м', 1600),
        _material('Фитинги / уголки / муфты', 0.3, 'шт', 420),
        _material('Краны / запорная арматура', 1.0, 'шт', 2800),
        _material('Коллектор', 1.0, 'шт', 18000),
        _material('Унитаз', 1.0, 'шт', 65000),
        _material('Инсталляция', 1.0, 'шт', 85000),
        _material('Раковина', 1.0, 'шт', 42000),
        _material('Смеситель', 1.0, 'шт', 28000),
        _material('Ванна', 1.0, 'шт', 120000),
        _material('Душевая зона', 1.0, 'шт', 140000),
        _material('Сифон / выпуск', 1.0, 'шт', 6500),
        _material('Теплоизоляция для труб', 0.2, 'м', 450),
        _material('Герметик санитарный', 1.0, 'шт', 2400),
        _material('ФУМ-лента', 1.0, 'шт', 500),
    ], PLUMBING_FIELDS),
    _definition('shtukaturka', 'Штукатурка', 'Расчёт смеси, маяков и грунтовки по площади стен и толщине слоя.', 'trowel', 'м²', [
        _material('Штукатурка гипсовая 30 кг', 0.95, 'мешок', 3200),
        _material('Грунтовка 10 кг', 0.18, 'шт', 6500),
        _material('Бетоноконтакт 15 кг', 0.05, 'шт', 7800),
        _material('Армировочная сетка', 1.05, 'м²', 420),
        _material('Маяк железный 3 м', 0.22, 'шт', 450),
        _material('Алюминиевый уголок 90°', 0.08, 'шт', 600),
        _material('Правило 1,5 м', 0.02, 'шт', 4500),
        _material('Правило 3 м', 0.02, 'шт', 7500),
        _material('Шпатель 15 см', 0.03, 'шт', 1800),
        _material('Валик', 0.03, 'шт', 2200),
        _material('Ведро строительное', 0.04, 'шт', 1800),
        _material('Бумажный малярный скотч', 0.04, 'рулон', 900),
        _material('Плёнка защитная', 1.05, 'м²', 280),
        _material('Монтажная пена', 0.03, 'шт', 2600),
        _material('Мусорные мешки', 0.2, 'шт', 120),
    ], PLASTER_FIELDS),
    _definition('gipsokarton-potolok', 'Гипсокартон Потолок', 'Листы ГКЛ, профиль, подвесы и крепёж по типу конструкции.', 'drywall', 'м²', [
        _material('Гипсокартон стеновой 12.5 мм', 0.38, 'шт', 3600),
        _material('Гипсокартон потолочный 9.5 мм', 0.38, 'шт', 3400),
        _material('Гипсокартон влагостойкий', 0.38, 'шт', 5200),
        _material('Профиль CD 60×27', 1.4, 'м', 520),
        _material('Профиль UD 27×28', 0.45, 'м', 420),
        _material('Профиль UW 50×40', 0.5, 'м', 650),
        _material('Профиль CW 50×50', 1.2, 'м', 720),
        _material('Профиль UW 75×40', 0.5, 'м', 850),
        _material('Профиль CW 75×50', 1.2, 'м', 920),
        _material('Подвес прямой', 0.8, 'шт', 180),
        _material('Краб одноуровневый', 0.45, 'шт', 260),
        _material('Соединитель CD профиля', 0.18, 'шт', 220),
        _material('Соединитель двухуровневый CD 60×27', 0.12, 'шт', 380),
        _material('Дюбель-гвоздь', 1.8, 'шт', 45),
        _material('Саморезы ГКЛ', 18, 'шт', 18),
        _material('Саморезы-клопы', 8, 'шт', 16),
        _material('Шумоизоляция', 1.0, 'м²', 1900),
        _material('Демпферная лента', 0.45, 'м', 180),
    ], DRYWALL_FIELDS, legacy_slugs=['gipsokarton'], warning='Количество комнат влияет на периметр, профиль UD/UW, крепёж и точность расчёта.'),
    _definition('nalivnoy-pol', 'Наливной Пол', 'Смесь, грунт и демпферная лента по площади и толщине слоя.', 'floor', 'м²', [
        _material('Наливной пол 25 кг', 0.72, 'мешок', 4100),
        _material('Грунтовка', 0.12, 'л', 700),
        _material('Демпферная лента', 0.45, 'м', 180),
        _material('Маяк-фиксатор', 0.35, 'шт', 120),
        _material('Ведро строительное', 0.04, 'шт', 1800),
        _material('Валик', 0.03, 'шт', 2200),
        _material('Игольчатый валик', 0.03, 'шт', 3500),
        _material('Обувь шиповая', 0.02, 'пара', 8500),
        _material('Степлер строительный', 0.01, 'шт', 9500),
        _material('Скобы для степлера', 0.08, 'упаковка', 1200),
        _material('Мусорные мешки', 0.2, 'шт', 120),
    ], SELF_LEVEL_FIELDS),
    _definition('plitka-keramogranit', 'Плитка - Керамогранит', 'Плитка, керамогранит, клей, фуга и расходники по зоне укладки и формату.', 'tile', 'м²', [
        _material('Плитка / кафель', 1.08, 'м²', 6200),
        _material('Керамогранит', 1.1, 'м²', 7800),
        _material('Гидроизоляция', 1.05, 'м²', 1300),
        _material('Клей плиточный 25 кг', 0.32, 'мешок', 3300),
        _material('Клей для крупного формата 25 кг', 0.38, 'мешок', 4600),
        _material('Фуга', 0.08, 'кг', 2200),
        _material('Эпоксидная фуга', 0.08, 'кг', 5200),
        _material('СВП', 0.06, 'комплект', 9500),
        _material('Крестики', 0.04, 'комплект', 1200),
        _material('Профиль / уголок для плитки', 0.12, 'м', 1800),
        _material('Силикон санитарный', 0.04, 'туба', 2400),
        _material('Плиткорезный диск', 0.03, 'шт', 4500),
        _material('Губка / ведро / мелкие расходники', 0.04, 'комплект', 3500),
        _material('Мусорные мешки', 0.2, 'шт', 120),
    ], TILE_FIELDS, legacy_slugs=['plitka']),
    _definition('laminat-spc-parket', 'Ламинат-Spc-Паркет', 'Покрытие, подложка, плинтус и расходники по типу покрытия и укладки.', 'laminate', 'м²', [
        _material('Ламинат', 1.05, 'м²', 7200),
        _material('SPC покрытие', 1.05, 'м²', 9200),
        _material('Паркет / инженерная доска', 1.18, 'м²', 18500),
        _material('Подложка', 1.05, 'м²', 900),
        _material('Плинтус', 1.0, 'м', 1800),
        _material('Угол внутренний', 0.04, 'шт', 900),
        _material('Угол наружный', 0.03, 'шт', 900),
        _material('Соединитель плинтуса', 0.04, 'шт', 700),
        _material('Заглушка плинтуса', 0.04, 'шт', 700),
        _material('Порог', 0.04, 'шт', 5500),
        _material('Клей для паркета', 0.25, 'кг', 2600),
        _material('Грунтовка', 0.12, 'л', 650),
        _material('Плёнка защитная', 1.05, 'м²', 280),
        _material('Мусорные мешки', 0.2, 'шт', 120),
    ], FLOORING_FIELDS),
    _definition('malyarka', 'Малярка', 'Предварительный расчёт стен под покраску или обои без потолка.', 'paint', 'м²', [
        _material('Базовая шпаклёвка 25 кг', 0.12, 'мешок', 3600),
        _material('Финишная шпаклёвка 20 кг', 0.08, 'мешок', 4200),
        _material('Финишная полимерная шпаклёвка 25 кг', 0.06, 'мешок', 5600),
        _material('Грунтовка', 0.16, 'л', 650),
        _material('Стеклохолст 1×50 м', 1.05, 'м²', 900),
        _material('Клей для стеклохолста', 0.18, 'кг', 1100),
        _material('Краска', 0.22, 'л', 1800),
        _material('Грунт-краска', 0.18, 'л', 1600),
        _material('Обои', 0.2, 'рулон', 9500),
        _material('Обойный клей', 0.05, 'пачка', 2200),
        _material('Бумажный малярный скотч', 0.04, 'рулон', 900),
        _material('Шкурка / сетка P80', 0.02, 'упаковка', 1800),
        _material('Шкурка / сетка P120', 0.02, 'упаковка', 1800),
        _material('Шкурка / сетка P180', 0.02, 'упаковка', 1800),
        _material('Валик', 0.03, 'шт', 2200),
        _material('Кисть', 0.03, 'шт', 1200),
        _material('Лоток для краски', 0.03, 'шт', 1600),
        _material('Плёнка защитная', 1.05, 'м²', 280),
        _material('Мусорные мешки', 0.2, 'шт', 120),
    ], PAINTING_FIELDS),
    _definition('natyazhnoy-potolok', 'Натяжной Потолок', 'Полотно, профиль, закладные и световые точки.', 'ceiling', 'м²', [
        _material('ПВХ полотно', 1.0, 'м²', 4300),
        _material('Тканевый потолок', 1.0, 'м²', 7200),
        _material('ПВХ багет / профиль', 0.45, 'м', 750),
        _material('Алюминиевый профиль', 0.45, 'м', 1200),
        _material('Теневой профиль', 0.2, 'м', 2600),
        _material('Парящий профиль', 0.15, 'м', 3200),
        _material('Декоративная вставка', 0.45, 'м', 500),
        _material('Термокольца', 1.0, 'шт', 900),
        _material('Платформы под светильники', 1.0, 'шт', 1600),
        _material('Точечные светильники', 1.0, 'шт', 3500),
        _material('Кабель для освещения', 1.5, 'м', 220),
        _material('Световая линия / LED-профиль', 0.1, 'м', 6500),
        _material('LED-лента', 0.1, 'м', 2200),
        _material('Блок питания LED', 0.02, 'шт', 8500),
        _material('Магнитный трек', 0.08, 'м', 12000),
        _material('Трековые светильники', 0.15, 'шт', 7500),
        _material('Скрытый карниз / ниша', 0.1, 'м', 3200),
    ], CEILING_FIELDS, warning='Обычно площадь потолка равна площади пола. Работа не считается — только материалы.'),
    _definition('dveri', 'Двери', 'Полотно, коробка, наличники и фурнитура по количеству дверей.', 'door', 'шт', [
        _material('Дверное полотно', 1.0, 'шт', 52000),
        _material('Коробка дверная', 1.0, 'комплект', 12000),
        _material('Доборы', 1.0, 'комплект', 9000),
        _material('Наличники', 1.0, 'комплект', 8500),
        _material('Ручки', 1.0, 'комплект', 6500),
        _material('Замок / защёлка', 1.0, 'шт', 4800),
        _material('Магнитный замок', 1.0, 'шт', 7800),
        _material('Петли', 1.0, 'комплект', 3500),
        _material('Скрытые петли', 1.0, 'комплект', 12500),
        _material('Уплотнитель', 1.0, 'комплект', 1800),
        _material('Стопор дверной', 1.0, 'шт', 1000),
        _material('Пена монтажная', 1.0, 'шт', 2600),
        _material('Силикон / герметик', 1.0, 'шт', 2400),
    ], DOORS_FIELDS),
    _definition('teplyy-pol', 'Тёплый Пол', 'Мат, кабель или водяной контур с расходниками.', 'warmfloor', 'м²', [
        _material('Нагревательный мат', 1.05, 'м²', 14500),
        _material('Нагревательный кабель', 9.0, 'м', 1200),
        _material('Монтажная лента для кабеля', 1.5, 'м', 450),
        _material('Терморегулятор', 1.0, 'шт', 18500),
        _material('Wi-Fi терморегулятор', 1.0, 'шт', 28500),
        _material('Датчик температуры пола', 1.0, 'шт', 4500),
        _material('Гофра под датчик', 2.0, 'м', 350),
        _material('Теплоизоляция под тёплый пол', 1.05, 'м²', 1600),
        _material('Труба PE-RT / PEX 16 мм', 6.0, 'м', 650),
        _material('Демпферная лента', 0.8, 'м', 180),
        _material('Скобы / крепёж трубы', 4.0, 'шт', 80),
        _material('Коллектор', 1.0, 'шт', 42000),
        _material('Коллекторный шкаф', 1.0, 'шт', 38000),
        _material('Фитинги и соединители', 1.0, 'комплект', 18000),
        _material('Смесительный узел', 1.0, 'шт', 95000),
    ], WARM_FLOOR_FIELDS),
]

CALCULATORS_BY_SLUG = {item['slug']: item for item in CALCULATORS}
for item in CALCULATORS:
    for legacy_slug in item.get('legacy_slugs', []):
        CALCULATORS_BY_SLUG[legacy_slug] = item

SEGMENT_MULTIPLIERS = SEGMENTS
