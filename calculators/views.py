from django.http import Http404
from django.shortcuts import render

from .catalog import CALCULATORS, CALCULATORS_BY_SLUG, SEGMENT_MULTIPLIERS


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
        result = {
            'materials': materials,
            'materials_total': materials_total,
            'labor_total': labor_total,
            'grand_total': grand_total,
            'segment_label': segment['label'],
            'summary': f"{calculator['title']} · {area:g} {calculator['unit']} · {rooms} комн.",
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
        },
    )


def _to_float(value, default):
    try:
        return float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return default
