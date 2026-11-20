from core.localization import render
from django.urls import reverse
from urllib.parse import urlencode
from decimal import Decimal
from core.renovation_rates import rate_configuration, renovation_estimate, LEGACY_RATES

from calculators.validation import InputValidationError, validate_fields

CITIES = ['Астана', 'Шымкент', 'Алматы']
PACKAGE_FIELDS = [
    {'name': 'area', 'label': 'Квадратура квартиры', 'min': 1},
    {'name': 'city', 'label': 'Город', 'type': 'select', 'options': [{'value': value} for value in CITIES]},
]

TURNKEY_PACKAGES = [
    {
        'key': 'economy',
        'title': 'Эконом',
        'price_per_m2': int(LEGACY_RATES['economy']),
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
        'price_per_m2': int(LEGACY_RATES['standard']),
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
        'price_per_m2': int(LEGACY_RATES['premium']),
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
        'city': 'Шымкент',
        'area': '',
    }
    results = []
    rate_config = rate_configuration()

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
            from accounts.turnkey_views import meeting_master, signed_quote
            provider = meeting_master()
            area = format(Decimal(cleaned['area']).quantize(Decimal('.01')), 'f')
            for package in TURNKEY_PACKAGES:
                estimate = renovation_estimate(area, package['key'], rate_config)
                quote_url = reverse('accounts:turnkey_preview') + '?' + urlencode({'quote':signed_quote(estimate, cleaned['city'], provider)}) if provider else ''
                results.append({
                    **package,
                    'total': estimate['total'], 'quote_url': quote_url,
                    'price_per_m2': rate_config['rates'][package['key']],
                    'area': area,
                })

    return render(
        request,
        'marketplace/home.html',
        {
            'rate_config': rate_config,
            'form_data': form_data,
            'packages': TURNKEY_PACKAGES,
            'results': results,
            'form_errors': form_errors,
            'cities': CITIES,
        },
    )
