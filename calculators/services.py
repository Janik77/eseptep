"""Server-side calculator services for ESEPTEP."""

from accounts.models import Calculation, ClientProject

from .definitions import SEGMENTS

SEGMENT_ALIASES = {'econom': 'economy'}


def to_float(value, default):
    """Convert form values to float while supporting comma decimals."""
    try:
        return float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return default


def calculate_materials(calculator, form_data):
    """Calculate material quantities on the server.

    Main result is quantity + unit for each material. Reference prices are
    kept as secondary values for existing dashboards and future supplier flow.
    """
    slug = calculator['slug']
    if slug == 'demontazh':
        return _calculate_demontazh(calculator, form_data)
    if slug == 'teplyy-pol':
        return _calculate_teplyy_pol(calculator, form_data)
    if slug == 'dveri':
        return _calculate_dveri(calculator, form_data)
    return _calculate_ratio_based(calculator, form_data)


def save_calculation_for_user(user, slug, result):
    """Persist a server-calculated estimate for the authenticated client."""
    project = user.client_projects.order_by('-created_at').first()
    if project is None:
        project = ClientProject.objects.create(
            user=user,
            title=f'Проект {slug}',
            city=getattr(user.profile, 'city', '') or 'Не указан',
            area_m2=result['meta']['area'],
            rooms=result['meta']['rooms'],
            repair_segment=result['meta']['segment'],
            status=ClientProject.Status.CALCULATED,
        )

    calculation = Calculation.objects.create(
        project=project,
        calculator_slug=slug,
        area_m2=result['meta']['area'],
        rooms=result['meta']['rooms'],
        thickness=result['meta']['thickness'],
        segment=result['meta']['segment'],
        materials_total=result['materials_total'],
        works_total=result['labor_total'],
        grand_total=result['grand_total'],
        result_data={
            'materials': result['materials'],
            'summary': result['summary'],
            'segment_label': result['segment_label'],
            'warning': result['warning'],
            'input': result['meta'].get('input', {}),
        },
    )
    return project, calculation


def _calculate_ratio_based(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    thickness = to_float(form_data.get('thickness'), 1)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    segment_key, segment = _get_segment(form_data.get('segment', 'comfort'), calculator)
    complexity = _material_complexity(thickness, rooms)
    material_rows = [
        _row(material, round(area * material['ratio'] * complexity, 1))
        for material in calculator['materials']
    ]
    return _build_result(
        calculator=calculator,
        materials=material_rows,
        form_data=form_data,
        area=area,
        rooms=rooms,
        thickness=thickness,
        segment_key=segment_key,
        segment=segment,
        summary=f"{calculator['title']} · {area:g} {calculator['unit']} · {rooms} комн.",
    )


def _calculate_demontazh(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    demolition_type = form_data.get('type', 'partial')
    bag_multiplier = {
        'cosmetic': 1.2,
        'partial': 2.0,
        'full': 2.8,
    }.get(demolition_type, 2.0)
    material_rows = [
        _row_by_title(calculator, 'Мешки строительные 50 кг', area * bag_multiplier),
        _row_by_title(calculator, 'Плёнка защитная', area * 1.05),
        _row_by_title(calculator, 'Бумажный малярный скотч', max(1, area / 25)),
        _row_by_title(calculator, 'Перчатки рабочие', max(2, area / 20)),
        _row_by_title(calculator, 'Респиратор / маска', max(1, area / 20)),
        _row_by_title(calculator, 'Алмазный диск / расходный диск', max(1, area / 25)),
        _row_by_title(calculator, 'Вывоз мусора / машина', max(1, area / 45)),
        _row_by_title(calculator, 'Контейнер для строительного мусора', max(1, area / 45)),
    ]
    segment_key, segment = _get_segment('comfort', calculator)
    return _build_result(
        calculator=calculator,
        materials=material_rows,
        form_data=form_data,
        area=area,
        rooms=1,
        thickness=1,
        segment_key=segment_key,
        segment=segment,
        summary=f"{calculator['title']} · {area:g} м² · {demolition_type}",
    )


def _calculate_teplyy_pol(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    floor_type = form_data.get('type', 'mat')
    segment_key, segment = _get_segment(form_data.get('segment', 'comfort'), calculator)

    if floor_type == 'cable':
        cable_ratio = {'economy': 8, 'comfort': 9, 'business': 10}[segment_key]
        material_rows = [
            _row_by_title(calculator, 'Нагревательный кабель', area * cable_ratio),
            _row_by_title(calculator, 'Монтажная лента', area * 1.5),
            _row_by_title(calculator, 'Терморегулятор', 1),
            _row_by_title(calculator, 'Датчик температуры пола', 1),
            _row_by_title(calculator, 'Гофра под датчик', max(2, area * 0.25)),
            _row_by_title(calculator, 'Теплоизоляция', area * 1.05),
        ]
    elif floor_type == 'water':
        pipe_ratio = {'economy': 5, 'comfort': 6, 'business': 7}[segment_key]
        staples_ratio = {'economy': 3, 'comfort': 4, 'business': 5}[segment_key]
        contours = max(1, area / 15)
        material_rows = [
            _row_by_title(calculator, 'Труба PE-RT / PEX 16 мм', area * pipe_ratio),
            _row_by_title(calculator, 'Теплоизоляция', area * 1.05),
            _row_by_title(calculator, 'Демпферная лента', area * 0.8),
            _row_by_title(calculator, 'Скобы / крепёж трубы', area * staples_ratio),
            _row_by_title(calculator, 'Коллектор', contours),
            _row_by_title(calculator, 'Коллекторный шкаф', 1),
            _row_by_title(calculator, 'Фитинги', contours),
        ]
        if segment_key == 'business':
            material_rows.append(_row_by_title(calculator, 'Смесительный узел', 1))
    else:
        material_rows = [
            _row_by_title(calculator, 'Нагревательный мат', area * 1.05),
            _row_by_title(calculator, 'Терморегулятор', 1),
            _row_by_title(calculator, 'Датчик температуры пола', 1),
            _row_by_title(calculator, 'Гофра под датчик', max(2, area * 0.25)),
            _row_by_title(calculator, 'Теплоизоляция', area * 1.05),
        ]

    return _build_result(
        calculator=calculator,
        materials=material_rows,
        form_data=form_data,
        area=area,
        rooms=1,
        thickness=1,
        segment_key=segment_key,
        segment=segment,
        summary=f"{calculator['title']} · {area:g} м² · {floor_type}",
    )


def _calculate_dveri(calculator, form_data):
    count = max(1, int(to_float(form_data.get('count'), 1)))
    segment_key, segment = _get_segment(form_data.get('segment', 'comfort'), calculator)
    material_rows = [
        _row_by_title(calculator, 'Дверное полотно', count),
        _row_by_title(calculator, 'Коробка дверная', count),
        _row_by_title(calculator, 'Наличники', count),
        _row_by_title(calculator, 'Ручки', count),
        _row_by_title(calculator, 'Замок', count),
        _row_by_title(calculator, 'Петли', count),
    ]
    if segment_key == 'business':
        material_rows.append(_row_by_title(calculator, 'Уплотнители / стопоры', count))

    return _build_result(
        calculator=calculator,
        materials=material_rows,
        form_data=form_data,
        area=count,
        rooms=count,
        thickness=1,
        segment_key=segment_key,
        segment=segment,
        summary=f"{calculator['title']} · {count} шт · {segment['label']}",
    )


def _build_result(calculator, materials, form_data, area, rooms, thickness, segment_key, segment, summary):
    reference_total = 0
    result_materials = []
    for material in materials:
        reference_price = round(material['reference_price'] * segment['material'])
        reference_row_total = round(material['quantity'] * reference_price)
        reference_total += reference_row_total
        result_materials.append({
            'title': material['title'],
            'quantity': material['quantity'],
            'unit': material['unit'],
            'reference_price': reference_price,
            'reference_total': reference_row_total,
            'price': reference_price,
            'total': reference_row_total,
        })

    reference_labor_total = round(area * segment['labor'])
    reference_grand_total = reference_total + reference_labor_total
    saved_list = '\n'.join(
        f"{material['title']} — {material['quantity']} {material['unit']}"
        for material in result_materials
    )
    return {
        'materials': result_materials,
        'materials_count': len(result_materials),
        'reference_total': reference_total,
        'reference_labor_total': reference_labor_total,
        'reference_grand_total': reference_grand_total,
        'materials_total': reference_total,
        'labor_total': reference_labor_total,
        'grand_total': reference_grand_total,
        'segment_label': segment['label'],
        'summary': summary,
        'saved_list': saved_list,
        'whatsapp_text': (
            f"ESEPTEP: {summary}. Материалы:\n{saved_list}\n"
            'Цены уточняются у поставщиков.'
        ),
        'warning': calculator.get('warning'),
        'master_template_items': calculator.get('master_template_items', []),
        'meta': {
            'area': area,
            'thickness': thickness,
            'rooms': rooms,
            'segment': segment_key,
            'input': dict(form_data),
        },
    }


def _row(material, quantity):
    return {
        'title': material['title'],
        'quantity': _round_quantity(quantity),
        'unit': material['unit'],
        'reference_price': material['reference_price'],
    }


def _row_by_title(calculator, title, quantity):
    material = next(item for item in calculator['materials'] if item['title'] == title)
    return _row(material, quantity)


def _get_segment(value, calculator):
    segment_key = SEGMENT_ALIASES.get(value, value) or 'comfort'
    segment = calculator.get('segments', SEGMENTS).get(segment_key, SEGMENTS['comfort'])
    if segment_key not in SEGMENTS:
        segment_key = 'comfort'
    return segment_key, segment


def _round_quantity(value):
    if value <= 0:
        return 0
    if value < 10:
        return round(value, 1)
    return round(value)


def _material_complexity(thickness, rooms):
    """Shared quantity coefficient for current generic calculators."""
    return 1 + max(thickness - 1, 0) * 0.08 + max(rooms - 1, 0) * 0.035
