from django.shortcuts import render

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

    if request.method == 'POST':
        form_data['city'] = request.POST.get('city') or form_data['city']
        form_data['developer'] = request.POST.get('developer') or form_data['developer']
        form_data['area'] = request.POST.get('area') or ''
        try:
            area = max(float(str(form_data['area']).replace(',', '.')), 1)
        except (TypeError, ValueError):
            area = 0

        if area:
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
            'cities': ['Астана', 'Шымкент', 'Алматы'],
            'developers': ['BI', 'OTAU', 'Bazis', 'Rise Group'],
        },
    )
