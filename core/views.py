from django.shortcuts import render
from django.urls import reverse


def home(request):
    feature_cards = [
        {
            'eyebrow': 'Калькуляторы',
            'title': 'Расчёт материалов',
            'description': 'Быстрый старт для смет по стенам, полу, плитке и черновым материалам.',
            'cta': 'Открыть расчёт',
            'url': reverse('calculators:home'),
            'accent': 'mint',
        },
        {
            'eyebrow': 'Маркетплейс',
            'title': 'Ремонт под ключ',
            'description': 'Подготовленная структура для подбора бригад, услуг и готовых пакетов ремонта.',
            'cta': 'Смотреть услуги',
            'url': reverse('marketplace:home'),
            'accent': 'amber',
        },
        {
            'eyebrow': 'Проекты',
            'title': 'Загрузить проект',
            'description': 'Основа для загрузки планов, файлов и будущего расчёта по проектной документации.',
            'cta': 'Загрузить',
            'url': reverse('projects:home'),
            'accent': 'violet',
        },
    ]
    return render(request, 'core/home.html', {'feature_cards': feature_cards})
