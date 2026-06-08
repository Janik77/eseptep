"""Server-side calculator services for ESEPTEP."""

from accounts.models import Calculation, ClientProject

from .definitions import SEGMENTS


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
    area = to_float(form_data.get('area'), 0)
    thickness = to_float(form_data.get('thickness'), 1)
    rooms = max(1, int(to_float(form_data.get('rooms'), 1)))
    segment_key = form_data.get('segment', 'comfort')
    segment = calculator.get('segments', SEGMENTS).get(segment_key, SEGMENTS['comfort'])

    complexity = _material_complexity(thickness, rooms)
    materials = []
    reference_total = 0

    for material in calculator['materials']:
        quantity = round(area * material['ratio'] * complexity, 1)
        reference_price = round(material['reference_price'] * segment['material'])
        reference_row_total = round(quantity * reference_price)
        reference_total += reference_row_total
        materials.append({
            'title': material['title'],
            'quantity': quantity,
            'unit': material['unit'],
            'reference_price': reference_price,
            'reference_total': reference_row_total,
            # Backward-compatible aliases for existing templates/dashboard data.
            'price': reference_price,
            'total': reference_row_total,
        })

    reference_labor_total = round(area * segment['labor'] * complexity)
    reference_grand_total = reference_total + reference_labor_total
    saved_list = '\n'.join(
        f"{material['title']} — {material['quantity']} {material['unit']}"
        for material in materials
    )

    return {
        'materials': materials,
        'materials_count': len(materials),
        'reference_total': reference_total,
        'reference_labor_total': reference_labor_total,
        'reference_grand_total': reference_grand_total,
        # Backward-compatible totals for saved calculations and dashboards.
        'materials_total': reference_total,
        'labor_total': reference_labor_total,
        'grand_total': reference_grand_total,
        'segment_label': segment['label'],
        'summary': f"{calculator['title']} · {area:g} {calculator['unit']} · {rooms} комн.",
        'saved_list': saved_list,
        'whatsapp_text': (
            f"ESEPTEP: {calculator['title']} — {area:g} {calculator['unit']}. "
            f"Материалы:\n{saved_list}\nЦены уточняются у поставщиков."
        ),
        'warning': calculator.get('warning'),
        'master_template_items': calculator.get('master_template_items', []),
        'meta': {
            'area': area,
            'thickness': thickness,
            'rooms': rooms,
            'segment': segment_key,
        },
    }


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
        },
    )
    return project, calculation


def _material_complexity(thickness, rooms):
    """Shared quantity coefficient for current calculators.

    Thickness and room count slightly increase material reserve. The formula is
    intentionally centralized here to avoid calculations in templates or JS.
    """
    return 1 + max(thickness - 1, 0) * 0.08 + max(rooms - 1, 0) * 0.035
