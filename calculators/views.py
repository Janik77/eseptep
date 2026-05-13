from django.http import Http404
from django.shortcuts import render

from .catalog import CALCULATORS, CALCULATORS_BY_SLUG, SEGMENT_MULTIPLIERS

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
        'name': 'BuildMarket',
        'meta': 'Доставка сегодня · чек и гарантия',
        'badge': '−7% на смеси',
    },
    {
        'name': 'Kerama Hub',
        'meta': 'Плитка, СВП, клей · самовывоз',
        'badge': 'Есть остатки',
    },
    {
        'name': 'DomStroy склад',
        'meta': 'ГКЛ, профиль, электрика · опт',
        'badge': 'Счёт за 15 мин',
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
        area = _to_float(form_data['area'], 0)
        thickness = _to_float(form_data['thickness'], 1)
        rooms = max(1, int(_to_float(form_data['rooms'], 1)))
        segment = SEGMENT_MULTIPLIERS.get(form_data['segment'], SEGMENT_MULTIPLIERS['comfort'])
        complexity = 1 + max(thickness - 1, 0) * 0.08 + max(rooms - 1, 0) * 0.035

        materials = []
        materials_total = 0
        for title, qty_per_area, price in calculator['base_materials']:
            quantity = round(area * qty_per_area * complexity, 1)
            total = round(quantity * price * segment['material'])
            materials_total += total
            materials.append({
                'title': title,
                'quantity': quantity,
                'price': round(price * segment['material']),
                'total': total,
            })

        labor_total = round(area * segment['labor'] * complexity)
        grand_total = materials_total + labor_total
        saved_list = '\n'.join(
            f"{material['title']} — {material['quantity']} ед. — ₸ {material['total']}"
            for material in materials
        )
        result = {
            'materials': materials,
            'materials_total': materials_total,
            'labor_total': labor_total,
            'grand_total': grand_total,
            'segment_label': segment['label'],
            'summary': f"{calculator['title']} · {area:g} {calculator['unit']} · {rooms} комн.",
            'saved_list': saved_list,
            'whatsapp_text': f"ESEPTEP: {calculator['title']} — {area:g} {calculator['unit']}. Итого: ₸ {grand_total}. Материалы:\n{saved_list}",
        }

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
        },
    )


def _to_float(value, default):
    try:
        return float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return default
