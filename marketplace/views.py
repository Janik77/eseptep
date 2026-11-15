from core.localization import render

from calculators.validation import InputValidationError, validate_fields

CITIES = ['Астана', 'Шымкент', 'Алматы']
DEVELOPERS = ['BI', 'OTAU', 'Bazis', 'Rise Group']
PACKAGE_FIELDS = [
    {'name': 'area', 'label': 'Квадратура квартиры', 'min': 1},
    *[{'name': name, 'label': label, 'type': 'select',
       'options': [{'value': value} for value in values]}
      for name, label, values in [('city', 'Город', CITIES), ('developer', 'Застройщик', DEVELOPERS)]],
]

TURNKEY_PACKAGES = [
    {
        'key': 'economy',
        'title': 'Эконом',
        'price_per_m2': 120000,
        'description': 'Базовый ремонт без лишних расходов.',
        'duration': 'от 45 дней',
        'items': [
            'Демонтаж и подготовка',
            'Черновые материалы',
            'Базовая электрика',
            'Базовая сантехника',
            'Штукатурка и шпаклёвка',
            'Ламинат / базовое покрытие',
            'Покраска или обои',
            'Минимальный контроль работ',
        ],
    },
    {
        'key': 'standard',
        'title': 'Стандарт',
        'price_per_m2': 170000,
        'description': 'Оптимальный вариант для комфортного проживания.',
        'duration': 'от 60 дней',
        'items': [
            'Черновые работы',
            'Электрика с нормальным запасом',
            'Сантехника',
            'Стены и потолки',
            'Полы',
            'Плитка в мокрых зонах',
            'Межкомнатные двери',
            'Контроль материалов и мастеров',
        ],
    },
    {
        'key': 'premium',
        'title': 'Премиум',
        'price_per_m2': 250000,
        'description': 'Расширенный ремонт с качественными материалами и контролем.',
        'duration': 'от 75 дней',
        'items': [
            'Детальная подготовка',
            'Улучшенная электрика',
            'Сантехника повышенного уровня',
            'Качественная отделка стен',
            'Хорошие напольные покрытия',
            'Потолочные решения',
            'Плитка/керамогранит',
            'Расширенный контроль и сопровождение',
        ],
    },
]


def marketplace_home(request):
    form_data = {
        'city': 'Астана',
        'developer': 'BI',
        'area': '',
    }
    results = []

    form_errors = {}
    preview = request.method == 'GET' and request.GET.get('_preview') in {'0', '1'}
    source = request.POST if request.method == 'POST' else request.GET
    if request.method == 'POST' or preview:
        form_data = {name: source.get(name, '') for name in form_data}
    if request.method == 'POST' or (preview and source.get('_preview') == '1'):
        try:
            cleaned = validate_fields(PACKAGE_FIELDS, form_data)
        except InputValidationError as exc:
            form_errors = exc.errors
        else:
            area = float(cleaned['area'])
            for package in TURNKEY_PACKAGES:
                results.append({
                    **package,
                    'total': round(area * package['price_per_m2']),
                    'area': area,
                })

    return render(
        request,
        'marketplace/home.html',
        {
            'form_data': form_data,
            'packages': TURNKEY_PACKAGES,
            'results': results,
            'form_errors': form_errors,
            'cities': CITIES,
            'developers': DEVELOPERS,
        },
    )
