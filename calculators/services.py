"""Server-side calculator services for ESEPTEP."""

from math import sqrt

from accounts.models import Calculation, ClientProject

from .definitions import SEGMENTS

SEGMENT_ALIASES = {'econom': 'economy'}
PLAIN_REFERENCE = {'label': 'Предварительно', 'material': 1.0, 'labor': 0}


def to_float(value, default):
    """Convert form values to float while supporting comma decimals."""
    try:
        return float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return default


def calculate_materials(calculator, form_data):
    """Calculate material quantities on the server."""
    calculators = {
        'demontazh': _calculate_demontazh,
        'elektrika': _calculate_elektrika,
        'santehnika': _calculate_santehnika,
        'shtukaturka': _calculate_shtukaturka,
        'gipsokarton-potolok': _calculate_gipsokarton,
        'nalivnoy-pol': _calculate_nalivnoy_pol,
        'plitka-keramogranit': _calculate_plitka,
        'laminat-spc-parket': _calculate_laminat_spc_parket,
        'malyarka': _calculate_malyarka,
        'natyazhnoy-potolok': _calculate_natyazhnoy_potolok,
        'dveri': _calculate_dveri,
        'teplyy-pol': _calculate_teplyy_pol,
    }
    calculator_func = calculators.get(calculator['slug'], _calculate_ratio_based)
    return calculator_func(calculator, form_data)


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
    materials = [_row(material, area * material['ratio']) for material in calculator['materials']]
    return _build_result(calculator, materials, form_data, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} {calculator['unit']}")


def _calculate_demontazh(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    demolition_type = form_data.get('type', 'partial')
    bag_multiplier = {'cosmetic': 1.2, 'partial': 2.0, 'full': 2.8}.get(demolition_type, 2.0)
    materials = [
        _row_by_title(calculator, 'Мешки строительные 50 кг', area * bag_multiplier),
        _row_by_title(calculator, 'Плёнка защитная', area * 1.05),
        _row_by_title(calculator, 'Бумажный малярный скотч', max(1, area / 25)),
        _row_by_title(calculator, 'Перчатки рабочие', max(2, area / 20)),
        _row_by_title(calculator, 'Респиратор / маска', max(1, area / 20)),
        _row_by_title(calculator, 'Алмазный диск / расходный диск', max(1, area / 25)),
        _row_by_title(calculator, 'Вывоз мусора / машина', max(1, area / 45)),
        _row_by_title(calculator, 'Контейнер для строительного мусора', max(1, area / 45)),
    ]
    return _build_result(calculator, materials, form_data, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {demolition_type}")


def _calculate_elektrika(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    points = max(1, int(to_float(form_data.get('points'), max(8, area * 0.55))))
    segment_key, segment = _get_segment(form_data.get('segment', 'comfort'), calculator)
    group_multiplier = {'economy': 0.14, 'comfort': 0.18, 'business': 0.24}[segment_key]
    diff_multiplier = {'economy': 0.03, 'comfort': 0.06, 'business': 0.1}[segment_key]
    materials = [
        _row_by_title(calculator, 'Кабель ВВГнг-LS 3×2.5', points * 7 + area * 0.5),
        _row_by_title(calculator, 'Кабель ВВГнг-LS 3×1.5', points * 3.5),
        _row_by_title(calculator, 'Подрозетник/коробка', points),
        _row_by_title(calculator, 'Розетки / выключатели', points),
        _row_by_title(calculator, 'Автомат защиты', max(4, points * group_multiplier)),
        _row_by_title(calculator, 'УЗО / дифавтомат', max(1, points * diff_multiplier)),
        _row_by_title(calculator, 'Щит электрический', 1),
        _row_by_title(calculator, 'Гофра / клипсы / расходники', max(1, area / 25)),
    ]
    return _build_result(calculator, materials, form_data, area, 1, 1, segment_key, segment, f"{calculator['title']} · {points} точек · {segment['label']}")


def _calculate_santehnika(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    bathrooms = max(1, int(to_float(form_data.get('bathrooms'), 1)))
    kitchen = 1
    plumbing_points = bathrooms * 4 + kitchen
    materials = [
        _row_by_title(calculator, 'Труба водоснабжения', area * 0.35 + bathrooms * 12 + kitchen * 8),
        _row_by_title(calculator, 'Канализационная труба Ø50', bathrooms * 5 + kitchen * 4),
        _row_by_title(calculator, 'Канализационная труба Ø110', bathrooms * 3),
        _row_by_title(calculator, 'Фитинги / уголки / муфты', max(10, bathrooms * 18 + kitchen * 8 + area / 5)),
        _row_by_title(calculator, 'Краны / запорная арматура', bathrooms * 4 + kitchen * 2),
        _row_by_title(calculator, 'Коллектор', bathrooms),
        _row_by_title(calculator, 'Унитаз', bathrooms),
        _row_by_title(calculator, 'Инсталляция', bathrooms),
        _row_by_title(calculator, 'Раковина', bathrooms),
        _row_by_title(calculator, 'Смеситель', bathrooms + kitchen),
        _row_by_title(calculator, 'Ванна', max(1, bathrooms - 1)),
        _row_by_title(calculator, 'Душевая зона', bathrooms),
        _row_by_title(calculator, 'Сифон / выпуск', plumbing_points),
        _row_by_title(calculator, 'Теплоизоляция для труб', area * 0.2 + bathrooms * 3),
        _row_by_title(calculator, 'Герметик санитарный', bathrooms + kitchen),
        _row_by_title(calculator, 'ФУМ-лента', max(1, bathrooms + kitchen)),
    ]
    return _build_result(calculator, materials, form_data, area, bathrooms, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {bathrooms} санузел(а) + кухня")


def _calculate_shtukaturka(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    thickness = to_float(form_data.get('thickness'), 2)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    thickness_factor = max(thickness, 0.5) / 2
    room_factor = 1 + max(rooms - 1, 0) * 0.03
    materials = [
        _row_by_title(calculator, 'Гипсовая штукатурка, мешок 30 кг', area * 0.95 * thickness_factor * room_factor),
        _row_by_title(calculator, 'Грунтовка глубокого проникновения', area * 0.18),
        _row_by_title(calculator, 'Маяк штукатурный', area * 0.22),
        _row_by_title(calculator, 'Уголок штукатурный', rooms * 4),
    ]
    return _build_result(calculator, materials, form_data, area, rooms, thickness, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {thickness:g} см")


def _calculate_gipsokarton(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    construction_type = form_data.get('type', 'ceiling')
    profile_factor = {'ceiling': 1.7, 'partition': 2.2, 'box': 2.8}.get(construction_type, 1.7)
    sheet_factor = {'ceiling': 0.38, 'partition': 0.76, 'box': 0.55}.get(construction_type, 0.38)
    materials = [
        _row_by_title(calculator, 'Лист ГКЛ 12.5 мм', area * sheet_factor),
        _row_by_title(calculator, 'Профиль потолочный/направляющий', area * profile_factor),
        _row_by_title(calculator, 'Подвесы', area * (0.8 if construction_type == 'ceiling' else 0.35)),
        _row_by_title(calculator, 'Саморезы', area * 18),
        _row_by_title(calculator, 'Лента / шпаклёвка швов', max(1, area * 0.08)),
    ]
    return _build_result(calculator, materials, form_data, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {construction_type}")


def _calculate_nalivnoy_pol(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    thickness = to_float(form_data.get('thickness'), 5)
    mixture_bags = area * max(thickness, 1) * 1.7 / 25
    perimeter = 4 * sqrt(area) if area > 0 else 0
    materials = [
        _row_by_title(calculator, 'Самовыравнивающаяся смесь, мешок 25 кг', mixture_bags),
        _row_by_title(calculator, 'Грунтовка для пола', area * 0.12),
        _row_by_title(calculator, 'Демпферная лента', perimeter),
        _row_by_title(calculator, 'Игольчатый валик / расходники', max(1, area / 35)),
    ]
    return _build_result(calculator, materials, form_data, area, 1, thickness, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {thickness:g} мм")


def _calculate_plitka(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    reserve = to_float(form_data.get('reserve'), 10)
    layout = form_data.get('layout', 'straight')
    layout_factor = {'straight': 1.0, 'diagonal': 1.06, 'complex': 1.1}.get(layout, 1.0)
    tile_area = area * (1 + reserve / 100) * layout_factor
    materials = [
        _row_by_title(calculator, 'Плитка / керамогранит', tile_area),
        _row_by_title(calculator, 'Плиточный клей, мешок 25 кг', area * 0.32 * layout_factor),
        _row_by_title(calculator, 'Затирка', area * 0.08),
        _row_by_title(calculator, 'СВП / крестики', max(1, area * 0.05 * layout_factor)),
        _row_by_title(calculator, 'Грунтовка', area * 0.12),
    ]
    return _build_result(calculator, materials, form_data, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · запас {reserve:g}%")


def _calculate_laminat_spc_parket(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    flooring_type = form_data.get('type', 'laminate')
    layout = form_data.get('layout', 'straight')
    reserve_area = {'straight': area * 1.05, 'diagonal': area * 1.12, 'herringbone': area * 1.18}.get(layout, area * 1.05)
    perimeter = 4 * sqrt(area) if area > 0 else 0
    materials = []
    if flooring_type == 'spc':
        materials.append(_row_by_title(calculator, 'SPC покрытие', reserve_area))
    elif flooring_type == 'parquet':
        materials.append(_row_by_title(calculator, 'Паркет / инженерная доска', reserve_area))
    else:
        materials.append(_row_by_title(calculator, 'Ламинат', reserve_area))
    materials.extend([
        _row_by_title(calculator, 'Подложка', area * 1.05),
        _row_by_title(calculator, 'Плинтус', perimeter * 1.05),
        _row_by_title(calculator, 'Уголки / соединители / заглушки', max(1, perimeter / 10)),
        _row_by_title(calculator, 'Порог', max(1, area / 30)),
        _row_by_title(calculator, 'Плёнка защитная', area * 1.05),
        _row_by_title(calculator, 'Мусорные мешки', area / 5),
    ])
    if flooring_type == 'parquet':
        materials.extend([_row_by_title(calculator, 'Клей для паркета', area * 0.25), _row_by_title(calculator, 'Грунтовка', area * 0.12)])
    return _build_result(calculator, materials, {**form_data, 'reserve_area': reserve_area}, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {flooring_type} / {layout}")


def _calculate_malyarka(calculator, form_data):
    floor_area = to_float(form_data.get('floor_area'), 0)
    finish_type = form_data.get('type', 'paint')
    wall_area = floor_area * 3 * 0.9
    materials = [
        _row_by_title(calculator, 'Шпаклёвка', wall_area * 0.18),
        _row_by_title(calculator, 'Грунтовка', wall_area * 0.16),
        _row_by_title(calculator, 'Малярная лента', max(1, wall_area / 25)),
        _row_by_title(calculator, 'Наждачная сетка', max(1, wall_area / 35)),
        _row_by_title(calculator, 'Плёнка защитная', floor_area * 1.05),
        _row_by_title(calculator, 'Мусорные мешки', floor_area / 5),
    ]
    if finish_type == 'wallpaper':
        materials.append(_row_by_title(calculator, 'Обои', wall_area / 5))
    else:
        materials.extend([_row_by_title(calculator, 'Стеклохолст / флизелин', wall_area * 1.05), _row_by_title(calculator, 'Краска', wall_area * 0.22)])
    return _build_result(calculator, materials, {**form_data, 'wall_area': wall_area, 'ceiling_included': False}, floor_area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · стены {wall_area:g} м² · потолок не включён")


def _calculate_natyazhnoy_potolok(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    light_points = max(0, int(to_float(form_data.get('light_points'), 0)))
    corners = max(4, int(to_float(form_data.get('corners'), 4)))
    cornice_length = to_float(form_data.get('cornice_length'), 0)
    perimeter = 4 * sqrt(area) if area > 0 else 0
    materials = [
        _row_by_title(calculator, 'ПВХ полотно', area),
        _row_by_title(calculator, 'Профиль стеновой', perimeter),
        _row_by_title(calculator, 'Закладные под свет', light_points),
        _row_by_title(calculator, 'Термокольцо / платформа', light_points),
        _row_by_title(calculator, 'Обвод угла', corners),
        _row_by_title(calculator, 'Карнизная ниша / профиль', cornice_length),
    ]
    return _build_result(calculator, materials, form_data, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {light_points} точек света")


def _calculate_dveri(calculator, form_data):
    count = max(1, int(to_float(form_data.get('count'), 1)))
    segment_key, segment = _get_segment(form_data.get('segment', 'comfort'), calculator)
    materials = [
        _row_by_title(calculator, 'Дверное полотно', count),
        _row_by_title(calculator, 'Коробка дверная', count),
        _row_by_title(calculator, 'Наличники', count),
        _row_by_title(calculator, 'Ручки', count),
        _row_by_title(calculator, 'Замок', count),
        _row_by_title(calculator, 'Петли', count),
    ]
    if segment_key == 'business':
        materials.append(_row_by_title(calculator, 'Уплотнители / стопоры', count))
    return _build_result(calculator, materials, form_data, count, count, 1, segment_key, segment, f"{calculator['title']} · {count} шт · {segment['label']}")


def _calculate_teplyy_pol(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    floor_type = form_data.get('type', 'mat')
    segment_key, segment = _get_segment(form_data.get('segment', 'comfort'), calculator)
    if floor_type == 'cable':
        cable_ratio = {'economy': 8, 'comfort': 9, 'business': 10}[segment_key]
        materials = [
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
        materials = [
            _row_by_title(calculator, 'Труба PE-RT / PEX 16 мм', area * pipe_ratio),
            _row_by_title(calculator, 'Теплоизоляция', area * 1.05),
            _row_by_title(calculator, 'Демпферная лента', area * 0.8),
            _row_by_title(calculator, 'Скобы / крепёж трубы', area * staples_ratio),
            _row_by_title(calculator, 'Коллектор', contours),
            _row_by_title(calculator, 'Коллекторный шкаф', 1),
            _row_by_title(calculator, 'Фитинги', contours),
        ]
        if segment_key == 'business':
            materials.append(_row_by_title(calculator, 'Смесительный узел', 1))
    else:
        materials = [
            _row_by_title(calculator, 'Нагревательный мат', area * 1.05),
            _row_by_title(calculator, 'Терморегулятор', 1),
            _row_by_title(calculator, 'Датчик температуры пола', 1),
            _row_by_title(calculator, 'Гофра под датчик', max(2, area * 0.25)),
            _row_by_title(calculator, 'Теплоизоляция', area * 1.05),
        ]
    return _build_result(calculator, materials, form_data, area, 1, 1, segment_key, segment, f"{calculator['title']} · {area:g} м² · {floor_type}")


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
    saved_list = '\n'.join(f"{material['title']} — {material['quantity']} {material['unit']}" for material in result_materials)
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
        'whatsapp_text': f"ESEPTEP: {summary}. Материалы:\n{saved_list}\nЦены уточняются у поставщиков.",
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
    return {'title': material['title'], 'quantity': _round_quantity(quantity), 'unit': material['unit'], 'reference_price': material['reference_price']}


def _row_by_title(calculator, title, quantity):
    material = next(item for item in calculator['materials'] if item['title'] == title)
    return _row(material, quantity)


def _get_segment(value, calculator):
    segment_key = SEGMENT_ALIASES.get(value, value) or 'comfort'
    if segment_key not in SEGMENTS:
        segment_key = 'comfort'
    return segment_key, calculator.get('segments', SEGMENTS).get(segment_key, SEGMENTS['comfort'])


def _plain_segment():
    return PLAIN_REFERENCE


def _round_quantity(value):
    if value <= 0:
        return 0
    if value < 10:
        return round(value, 1)
    return round(value)
