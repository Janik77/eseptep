"""Immutable supplier offer PDF, never reads live prices."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph
from .whole_views import tr


def offer_pdf(request, offer):
    if 'WholeOffer' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('WholeOffer',str(Path(__file__).resolve().parent.parent/'calculators/pdf_fonts/DejaVuSans.ttf')))
    style=ParagraphStyle('body',fontName='WholeOffer',fontSize=10,leading=15,spaceAfter=8)
    def p(text): return Paragraph(escape(str(text)),style)
    s=offer.snapshot;r=request.request_snapshot
    rows=[p(tr('Предложение тестового магазина','Тест дүкенінің ұсынысы')),
        p(r['project_title']),p(r['supplier_name']),p(offer.created_at.isoformat()),
        p(tr('Это не заказ и не обязательство купить.','Бұл тапсырыс немесе сатып алу міндеттемесі емес.'))]
    statuses={'available':tr('В наличии','Бар'),'unknown':tr('Наличие не подтверждено','Бар-жоғы расталмаған'),'unavailable':tr('Нет в наличии','Жоқ')}
    for line in s['lines']:
        price=line['unit_price'] if line['unit_price'] is not None else tr('уточнить','нақтылау')
        amount=line['line_total'] if line['line_total'] is not None else tr('не подтверждено','расталмаған')
        rows.append(p(f"{line['title']}: {line['quantity']} {line['unit']} × {price} ₸; {statuses[line['availability']]}; {amount} ₸"))
    rows += [p(tr('Подтверждённая часть: ','Расталған бөлігі: ')+s['confirmed_subtotal']+' ₸'),
             p(tr('Неподтверждённых позиций: ','Расталмаған позициялар: ')+str(s['unconfirmed'])),p(s['message'])]
    out=BytesIO();SimpleDocTemplate(out).build(rows);return out.getvalue()
