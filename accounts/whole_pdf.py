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
    # The linked saved estimate is the immutable source; never re-read the active price book.
    catalog_version = request.whole_estimate.snapshot.get('price_version')
    if catalog_version:
        rows.append(p(tr('Справочно, редакция каталога исходной сметы ESEPTEP: ',
                         'Анықтама: ESEPTEP бастапқы сметасының каталог нұсқасы: ') + catalog_version))
        rows.append(p(tr('Цены предложения указаны магазином отдельно.',
                         'Ұсыныс бағаларын дүкен бөлек көрсеткен.')))
    statuses={'available':tr('В наличии','Бар'),'unknown':tr('Наличие не подтверждено','Бар-жоғы расталмаған'),'unavailable':tr('Нет в наличии','Жоқ')}
    for line in s['lines']:
        price=line['unit_price'] if line['unit_price'] is not None else tr('уточнить','нақтылау')
        amount=line['line_total'] if line['line_total'] is not None else tr('не подтверждено','расталмаған')
        quantity = line['quantity'] + ' ' + line['unit']
        if line.get('purchase_unit') == 'pack':
            pack = tr('упак.', 'қапт.')
            quantity = f"{line['purchase_quantity']} {pack} ({line['pack_coverage']} {line['unit']} / {pack}; {tr('нужно', 'қажет')} {quantity})"
            if line.get('purchase_covered_quantity'):
                quantity += f"; {tr('к закупке', 'сатып алу')} {line['purchase_covered_quantity']} {line['unit']}"
        rows.append(p(f"{line['title']}: {quantity} × {price} ₸; {statuses[line['availability']]}; {amount} ₸"))
    rows += [p((tr('Сумма предложения: ','Ұсыныстың жалпы сомасы: ') if s['total'] is not None else tr('Подтверждённая часть: ','Расталған бөлігі: '))+(s['confirmed_subtotal']+' ₸' if s['confirmed_subtotal'] is not None else tr('пока нет подтверждённых цен','расталған баға әзірге жоқ'))),
             p(tr('Неподтверждённых позиций: ','Расталмаған позициялар: ')+str(s['unconfirmed'])),p(s['message'])]
    out=BytesIO();SimpleDocTemplate(out).build(rows);return out.getvalue()
