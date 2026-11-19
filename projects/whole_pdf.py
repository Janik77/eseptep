"""PDF from saved immutable snapshot; no reprice or external requests."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from django.utils.translation import get_language


def build_pdf(estimate):
    font = Path(__file__).resolve().parent.parent / 'calculators/pdf_fonts/DejaVuSans.ttf'
    if 'WholePlan' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('WholePlan', str(font)))
    style = ParagraphStyle('body', fontName='WholePlan', fontSize=10, leading=15, spaceAfter=8)
    kk = (get_language() or '').startswith('kk')
    def tr(ru, kz): return kz if kk else ru
    def p(text): return Paragraph(escape(str(text)), style)
    s = estimate.snapshot
    items = [p('ESEPTEP · '+tr('Смета материалов пола', 'Еден материалдарының сметасы')),
             p(f"#{estimate.pk} · {s['version']} · {estimate.created_at.isoformat()}"),
             p(tr('Предварительно. Работы, стены и потолки не включены. Неизвестные цены не равны нулю.',
                  'Алдын ала. Жұмыс, қабырға және төбе кірмейді. Белгісіз баға нөл емес.')),
             p(tr('Источник цен: ', 'Баға көзі: ')+str(s.get('price_source') or tr('не указан','көрсетілмеген')))]
    for room in s['rooms']:
        items.append(p(f"{room['name']} · {room['area'] or '?'} м² · {room['finish']}"))
        items.append(p(str(room.get('visual_evidence') or room.get('evidence') or '')))
    items.append(Spacer(1, 12))
    for row in s['procurement']:
        price = row['unit_price'] if row['unit_price'] is not None else tr('уточнить цену','бағаны нақтылау')
        total = row['line_total'] if row['line_total'] is not None else '?'
        items.append(p(f"{row['title']}: {row['quantity']} {row['unit']} × {price} = {total} ₸"))
    items.extend([p(tr('Подытог позиций с ценой: ', 'Бағасы бар позициялар жиыны: ')+s['priced_subtotal']+' ₸'),
                  p(tr('Окончательная стоимость неизвестна. Согласуйте работы и недостающие данные.',
                       'Соңғы құны белгісіз. Жұмысты және жетіспейтін деректерді келісіңіз.'))])
    output = BytesIO()
    SimpleDocTemplate(output, pagesize=A4, rightMargin=42, leftMargin=42).build(items)
    return output.getvalue()
