"""Central calculator definitions for ESEPTEP.

The dictionaries in this module describe calculator inputs, materials,
units, reference prices and master template defaults. Calculation formulas
belong in ``calculators.services`` so templates and JavaScript only render
server-prepared results.
"""

DEFAULT_FIELDS = [
    {
        'name': 'area',
        'label': 'Площадь',
        'type': 'number',
        'unit': 'м²',
        'min': 1,
        'step': 0.1,
        'default': 42,
    },
    {
        'name': 'thickness',
        'label': 'Толщина',
        'type': 'number',
        'unit': 'см',
        'min': 1,
        'step': 0.1,
        'default': 3,
    },
    {
        'name': 'rooms',
        'label': 'Количество комнат',
        'type': 'number',
        'unit': 'комн.',
        'min': 1,
        'step': 1,
        'default': 2,
    },
    {
        'name': 'segment',
        'label': 'Сегмент',
        'type': 'select',
        'default': 'comfort',
    },
]

SEGMENTS = {
    'econom': {'label': 'Эконом', 'material': 0.9, 'labor': 5500},
    'comfort': {'label': 'Комфорт', 'material': 1.0, 'labor': 7500},
    'business': {'label': 'Бизнес', 'material': 1.22, 'labor': 10500},
}

DEFAULT_WARNING = (
    'Расчёт показывает ориентировочное количество материалов. '
    'Цены указаны справочно и уточняются у поставщиков отдельным этапом.'
)


def _material(title, ratio, unit, reference_price):
    return {
        'title': title,
        'ratio': ratio,
        'unit': unit,
        'reference_price': reference_price,
    }


def _definition(slug, title, description, icon, unit, materials, legacy_slugs=None):
    return {
        'slug': slug,
        'legacy_slugs': legacy_slugs or [],
        'title': title,
        'description': description,
        'icon': icon,
        'fields': DEFAULT_FIELDS,
        'materials': materials,
        'units': {
            'input': unit,
            'materials': {material['title']: material['unit'] for material in materials},
        },
        'unit': unit,
        'reference_price': {
            'currency': 'KZT',
            'source': 'demo_reference',
            'is_primary_result': False,
        },
        'segments': SEGMENTS,
        'warning': DEFAULT_WARNING,
        'master_template_items': [
            {
                'title': material['title'],
                'default_quantity': material['ratio'],
                'unit': material['unit'],
            }
            for material in materials
        ],
        # Backward-compatible shape for older templates/admin demo code.
        'base_materials': [
            (material['title'], material['ratio'], material['reference_price'])
            for material in materials
        ],
    }


CALCULATORS = [
    _definition(
        'demontazh',
        'Демонтаж',
        'Мешки, защита, вынос и вывоз мусора перед стартом ремонта.',
        'demolition',
        'м²',
        [
            _material('Мешки строительные', 0.55, 'шт', 120),
            _material('Защитная плёнка и скотч', 0.04, 'комплект', 7000),
            _material('Вывоз мусора', 0.08, 'м³', 9000),
        ],
    ),
    _definition(
        'elektrika',
        'Электрика',
        'Кабель, автоматы, подрозетники и точки подключения.',
        'electric',
        'точка',
        [
            _material('Кабель ВВГнг-LS', 4.5, 'м', 380),
            _material('Подрозетник/коробка', 1.0, 'шт', 220),
            _material('Автоматика и расходники', 0.08, 'комплект', 9000),
        ],
    ),
    _definition(
        'santehnika',
        'Сантехника',
        'Трубы, фитинги и базовые расходники для мокрых зон.',
        'plumbing',
        'точка',
        [
            _material('Труба PPR/PEX', 3.2, 'м', 460),
            _material('Фитинги и краны', 0.35, 'комплект', 2800),
            _material('Гидроизоляционные расходники', 0.06, 'комплект', 12000),
        ],
    ),
    _definition(
        'shtukaturka',
        'Штукатурка',
        'Расчёт смеси, маяков и грунтовки по площади стен.',
        'trowel',
        'м²',
        [
            _material('Гипсовая штукатурка, мешок 30 кг', 0.95, 'мешок', 3200),
            _material('Грунтовка глубокого проникновения', 0.18, 'л', 650),
            _material('Маяк штукатурный', 0.22, 'шт', 450),
        ],
    ),
    _definition(
        'gipsokarton-potolok',
        'Гипсокартон Потолок',
        'Листы ГКЛ, профиль, подвесы и крепёж для потолочных конструкций.',
        'drywall',
        'м²',
        [
            _material('Лист ГКЛ 12.5 мм', 0.38, 'шт', 3600),
            _material('Профиль потолочный/направляющий', 1.7, 'м', 520),
            _material('Подвесы, саморезы и лента', 0.1, 'комплект', 2800),
        ],
        legacy_slugs=['gipsokarton'],
    ),
    _definition(
        'nalivnoy-pol',
        'Наливной Пол',
        'Смесь, грунт и демпферная лента для ровного основания.',
        'floor',
        'м²',
        [
            _material('Самовыравнивающаяся смесь, мешок 25 кг', 0.72, 'мешок', 4100),
            _material('Грунтовка для пола', 0.12, 'л', 700),
            _material('Демпферная лента', 0.45, 'м', 180),
        ],
    ),
    _definition(
        'plitka-keramogranit',
        'Плитка - Керамогранит',
        'Плитка/керамогранит, клей, затирка и СВП с учётом запаса.',
        'tile',
        'м²',
        [
            _material('Керамогранит', 1.08, 'м²', 6800),
            _material('Плиточный клей, мешок 25 кг', 0.32, 'мешок', 3300),
            _material('Затирка и СВП', 0.05, 'комплект', 9500),
        ],
        legacy_slugs=['plitka'],
    ),
    _definition(
        'laminat-spc-parket',
        'Ламинат-Spc-Паркет',
        'Напольное покрытие, подложка, плинтус и базовые расходники.',
        'laminate',
        'м²',
        [
            _material('Ламинат/SPC/паркет', 1.08, 'м²', 7200),
            _material('Подложка', 1.05, 'м²', 900),
            _material('Плинтус и расходники', 0.06, 'комплект', 8500),
        ],
    ),
    _definition(
        'malyarka',
        'Малярка',
        'Шпаклёвка, грунтовка, краска и расходники для финишной отделки.',
        'paint',
        'м²',
        [
            _material('Финишная шпаклёвка', 0.18, 'мешок', 3600),
            _material('Грунтовка', 0.16, 'л', 650),
            _material('Краска интерьерная', 0.22, 'л', 1800),
        ],
    ),
    _definition(
        'natyazhnoy-potolok',
        'Натяжной Потолок',
        'Полотно, профиль, закладные и световые точки.',
        'ceiling',
        'м²',
        [
            _material('ПВХ полотно', 1.0, 'м²', 4300),
            _material('Профиль стеновой', 0.45, 'м', 750),
            _material('Закладные под свет', 0.18, 'шт', 1600),
        ],
    ),
    _definition(
        'dveri',
        'Двери',
        'Комплект полотна, коробки, наличников и фурнитуры.',
        'door',
        'проём',
        [
            _material('Межкомнатная дверь', 1.0, 'комплект', 52000),
            _material('Доборы и наличники', 1.0, 'комплект', 12000),
            _material('Фурнитура и пена', 1.0, 'комплект', 8500),
        ],
    ),
    _definition(
        'teplyy-pol',
        'Тёплый Пол',
        'Мат, терморегулятор и комплект монтажа под плитку.',
        'warmfloor',
        'м²',
        [
            _material('Нагревательный мат', 1.0, 'м²', 14500),
            _material('Терморегулятор', 0.12, 'шт', 18500),
            _material('Датчик и монтажный комплект', 0.12, 'комплект', 6200),
        ],
    ),
]

CALCULATORS_BY_SLUG = {item['slug']: item for item in CALCULATORS}
for item in CALCULATORS:
    for legacy_slug in item.get('legacy_slugs', []):
        CALCULATORS_BY_SLUG[legacy_slug] = item

# Backward-compatible public name used by existing templates/views.
SEGMENT_MULTIPLIERS = SEGMENTS
