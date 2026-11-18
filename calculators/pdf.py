"""Owner-only export of saved snapshots. Never recalculate or fetch live prices."""
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

from accounts.identifiers import parse_positive_id
from accounts.models import Calculation
from .definitions import CALCULATORS_BY_SLUG


def number(value):
    try:
        n = Decimal(str(value).replace(',', '.'))
        if not n.is_finite():
            return str(value)
        text = format(n, 'f')
        return (text.rstrip('0').rstrip('.') if '.' in text else text).replace('.', ',')
    except (InvalidOperation, TypeError, ValueError):
        return str(value)


def money(value):
    return f'{number(value)} ₸'


def build_saved_pdf(calculation):
    fonts = Path(__file__).with_name('pdf_fonts')
    for suffix, file in [('', 'DejaVuSans.ttf'), ('-Bold', 'DejaVuSans-Bold.ttf')]:
        if 'ESEPTEP' + suffix not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('ESEPTEP' + suffix, str(fonts / file)))
    styles = {
        'body': ParagraphStyle('body', fontName='ESEPTEP', fontSize=9, leading=14, textColor=colors.HexColor('#243449'), spaceAfter=6),
        'small': ParagraphStyle('small', fontName='ESEPTEP', fontSize=8, leading=12, textColor=colors.HexColor('#4b5d73'), spaceAfter=5),
        'title': ParagraphStyle('title', fontName='ESEPTEP-Bold', fontSize=20, leading=27, textColor=colors.HexColor('#2e609f'), spaceAfter=12),
        'heading': ParagraphStyle('heading', fontName='ESEPTEP-Bold', fontSize=12, leading=18, spaceBefore=13, spaceAfter=8),
        'right': ParagraphStyle('right', fontName='ESEPTEP', fontSize=9, leading=14, alignment=TA_RIGHT),
    }
    def p(text, style='body'):
        return Paragraph(escape(str(text)).replace('\n', '<br/>'), styles[style])
    def table(rows, widths):
        result = Table(rows, colWidths=widths, repeatRows=1, hAlign='LEFT')
        result.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'), ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3fa')),
            ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#becbdb')),
            ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dfe6ee')),
            ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
            ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ]))
        return result

    data = calculation.result_data or {}
    definition = CALCULATORS_BY_SLUG.get(calculation.calculator_slug, {})
    items = [p('ESEPTEP.KZ', 'title'), p(_('Сохранённая смета'), 'heading'),
             p(_(definition.get('title', calculation.calculator_slug))),
             p(f"{_('Проект:')} {calculation.project.title}"),
             p(f"№ {calculation.pk} · {timezone.localtime(calculation.created_at):%d.%m.%Y %H:%M}"),
             p(_('Это сохранённые данные расчёта, без пересчёта по текущим ценам.'), 'small')]
    variant = data.get('selected_variant_label')
    if variant:
        items.append(p(f"{_('Вариант:')} {_(variant)}"))
    items.append(p(_('Параметры'), 'heading'))
    inputs = data.get('input', {})
    for field in definition.get('fields', []):
        value = inputs.get(field['name'])
        if value is None:
            continue
        if field.get('type') == 'select':
            value = next((_(option['label']) for option in field.get('options', []) if option['value'] == value), str(value))
        else:
            value = number(value)
        items.append(p(f"{_(field['label'])}: {value} {_(field.get('unit', ''))}".strip()))
    if 'area' not in inputs:
        items.append(p(f"{_('Площадь пола, м²')}: {number(calculation.area_m2)}"))
    source = data.get('plan_source') or {}
    if source:
        items.append(p(_('Подтверждённая площадь пола из плана'), 'heading'))
        items.append(p(f"{source.get('name', '')} · {number(source.get('area', ''))} м²"))
    items.append(p(_('Предварительная оценка калькулятора'), 'heading'))
    material_rows = [[p(_('Материал')), p(_('Кол-во'), 'right'), p(_('Сумма, ₸'), 'right')]]
    for row in data.get('materials', []):
        label = _(row.get('title', ''))
        basis = row.get('quantity_basis') or {}
        if basis.get('mode') == 'ceiling':
            label += '\n' + _('К закупке: %(raw)s → %(quantity)s %(unit)s (округление вверх)') % {
                'raw': number(basis['unrounded']), 'quantity': number(row.get('quantity')), 'unit': _(row.get('unit', ''))}
        material_rows.append([p(label), p(f"{number(row.get('quantity', ''))} {_(row.get('unit', ''))}", 'right'),
                              p(money(row.get('total', row.get('reference_total', ''))), 'right')])
    items.append(table(material_rows, [296, 90, 113]))
    items.append(Spacer(1,10))
    items.append(p(f"{_('Итого:')} {money(calculation.grand_total)}", 'heading'))
    items.append(p(_('Цены справочные. Это не коммерческое предложение.'), 'small'))
    quote = data.get('admin_quote')
    quote_start = len(items)
    items.append(p(_('Расчёт по прайсу магазина'), 'heading'))
    if quote:
        items.extend([p(quote.get('store_name', '')), p(f"{_('Версия:')} {quote.get('version', '')} · {quote.get('price_date', '')}"),
                      p(quote.get('source_note', ''), 'small'),
                      p(_('Цены найдены для %(priced)s из %(required)s позиций') % {'priced':quote.get('coverage',0),'required':quote.get('required',0)})])
        quote_rows = [[p(_('Материал')), p(_('Кол-во'), 'right'), p(_('Сумма, ₸'), 'right')]]
        for row in quote.get('rows', []):
            quote_rows.append([p(_(row.get('material_title', ''))), p(f"{number(row.get('quantity', ''))} {_(row.get('unit_label', ''))}", 'right'), p(money(row.get('line_total', '')), 'right')])
        for row in quote.get('missing', []):
            quote_rows.append([p(_(row.get('material_title',''))),p(f"{number(row.get('quantity',''))} {_(row.get('unit_label',''))}", 'right'),p(_('Цена по запросу'), 'right')])
        items.append(table(quote_rows, [296,90,113]))
        items.append(p(_('Материалы по прайсу магазина') if quote.get('complete') else _('Неполная сумма — только позиции с ценой'), 'heading'))
        items.append(p(money(quote.get('subtotal', '')), 'heading'))
        items.append(p(_('Без работ и доставки. Наличие и совместимость материалов требуют подтверждения магазина.'), 'small'))
    else:
        items.append(p(_('Опубликованный прайс магазина не настроен. Показанные выше цены остаются справочными, это не предложение магазина.')))
    items[quote_start:] = [KeepTogether(items[quote_start:])]
    result = BytesIO()
    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont('ESEPTEP',8);canvas.setFillColor(colors.HexColor('#4b5d73'))
        canvas.drawString(48,25,'ESEPTEP.KZ');canvas.drawRightString(A4[0]-48,25,str(doc.page));canvas.restoreState()
    doc = SimpleDocTemplate(result, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=40, bottomMargin=42,
                            title='ESEPTEP - '+_('Сохранённая смета'), author='ESEPTEP')
    doc.build(items,onFirstPage=footer,onLaterPages=footer)
    return result.getvalue()


@login_required
@require_GET
def saved_pdf(request, calculation_id):
    pk = parse_positive_id(calculation_id)
    if pk is None:
        raise Http404
    calculation = get_object_or_404(Calculation.objects.select_related('project'),pk=pk,project__user=request.user)
    response = HttpResponse(build_saved_pdf(calculation), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="eseptep-estimate-{calculation.pk}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
