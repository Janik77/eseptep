from core.localization import render
from django.urls import reverse


def home(request):
    feature_cards = [
        {
            'eyebrow': 'Материалы',
            'title': 'Расчёт материалов',
            'description': 'Смета по категориям, объёмам и запасу — без Excel и ручных формул.',
            'cta': 'Открыть расчёт',
            'url': reverse('calculators:home'),
            'accent': 'mint',
            'icon': 'ruler',
        },
        {
            'eyebrow': 'Мастера',
            'title': 'Ремонт под ключ',
            'description': 'Выберите пакет и оцените предварительный бюджет ремонта.',
            'cta': 'Оценить бюджет',
            'url': reverse('masters'),
            'accent': 'amber',
            'icon': 'helmet',
        },
        {
            'eyebrow': 'Планы',
            'title': 'Загрузить проект',
            'description': 'Файлы, планировки и данные объекта в одной карточке проекта.',
            'cta': 'Загрузить',
            'url': reverse('projects:upload'),
            'accent': 'violet',
            'icon': 'plan',
        },
    ]
    return render(request, 'core/home.html', {'feature_cards': feature_cards})
