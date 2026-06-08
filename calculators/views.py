from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render

from accounts.models import ServiceRequest

from .definitions import CALCULATORS, CALCULATORS_BY_SLUG, SEGMENT_MULTIPLIERS
from .services import calculate_materials, save_calculation_for_user

RECOMMENDED_MASTERS = [
    {
        'name': 'Азамат Рахимов',
        'photo': 'https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=360&q=80',
        'rating': '4.9',
        'specialization': 'Черновые работы',
        'experience': '9 лет опыта',
        'city': 'Алматы',
        'status': 'Свободен',
    },
    {
        'name': 'Айдана Сеитова',
        'photo': 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=360&q=80',
        'rating': '5.0',
        'specialization': 'Плитка и санузлы',
        'experience': '7 лет опыта',
        'city': 'Астана',
        'status': 'Свободен',
    },
    {
        'name': 'Бригада Qurylys Pro',
        'photo': 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=360&q=80',
        'rating': '4.8',
        'specialization': 'Ремонт под ключ',
        'experience': '12 лет опыта',
        'city': 'Алматы',
        'status': 'Свободен',
    },
    {
        'name': 'Руслан Темир',
        'photo': 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=360&q=80',
        'rating': '4.9',
        'specialization': 'Электрика',
        'experience': '8 лет опыта',
        'city': 'Шымкент',
        'status': 'Свободен',
    },
    {
        'name': 'Мария Волкова',
        'photo': 'https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&w=360&q=80',
        'rating': '4.7',
        'specialization': 'Дизайн + отделка',
        'experience': '6 лет опыта',
        'city': 'Алматы',
        'status': 'Свободен',
    },
    {
        'name': 'Ержан Мусин',
        'photo': 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=360&q=80',
        'rating': '4.8',
        'specialization': 'Сантехника',
        'experience': '10 лет опыта',
        'city': 'Караганда',
        'status': 'Свободен',
    },
]

MATERIAL_SELLERS = [
    {
        'name': 'СтройМарт Astana',
        'price': 'от ₸ 3 200',
        'delivery': 'Доставка 2–3 часа',
        'address': 'пр. Кабанбай Батыра, 48',
        'availability': 'В наличии: 142 позиции',
        'whatsapp': 'https://wa.me/?text=ESEPTEP%20-%20хочу%20заказать%20материалы%20в%20СтройМарт%20Astana',
    },
    {
        'name': 'Keruen Build Market',
        'price': 'от ₸ 4 100',
        'delivery': 'Доставка сегодня',
        'address': 'ул. Сыганак, 16/5',
        'availability': 'В наличии: плитка, клей, СВП',
        'whatsapp': 'https://wa.me/?text=ESEPTEP%20-%20нужен%20счёт%20Keruen%20Build%20Market',
    },
    {
        'name': 'ДомСтрой склад',
        'price': 'от ₸ 2 850',
        'delivery': 'Самовывоз + доставка',
        'address': 'ул. Алаш, 29',
        'availability': 'В наличии: ГКЛ, профиль, смеси',
        'whatsapp': 'https://wa.me/?text=ESEPTEP%20-%20заказ%20материалов%20ДомСтрой%20склад',
    },
    {
        'name': 'MegaPlitka Astana',
        'price': 'от ₸ 6 900 / м²',
        'delivery': 'Доставка завтра',
        'address': 'пр. Туран, 55',
        'availability': 'В наличии: 38 коллекций',
        'whatsapp': 'https://wa.me/?text=ESEPTEP%20-%20подберите%20плитку%20MegaPlitka%20Astana',
    },
]

def calculators_home(request):
    return render(request, 'calculators/home.html', {'calculators': CALCULATORS})


def calculator_detail(request, slug):
    calculator = CALCULATORS_BY_SLUG.get(slug)
    if calculator is None:
        raise Http404('Калькулятор не найден')

    form_data = {
        'area': request.POST.get('area', '42'),
        'thickness': request.POST.get('thickness', '3'),
        'rooms': request.POST.get('rooms', '2'),
        'segment': request.POST.get('segment', 'comfort'),
    }
    result = None

    if request.method == 'POST':
        result = calculate_materials(calculator, form_data)
        action = request.POST.get('action')

        if request.user.is_authenticated and action in {'save_estimate', 'request_master', 'request_supplier'}:
            project, calculation = save_calculation_for_user(request.user, slug, result)
            if action == 'request_master':
                ServiceRequest.objects.create(
                    client=request.user,
                    project=project,
                    calculation=calculation,
                    request_type=ServiceRequest.RequestType.MASTER,
                    status=ServiceRequest.Status.NEW,
                    comment=f'Заявка после расчёта: {calculator["title"]}',
                )
                messages.success(request, 'Смета сохранена и заявка мастерам отправлена.')
            elif action == 'request_supplier':
                ServiceRequest.objects.create(
                    client=request.user,
                    project=project,
                    calculation=calculation,
                    request_type=ServiceRequest.RequestType.SUPPLIER,
                    status=ServiceRequest.Status.NEW,
                    comment=f'Запрос поставщикам после расчёта: {calculator["title"]}',
                )
                messages.success(request, 'Смета сохранена и запрос поставщикам отправлен.')
            else:
                messages.success(request, 'Смета сохранена в личный кабинет.')
            return redirect('calculators:detail', slug=slug)
    return render(
        request,
        'calculators/detail.html',
        {
            'calculator': calculator,
            'form_data': form_data,
            'segments': SEGMENT_MULTIPLIERS,
            'result': result,
            'calculators': CALCULATORS,
            'recommended_masters': RECOMMENDED_MASTERS,
            'material_sellers': MATERIAL_SELLERS,
            'show_auth_save_cta': not request.user.is_authenticated,
        },
    )

