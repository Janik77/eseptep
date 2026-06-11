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
        _row_by_title(calculator, 'Очки защитные', max(1, area / 35)),
        _row_by_title(calculator, 'Лом / монтажка', max(1, area / 60)),
        _row_by_title(calculator, 'Шпатель / скребок', max(1, area / 25)),
        _row_by_title(calculator, 'Алмазный диск / расходный диск', max(1, area / 25)),
        _row_by_title(calculator, 'Вывоз мусора / машина', max(1, area / 45)),
        _row_by_title(calculator, 'Контейнер для строительного мусора', max(1, area / 45)),
    ]
    return _build_result(calculator, materials, form_data, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {demolition_type}")


def _calculate_elektrika(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    lighting_lines = 2
    socket_groups = 5
    room_extra_groups = max(0, rooms - 1)
    sockets = max(10, area * 0.32 + rooms * 4)
    switches = max(4, rooms * 2 + 2)
    junction_boxes = max(3, rooms + area / 25)
    cable_25 = area * 3.2 + rooms * 12
    cable_15 = area * 1.8 + rooms * 8
    cable_6 = max(12, area * 0.18)
    materials = [
        _row_by_title(calculator, 'Кабель ВВГнг-LS 3×2.5', cable_25),
        _row_by_title(calculator, 'Кабель ВВГнг-LS 3×1.5', cable_15),
        _row_by_title(calculator, 'Кабель ВВГнг-LS 3×6', cable_6),
        _row_by_title(calculator, 'Подрозетники', max(12, sockets + switches)),
        _row_by_title(calculator, 'Распредкоробки', junction_boxes),
        _row_by_title(calculator, 'Розетки', sockets),
        _row_by_title(calculator, 'Выключатели', switches),
        _row_by_title(calculator, 'Автомат 10А', lighting_lines),
        _row_by_title(calculator, 'Автомат 16А', socket_groups + room_extra_groups),
        _row_by_title(calculator, 'Автомат 25А', 1),
        _row_by_title(calculator, 'Автомат 32А', 1),
        _row_by_title(calculator, 'УЗО', max(2, rooms)),
        _row_by_title(calculator, 'Дифавтомат', max(1, rooms // 2)),
        _row_by_title(calculator, 'Электрощит', 1),
        _row_by_title(calculator, 'Гофра 16 мм', cable_15 * 0.55),
        _row_by_title(calculator, 'Гофра 20 мм', (cable_25 + cable_6) * 0.35),
        _row_by_title(calculator, 'Клипсы для гофры', max(30, area * 1.2)),
        _row_by_title(calculator, 'Дюбель-гвоздь / анкер', max(40, area * 1.1)),
        _row_by_title(calculator, 'Гвозди Toua / газовый пистолет', max(30, area * 0.7)),
        _row_by_title(calculator, 'Реле напряжения', 1),
        _row_by_title(calculator, 'DIN-рейка', 1),
        _row_by_title(calculator, 'Нулевая шина', 1),
        _row_by_title(calculator, 'Заземляющая шина', 1),
        _row_by_title(calculator, 'Клеммы WAGO', max(20, junction_boxes * 6)),
        _row_by_title(calculator, 'Интернет кабель UTP', area * 0.8 + rooms * 8),
        _row_by_title(calculator, 'ТВ кабель', area * 0.45 + rooms * 5),
        _row_by_title(calculator, 'Кабель домофона', max(10, area * 0.2)),
        _row_by_title(calculator, 'Изолента', max(2, area / 35)),
        _row_by_title(calculator, 'Стяжки пластиковые', max(50, area * 1.5)),
        _row_by_title(calculator, 'Алебастр / гипс', max(5, area * 0.18)),
    ]
    return _build_result(calculator, materials, form_data, area, rooms, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {rooms} комн.")


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
    thickness_factor = max(thickness, 0.5) / 2
    materials = [
        _row_by_title(calculator, 'Штукатурка гипсовая 30 кг', area * 0.95 * thickness_factor),
        _row_by_title(calculator, 'Грунтовка 10 кг', max(1, area * 0.018)),
        _row_by_title(calculator, 'Бетоноконтакт 15 кг', max(1, area * 0.012)),
        _row_by_title(calculator, 'Армировочная сетка', area * 1.05),
        _row_by_title(calculator, 'Маяк железный 3 м', area * 0.22),
        _row_by_title(calculator, 'Алюминиевый уголок 90°', max(4, area * 0.08)),
        _row_by_title(calculator, 'Правило 1,5 м', 1),
        _row_by_title(calculator, 'Правило 3 м', 1),
        _row_by_title(calculator, 'Шпатель 15 см', 2),
        _row_by_title(calculator, 'Валик', 1),
        _row_by_title(calculator, 'Ведро строительное', max(2, area / 40)),
        _row_by_title(calculator, 'Бумажный малярный скотч', max(1, area / 25)),
        _row_by_title(calculator, 'Плёнка защитная', area * 1.05),
        _row_by_title(calculator, 'Монтажная пена', max(1, area / 50)),
        _row_by_title(calculator, 'Мусорные мешки', area / 5),
    ]
    return _build_result(calculator, materials, form_data, area, 1, thickness, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {thickness:g} см")


def _calculate_gipsokarton(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    construction_type = form_data.get('construction_type', 'ceiling')
    room_factor = 1 + max(rooms - 1, 0) * 0.08
    ceiling = construction_type == 'ceiling'
    partition = construction_type == 'partition'
    box = construction_type == 'box'
    sheet_factor = 0.38 if ceiling else 0.76 if partition else 0.55
    materials = [
        _row_by_title(calculator, 'Гипсокартон стеновой 12.5 мм', 0 if ceiling else area * sheet_factor),
        _row_by_title(calculator, 'Гипсокартон потолочный 9.5 мм', area * sheet_factor if ceiling else 0),
        _row_by_title(calculator, 'Гипсокартон влагостойкий', area * 0.12 if partition else 0),
        _row_by_title(calculator, 'Профиль CD 60×27', area * (1.4 if ceiling or box else 0.4) * room_factor),
        _row_by_title(calculator, 'Профиль UD 27×28', area * (0.45 if ceiling or box else 0.15) * room_factor),
        _row_by_title(calculator, 'Профиль UW 50×40', area * (0.5 if partition else 0)),
        _row_by_title(calculator, 'Профиль CW 50×50', area * (1.2 if partition else 0)),
        _row_by_title(calculator, 'Профиль UW 75×40', area * (0.25 if partition else 0)),
        _row_by_title(calculator, 'Профиль CW 75×50', area * (0.6 if partition else 0)),
        _row_by_title(calculator, 'Подвес прямой', area * (0.8 if ceiling else 0.35) * room_factor),
        _row_by_title(calculator, 'Краб одноуровневый', area * (0.45 if ceiling else 0.15)),
        _row_by_title(calculator, 'Соединитель CD профиля', area * 0.18),
        _row_by_title(calculator, 'Соединитель двухуровневый CD 60×27', area * (0.12 if ceiling else 0.04)),
        _row_by_title(calculator, 'Дюбель-гвоздь', area * 1.8 * room_factor),
        _row_by_title(calculator, 'Саморезы ГКЛ', area * 18 * room_factor),
        _row_by_title(calculator, 'Саморезы-клопы', area * 8 * room_factor),
        _row_by_title(calculator, 'Шумоизоляция', area if partition else 0),
        _row_by_title(calculator, 'Демпферная лента', max(1, area * 0.45 * room_factor)),
    ]
    return _build_result(calculator, materials, form_data, area, rooms, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {rooms} комн. · {construction_type}")


def _calculate_nalivnoy_pol(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    thickness = to_float(form_data.get('thickness'), 5)
    mixture_bags = area * max(thickness, 1) * 1.7 / 25
    perimeter = 4 * sqrt(area) if area > 0 else 0
    materials = [
        _row_by_title(calculator, 'Наливной пол 25 кг', mixture_bags),
        _row_by_title(calculator, 'Грунтовка', area * 0.12),
        _row_by_title(calculator, 'Демпферная лента', perimeter),
        _row_by_title(calculator, 'Маяк-фиксатор', max(4, area * 0.35)),
        _row_by_title(calculator, 'Ведро строительное', max(1, area / 40)),
        _row_by_title(calculator, 'Валик', 1),
        _row_by_title(calculator, 'Игольчатый валик', max(1, area / 35)),
        _row_by_title(calculator, 'Обувь шиповая', 1),
        _row_by_title(calculator, 'Степлер строительный', 1),
        _row_by_title(calculator, 'Скобы для степлера', max(1, area / 20)),
        _row_by_title(calculator, 'Мусорные мешки', area / 5),
    ]
    return _build_result(calculator, materials, form_data, area, 1, thickness, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {thickness:g} мм")


def _calculate_plitka(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    zone_type = form_data.get('zone_type', 'floor')
    tile_format = form_data.get('tile_format', '60x60')
    reserve_factor = {'floor': 1.07, 'walls': 1.1, 'bathroom': 1.12, 'backsplash': 1.15}.get(zone_type, 1.08)
    is_large_format = tile_format == '120x120'
    tile_area = area * reserve_factor
    edge_length = 4 * sqrt(area) if area > 0 else 0
    wet_zone = zone_type == 'bathroom'
    backsplash = zone_type == 'backsplash'
    materials = [
        _row_by_title(calculator, 'Плитка / кафель', 0 if is_large_format else tile_area),
        _row_by_title(calculator, 'Керамогранит', tile_area if is_large_format else 0),
        _row_by_title(calculator, 'Гидроизоляция', area * 1.05 if wet_zone else 0),
        _row_by_title(calculator, 'Клей плиточный 25 кг', 0 if is_large_format else area * 0.32),
        _row_by_title(calculator, 'Клей для крупного формата 25 кг', area * 0.38 if is_large_format else 0),
        _row_by_title(calculator, 'Фуга', 0 if wet_zone else area * (0.06 if backsplash else 0.08)),
        _row_by_title(calculator, 'Эпоксидная фуга', area * 0.08 if wet_zone else 0),
        _row_by_title(calculator, 'СВП', max(1, area * (0.08 if is_large_format else 0.04))),
        _row_by_title(calculator, 'Крестики', 0 if is_large_format else max(1, area * 0.04)),
        _row_by_title(calculator, 'Профиль / уголок для плитки', max(1, edge_length * (0.35 if backsplash else 0.2))),
        _row_by_title(calculator, 'Силикон санитарный', max(1, area / 20) if wet_zone or backsplash else 1),
        _row_by_title(calculator, 'Плиткорезный диск', max(1, area / 35)),
        _row_by_title(calculator, 'Губка / ведро / мелкие расходники', max(1, area / 30)),
        _row_by_title(calculator, 'Мусорные мешки', area / 5),
    ]
    return _build_result(calculator, materials, form_data, area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {zone_type} · {tile_format}")


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
        _row_by_title(calculator, 'Угол внутренний', max(1, perimeter / 18)),
        _row_by_title(calculator, 'Угол наружный', max(1, perimeter / 24)),
        _row_by_title(calculator, 'Соединитель плинтуса', max(1, perimeter / 16)),
        _row_by_title(calculator, 'Заглушка плинтуса', max(2, perimeter / 18)),
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
        _row_by_title(calculator, 'Базовая шпаклёвка 25 кг', wall_area * 0.12),
        _row_by_title(calculator, 'Финишная шпаклёвка 20 кг', wall_area * 0.08),
        _row_by_title(calculator, 'Финишная полимерная шпаклёвка 25 кг', wall_area * 0.06),
        _row_by_title(calculator, 'Грунтовка', wall_area * 0.16),
        _row_by_title(calculator, 'Бумажный малярный скотч', max(1, wall_area / 25)),
        _row_by_title(calculator, 'Шкурка / сетка P80', max(1, wall_area / 45)),
        _row_by_title(calculator, 'Шкурка / сетка P120', max(1, wall_area / 45)),
        _row_by_title(calculator, 'Шкурка / сетка P180', max(1, wall_area / 45)),
        _row_by_title(calculator, 'Валик', 1),
        _row_by_title(calculator, 'Кисть', 1),
        _row_by_title(calculator, 'Лоток для краски', 1),
        _row_by_title(calculator, 'Плёнка защитная', floor_area * 1.05),
        _row_by_title(calculator, 'Мусорные мешки', floor_area / 5),
    ]
    if finish_type == 'wallpaper':
        materials.extend([
            _row_by_title(calculator, 'Обои', wall_area / 5),
            _row_by_title(calculator, 'Обойный клей', max(1, wall_area / 25)),
        ])
    else:
        materials.extend([
            _row_by_title(calculator, 'Стеклохолст 1×50 м', wall_area * 1.05),
            _row_by_title(calculator, 'Клей для стеклохолста', wall_area * 0.18),
            _row_by_title(calculator, 'Краска', wall_area * 0.22),
            _row_by_title(calculator, 'Грунт-краска', wall_area * 0.18),
        ])
    return _build_result(calculator, materials, {**form_data, 'wall_area': wall_area, 'ceiling_included': False}, floor_area, 1, 1, 'comfort', _plain_segment(), f"{calculator['title']} · стены {wall_area:g} м² · потолок не включён")


def _calculate_natyazhnoy_potolok(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    perimeter = 4 * sqrt(area) if area > 0 else 0
    light_points = max(rooms, round(area / 7))
    profile_factor = 1 + max(rooms - 1, 0) * 0.08
    materials = [
        _row_by_title(calculator, 'ПВХ полотно', area),
        _row_by_title(calculator, 'Тканевый потолок', 0),
        _row_by_title(calculator, 'ПВХ багет / профиль', perimeter * profile_factor),
        _row_by_title(calculator, 'Алюминиевый профиль', perimeter * 0.25 * profile_factor),
        _row_by_title(calculator, 'Теневой профиль', perimeter * 0.12),
        _row_by_title(calculator, 'Парящий профиль', perimeter * 0.08),
        _row_by_title(calculator, 'Декоративная вставка', perimeter * profile_factor),
        _row_by_title(calculator, 'Термокольца', light_points),
        _row_by_title(calculator, 'Платформы под светильники', light_points),
        _row_by_title(calculator, 'Точечные светильники', light_points),
        _row_by_title(calculator, 'Кабель для освещения', max(10, area * 1.5)),
        _row_by_title(calculator, 'Световая линия / LED-профиль', max(0, area / 12)),
        _row_by_title(calculator, 'LED-лента', max(0, area / 12)),
        _row_by_title(calculator, 'Блок питания LED', max(1, area / 40)),
        _row_by_title(calculator, 'Магнитный трек', max(0, rooms * 0.5)),
        _row_by_title(calculator, 'Трековые светильники', max(0, rooms * 2)),
        _row_by_title(calculator, 'Скрытый карниз / ниша', max(0, rooms * 1.5)),
    ]
    return _build_result(calculator, materials, form_data, area, rooms, 1, 'comfort', _plain_segment(), f"{calculator['title']} · {area:g} м² · {rooms} комн.")


def _calculate_dveri(calculator, form_data):
    count = max(1, int(to_float(form_data.get('count'), 1)))
    materials = [
        _row_by_title(calculator, 'Дверное полотно', count),
        _row_by_title(calculator, 'Коробка дверная', count),
        _row_by_title(calculator, 'Доборы', count),
        _row_by_title(calculator, 'Наличники', count),
        _row_by_title(calculator, 'Ручки', count),
        _row_by_title(calculator, 'Замок / защёлка', count),
        _row_by_title(calculator, 'Магнитный замок', count),
        _row_by_title(calculator, 'Петли', count),
        _row_by_title(calculator, 'Скрытые петли', count),
        _row_by_title(calculator, 'Уплотнитель', count),
        _row_by_title(calculator, 'Стопор дверной', count),
        _row_by_title(calculator, 'Пена монтажная', max(1, count)),
        _row_by_title(calculator, 'Силикон / герметик', max(1, count)),
    ]
    return _build_result(
        calculator,
        materials,
        form_data,
        count,
        count,
        1,
        'comfort',
        _plain_segment(),
        f"{calculator['title']} · {count} шт",
    )


def _calculate_teplyy_pol(calculator, form_data):
    area = to_float(form_data.get('area'), 0)
    floor_type = form_data.get('type', 'mat')
    if floor_type == 'cable':
        materials = [
            _row_by_title(calculator, 'Нагревательный кабель', area * 9),
            _row_by_title(calculator, 'Монтажная лента для кабеля', area * 1.5),
            _row_by_title(calculator, 'Терморегулятор', 1),
            _row_by_title(calculator, 'Wi-Fi терморегулятор', 1),
            _row_by_title(calculator, 'Датчик температуры пола', 1),
            _row_by_title(calculator, 'Гофра под датчик', max(2, area * 0.25)),
            _row_by_title(calculator, 'Теплоизоляция под тёплый пол', area * 1.05),
        ]
    elif floor_type == 'water':
        contours = max(1, area / 15)
        materials = [
            _row_by_title(calculator, 'Труба PE-RT / PEX 16 мм', area * 6),
            _row_by_title(calculator, 'Теплоизоляция под тёплый пол', area * 1.05),
            _row_by_title(calculator, 'Демпферная лента', area * 0.8),
            _row_by_title(calculator, 'Скобы / крепёж трубы', area * 4),
            _row_by_title(calculator, 'Коллектор', contours),
            _row_by_title(calculator, 'Коллекторный шкаф', 1),
            _row_by_title(calculator, 'Фитинги и соединители', contours),
            _row_by_title(calculator, 'Смесительный узел', 1),
        ]
    else:
        materials = [
            _row_by_title(calculator, 'Нагревательный мат', area * 1.05),
            _row_by_title(calculator, 'Терморегулятор', 1),
            _row_by_title(calculator, 'Wi-Fi терморегулятор', 1),
            _row_by_title(calculator, 'Датчик температуры пола', 1),
            _row_by_title(calculator, 'Гофра под датчик', max(2, area * 0.25)),
            _row_by_title(calculator, 'Теплоизоляция под тёплый пол', area * 1.05),
        ]
    return _build_result(
        calculator,
        materials,
        form_data,
        area,
        1,
        1,
        'comfort',
        _plain_segment(),
        f"{calculator['title']} · {area:g} м² · {floor_type}",
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
