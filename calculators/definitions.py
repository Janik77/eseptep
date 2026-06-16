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
    {'name': 'area', 'label': 'Площадь квартиры (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 42},
    {
        'name': 'demolition_type',
        'label': 'Тип демонтажа',
        'type': 'select',
        'default': 'partial',
        'options': [
            {'value': 'cosmetic', 'label': 'Косметический демонтаж'},
            {'value': 'partial', 'label': 'Частичный демонтаж'},
            {'value': 'full', 'label': 'Полный демонтаж'},
        ],
    },
]

PLUMBING_FIELDS = [
    {'name': 'area', 'label': 'Площадь объекта (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 60},
    {'name': 'bathrooms', 'label': 'Количество санузлов', 'type': 'number', 'unit': 'шт', 'min': 1, 'step': 1, 'default': 1},
]

PLASTER_FIELDS = [
    {'name': 'area', 'label': 'Площадь помещения (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 42},
    {'name': 'thickness', 'label': 'Толщина штукатурки (см)', 'type': 'number', 'unit': '', 'min': 0.5, 'step': 0.1, 'default': 2},
]

DRYWALL_FIELDS = [
    {'name': 'area', 'label': 'Площадь (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 30},
    {'name': 'rooms', 'label': 'Количество комнат', 'type': 'number', 'unit': '', 'min': 1, 'step': 1, 'default': 2},
    {
        'name': 'construction_type',
        'label': 'Тип конструкции',
        'type': 'select',
        'default': 'ceiling',
        'options': [
            {'value': 'ceiling', 'label': 'Потолок из гипсокартона'},
            {'value': 'wall', 'label': 'Обшивка стены'},
            {'value': 'partition', 'label': 'Перегородка'},
        ],
    },
]

SELF_LEVEL_FIELDS = [
    {'name': 'area', 'label': 'Площадь пола (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 30},
    {'name': 'thickness', 'label': 'Толщина (см)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 2},
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
    {'name': 'area', 'label': 'Площадь пола (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 20},
    {
        'name': 'covering_type',
        'label': 'Покрытие',
        'type': 'select',
        'default': 'laminate',
        'options': [
            {'value': 'laminate', 'label': 'Ламинат'},
            {'value': 'spc', 'label': 'SPC покрытие'},
            {'value': 'parquet', 'label': 'Паркет / инженерная доска'},
        ],
    },
]


PAINTING_FIELDS = [
    {'name': 'floor_area', 'label': 'Площадь пола (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 30},
    {
        'name': 'type',
        'label': 'Тип отделки',
        'type': 'select',
        'default': 'paint',
        'options': [
            {'value': 'wallpaper', 'label': 'Малярка под обои'},
            {'value': 'paint', 'label': 'Малярка под покраску'},
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
    {'name': 'area', 'label': 'Площадь (м²)', 'type': 'number', 'unit': '', 'min': 1, 'step': 0.1, 'default': 20},
    {
        'name': 'type',
        'label': 'Тип системы',
        'type': 'select',
        'default': 'electric_mat',
        'options': [
            {'value': 'electric_mat', 'label': 'Электрический мат'},
            {'value': 'electric_cable', 'label': 'Кабельный тёплый пол'},
            {'value': 'water', 'label': 'Водяной тёплый пол'},
        ],
    },
]

DRYWALL_MASTER_TEMPLATE_GROUPS = {
    'ceiling': [
        {'title': 'Гипсокартон потолочный 2 слоя', 'default_quantity': 1.0, 'unit': 'лист'},
        {'title': 'Профиль CD усиленный', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Профиль UD усиленный', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Подвес усиленный', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Краб усиленный', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Соединитель CD профиля', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Соединитель двухуровневый CD 60×27', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Дюбель-гвоздь', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Саморезы ГКЛ', 'default_quantity': 1.0, 'unit': 'пачка'},
        {'title': 'Саморезы-клопы', 'default_quantity': 1.0, 'unit': 'пачка'},
    ],
    'wall': [
        {'title': 'Гипсокартон стеновой 12.5 мм', 'default_quantity': 1.0, 'unit': 'лист'},
        {'title': 'Профиль UW усиленный', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Профиль CW усиленный', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Шумоизоляция Knauf Acoustic', 'default_quantity': 1.0, 'unit': 'м²'},
        {'title': 'Демпферная лента', 'default_quantity': 1.0, 'unit': 'м'},
        {'title': 'Дюбель-гвоздь', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Саморезы ГКЛ', 'default_quantity': 1.0, 'unit': 'пачка'},
    ],
    'partition': [
        {'title': 'Гипсокартон 2 слоя с одной стороны', 'default_quantity': 1.0, 'unit': 'лист'},
        {'title': 'Профиль UW усиленный', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Профиль CW усиленный', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Шумоизоляция Knauf Acoustic', 'default_quantity': 1.0, 'unit': 'м²'},
        {'title': 'Демпферная лента', 'default_quantity': 1.0, 'unit': 'м'},
        {'title': 'Дюбель-гвоздь 8×60', 'default_quantity': 1.0, 'unit': 'шт'},
        {'title': 'Саморезы ГКЛ', 'default_quantity': 1.0, 'unit': 'пачка'},
    ],
}

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



FLOORING_MASTER_TEMPLATE_GROUPS = {
    'laminate': [
        {'title': 'Ламинат', 'unit': 'м²'},
        {'title': 'Подложка', 'unit': 'м²'},
        {'title': 'Плинтус', 'unit': 'м'},
        {'title': 'Уголки/соединители/заглушки', 'unit': 'комплект'},
        {'title': 'Порог', 'unit': 'шт'},
        {'title': 'Мусорные мешки', 'unit': 'шт'},
    ],
    'spc': [
        {'title': 'SPC покрытие', 'unit': 'м²'},
        {'title': 'Подложка, если требуется', 'unit': 'м²'},
        {'title': 'Плинтус', 'unit': 'м'},
        {'title': 'Уголки/соединители/заглушки', 'unit': 'комплект'},
        {'title': 'Порог', 'unit': 'шт'},
        {'title': 'Мусорные мешки', 'unit': 'шт'},
    ],
    'parquet': [
        {'title': 'Паркет / инженерная доска', 'unit': 'м²'},
        {'title': 'Клей для паркета', 'unit': 'кг'},
        {'title': 'Грунтовка', 'unit': 'кг'},
        {'title': 'Плинтус', 'unit': 'м'},
        {'title': 'Уголки/соединители/заглушки', 'unit': 'комплект'},
        {'title': 'Порог', 'unit': 'шт'},
        {'title': 'Мусорные мешки', 'unit': 'шт'},
    ],
}

CALCULATORS = [
    _definition('demontazh', 'Демонтаж', 'Расчёт включает расходники и вывоз мусора: мешки, защитную плёнку, бумажный скотч, перчатки, диски и транспорт. Работа мастеров не считается.', 'demolition', 'м²', [
        _material('Мешки строительные 50 кг', 1.0, 'шт', 80),
        _material('Плёнка защитная', 1.05, 'м²', 45),
        _material('Бумажный малярный скотч', 0.04, 'шт', 1200),
        _material('Перчатки рабочие', 0.04, 'пар', 250),
        _material('Респиратор / маска', 0.03, 'шт', 800),
        _material('Очки защитные', 0.03, 'шт', 1800),
        _material('Алмазный диск / расходный диск', 0.03, 'шт', 3500),
        _material('Лом / монтажка', 0.02, 'шт', 6500),
        _material('Шпатель / скребок', 0.04, 'шт', 1200),
        _material('Вывоз мусора / машина', 0.03, 'рейс', 35000),
        _material('Контейнер для строительного мусора', 0.02, 'шт', 100000),
    ], DEMOLITION_FIELDS, warning='Расчёт предварительный. Объём мусора зависит от толщины стяжки, плитки, штукатурки, перегородок, этажа, лифта и расстояния до машины. Работа мастеров не включена.'),
    _definition('elektrika', 'Электрика', 'Расчёт материалов: кабель, автоматы, розетки, выключатели, гофра, клипсы, щит и защита.', 'electric', 'точка', [
        _material('Кабель ВВГнг-LS 3×1.5', 1.0, 'м', 520),
        _material('Кабель ВВГнг-LS 3×2.5', 1.0, 'м', 780),
        _material('Кабель ВВГнг-LS 3×6', 1.0, 'м', 1900),
        _material('Гофра 16 мм', 1.0, 'м', 120),
        _material('Гофра 20 мм', 1.0, 'м', 160),
        _material('Клипсы для гофры', 1.0, 'шт', 25),
        _material('Дюбель-гвоздь / анкер', 1.0, 'шт', 20),
        _material('Гвозди Toua', 1.0, 'шт', 25),
        _material('Розетки', 1.0, 'шт', 2500),
        _material('Выключатели', 1.0, 'шт', 2500),
        _material('Подрозетники', 1.0, 'шт', 250),
        _material('Распредкоробки', 1.0, 'шт', 500),
        _material('Автомат 10А', 1.0, 'шт', 3000),
        _material('Автомат 16А', 1.0, 'шт', 3200),
        _material('Автомат 25А', 1.0, 'шт', 4500),
        _material('Автомат 32А', 1.0, 'шт', 5500),
        _material('УЗО', 1.0, 'шт', 12000),
        _material('Дифавтомат', 1.0, 'шт', 16000),
        _material('Реле напряжения', 1.0, 'шт', 20000),
        _material('Электрощит 36 модулей', 1.0, 'шт', 40000),
        _material('DIN-рейка', 1.0, 'шт', 2000),
        _material('Нулевая шина', 1.0, 'шт', 1800),
        _material('Заземляющая шина', 1.0, 'шт', 1800),
        _material('Клеммы WAGO', 1.0, 'шт', 160),
        _material('Интернет кабель UTP', 1.0, 'м', 200),
        _material('ТВ кабель', 1.0, 'м', 220),
        _material('Кабель домофона', 1.0, 'м', 180),
        _material('Изолента', 1.0, 'шт', 700),
        _material('Стяжки пластиковые', 1.0, 'пачка', 1800),
        _material('Алебастр / гипс', 1.0, 'кг', 300),
    ], ELECTRIC_FIELDS, warning='Расчёт предварительный. Финальную схему групп, сечение кабеля, номиналы автоматов, УЗО и дифавтоматов должен проверить электрик по проекту, нагрузке и расстоянию от щита.'),
    _definition('santehnika', 'Сантехника', 'Санузел = ванная, туалет или совмещённый санузел. Кухня учитывается автоматически.', 'plumbing', 'м²', [
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
    ], PLUMBING_FIELDS, warning='Расчёт предварительный. Точная сантехника зависит от планировки, расположения стояков, кухни, санузлов, ванны/душевой, бойлера и выбранных брендов.'),
    _definition('shtukaturka', 'Штукатурные работы', 'Расчёт смеси, маяков и грунтовки по площади стен и толщине слоя.', 'trowel', 'м²', [
        _material('Штукатурка 30 кг', 1.0, 'мешков', 2700),
        _material('Грунтовка 10 кг', 1.0, 'шт', 4000),
        _material('Бетоноконтакт 15 кг', 1.0, 'шт', 11000),
        _material('Маяк железный 3 м', 1.0, 'шт', 200),
        _material('Армировочная сетка 10 м', 1.0, 'рулонов', 4000),
        _material('Алюминиевый уголок 90°', 1.0, 'шт', 2000),
        _material('Правило 1,5 м', 1.0, 'шт', 4000),
        _material('Правило 3 м', 1.0, 'шт', 6000),
        _material('Шпатель 15 см', 1.0, 'шт', 1500),
        _material('Валик', 1.0, 'шт', 1500),
        _material('Ведро строительное', 1.0, 'шт', 1500),
        _material('Бумажный малярный скотч', 1.0, 'шт', 1000),
        _material('Плёнка защитная', 1.0, 'м²', 150),
        _material('Монтажная пена', 1.0, 'шт', 2500),
        _material('Мусорные мешки', 1.0, 'шт', 50),
    ], PLASTER_FIELDS, warning='Расчёт предварительный. Количество материалов нужно уточнить по проекту и фактическим условиям.'),
    _definition('gipsokarton-potolok', 'Гипсокартон', 'Расчёт монтажа гипсокартона и каркаса по площади, комнатам и типу конструкции.', 'drywall', 'м²', [
        _material('Гипсокартон потолочный 2 слоя', 1.0, 'лист', 3900),
        _material('Профиль CD усиленный', 1.0, 'шт', 1450),
        _material('Профиль UD усиленный', 1.0, 'шт', 1200),
        _material('Подвес усиленный', 1.0, 'шт', 180),
        _material('Краб усиленный', 1.0, 'шт', 180),
        _material('Соединитель CD профиля', 1.0, 'шт', 150),
        _material('Соединитель двухуровневый CD 60×27', 1.0, 'шт', 180),
        _material('Дюбель-гвоздь', 1.0, 'шт', 30),
        _material('Саморезы ГКЛ', 1.0, 'пачка', 3000),
        _material('Саморезы-клопы', 1.0, 'пачка', 3000),
        _material('Гипсокартон стеновой 12.5 мм', 1.0, 'лист', 4500),
        _material('Профиль UW усиленный', 1.0, 'шт', 1900),
        _material('Профиль CW усиленный', 1.0, 'шт', 2300),
        _material('Шумоизоляция Knauf Acoustic', 1.0, 'м²', 3200),
        _material('Демпферная лента', 1.0, 'м', 350),
        _material('Гипсокартон 2 слоя с одной стороны', 1.0, 'лист', 4500),
        _material('Дюбель-гвоздь 8×60', 1.0, 'шт', 45),
    ], DRYWALL_FIELDS, legacy_slugs=['gipsokarton'], warning='Малярные материалы не включены. Тут считается только монтаж гипсокартона и каркас. Для точного расчёта важны планировка, количество комнат, высота, ниши, световые линии и сложность конструкции.'),
    _definition('nalivnoy-pol', 'Наливной Пол', 'Наливной пол, грунтовка, маяки и расходники по площади и толщине слоя.', 'floor', 'м²', [
        _material('Наливной пол 25 кг', 1.0, 'мешков', 2900),
        _material('Грунтовка 10 кг', 1.0, 'шт', 400),
        _material('Маяк фиксатор', 1.0, 'шт', 80),
        _material('Демпферная лента', 1.0, 'м', 100),
        _material('Ведро строительное', 1.0, 'шт', 1000),
        _material('Валик', 1.0, 'шт', 1500),
        _material('Игольчатый валик 30-40 мм', 1.0, 'шт', 3500),
        _material('Игольчатый валик 40-50 мм', 1.0, 'шт', 4500),
        _material('Обувь шиповая', 1.0, 'пара', 5000),
        _material('Степлер', 1.0, 'шт', 3500),
        _material('Скобы', 1.0, 'шт', 10),
        _material('Мусорные мешки', 1.0, 'шт', 50),
    ], SELF_LEVEL_FIELDS),
    _definition('plitka-keramogranit', 'Плитка - Керамогранит', 'Плитка, керамогранит, клей, фуга и расходники по зоне укладки и формату.', 'tile', 'м²', [
        _material('Плитка / кафель', 1.08, 'м²', 6200),
        _material('Керамогранит', 1.1, 'м²', 7800),
        _material('Гидроизоляция', 1.05, 'м²', 1300),
        _material('Клей плиточный 25 кг', 0.32, 'мешок', 3300),
        _material('Клей для крупного формата 25 кг', 0.38, 'мешок', 4600),
        _material('Грунтовка', 0.12, 'л', 650),
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
    _definition('laminat-spc-parket', 'Напольное покрытие', 'Ламинат, SPC или паркет: покрытие, подложка, плинтус и расходники. Работа не включена — только материалы.', 'laminate', 'м²', [
        _material('Ламинат', 1.0, 'м²', 4500),
        _material('SPC покрытие', 1.0, 'м²', 6500),
        _material('Паркет / инженерная доска', 1.0, 'м²', 14500),
        _material('Подложка', 1.0, 'м²', 700),
        _material('Подложка, если требуется', 1.0, 'м²', 700),
        _material('Плинтус', 1.0, 'м', 1200),
        _material('Уголки/соединители/заглушки', 1.0, 'комплект', 5000),
        _material('Порог', 1.0, 'шт', 2500),
        _material('Клей для паркета', 1.0, 'кг', 2500),
        _material('Грунтовка', 1.0, 'кг', 1200),
        _material('Мусорные мешки', 1.0, 'шт', 500),
    ], FLOORING_FIELDS),
    _definition('malyarka', 'Малярка', 'Предварительный расчёт стен под обои или покраску без потолка.', 'paint', 'м²', [
        _material('Грунтовка 1 слой', 1.0, 'шт', 400),
        _material('Базовая шпаклёвка 2 слоя', 1.0, 'мешок', 3500),
        _material('Шкурка / сетка P100/P120', 1.0, 'шт', 300),
        _material('Обойный клей Metylan / аналог', 1.0, 'пачка', 3000),
        _material('Обои комфорт-класс', 1.0, 'рулон', 12000),
        _material('Финишная полимерная шпаклёвка 2 слоя', 1.0, 'мешок', 5000),
        _material('Шкурка / сетка P120/P180', 1.0, 'шт', 300),
        _material('Краска среднего сегмента 2 слоя', 1.0, 'л', 2200),
    ], PAINTING_FIELDS, warning='Расчёт предварительный. Площадь стен считается по формуле: Площадь пола × 3 − 10%.'),
    _definition('natyazhnoy-potolok', 'Натяжной потолок', 'Обычно площадь потолка равна площади пола. Работа не считается — только материалы.', 'ceiling', 'м²', [
        _material('ПВХ полотно MSD / аналог', 1.0, 'м²', 3500),
        _material('Алюминиевый профиль', 1.0, 'м', 400),
        _material('Теневая / декоративная вставка', 1.0, 'м', 300),
        _material('Термокольца под свет', 1.0, 'шт', 400),
        _material('Платформы под светильники', 1.0, 'шт', 900),
        _material('Точечные светильники комфорт', 1.0, 'шт', 4500),
        _material('Кабель для освещения', 1.0, 'м', 300),
        _material('Скрытый карниз / ниша', 1.0, 'шт', 6000),
    ], CEILING_FIELDS, warning='Расчёт предварительный. Периметр считается ориентировочно по площади. Точная смета зависит от формы комнат, количества углов, труб, карнизов, светильников, треков и выбранного полотна. Работа не включена.'),
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
    _definition('teplyy-pol', 'Тёплый пол', 'Для каждого типа система считает свои материалы. Работа не включена — только материалы.', 'warmfloor', 'м²', [
        _material('Нагревательный мат комфорт', 1.0, 'м²', 8500),
        _material('Нагревательный кабель комфорт', 1.0, 'м', 900),
        _material('Терморегулятор сенсорный', 1.0, 'шт', 25000),
        _material('Wi-Fi терморегулятор', 1.0, 'шт', 35000),
        _material('Датчик температуры пола', 1.0, 'шт', 4500),
        _material('Гофра под датчик', 1.0, 'м', 250),
        _material('Теплоизоляция плотная', 1.0, 'м²', 1800),
        _material('Монтажная лента усиленная', 1.0, 'м', 350),
        _material('Труба PE-RT / PEX 16 мм с кислородным барьером', 1.0, 'м', 650),
        _material('Маты / теплоизоляция плотная', 1.0, 'м²', 1800),
        _material('Демпферная лента', 1.0, 'м', 250),
        _material('Скобы / крепёж трубы', 1.0, 'шт', 45),
        _material('Коллектор с расходомерами', 1.0, 'компл.', 85000),
        _material('Коллекторный шкаф', 1.0, 'шт', 35000),
        _material('Фитинги и соединители', 1.0, 'компл.', 45000),
    ], WARM_FLOOR_FIELDS, warning='Расчёт предварительный. Электрический мат, кабельный и водяной тёплый пол считаются по разным материалам. Работа не включена.'),
]

CALCULATORS_BY_SLUG = {item['slug']: item for item in CALCULATORS}
CALCULATORS_BY_SLUG['gipsokarton-potolok']['master_template_groups'] = DRYWALL_MASTER_TEMPLATE_GROUPS
CALCULATORS_BY_SLUG['laminat-spc-parket']['master_template_groups'] = FLOORING_MASTER_TEMPLATE_GROUPS
for item in CALCULATORS:
    for legacy_slug in item.get('legacy_slugs', []):
        CALCULATORS_BY_SLUG[legacy_slug] = item

SEGMENT_MULTIPLIERS = SEGMENTS
