"""Generate downloads from a selected immutable revision, never from live AI."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate

from .contract_copy import CLAUSES, clause_label, kind_label, missing, status, word


def headings(language):
    def w(ru, kk):
        return word(language, ru, kk)
    return {
        'date':w('Дата договора', 'Шарт күні'),
        'customer':w('Заказчик', 'Тапсырыс беруші'),
        'provider':w('Исполнитель', 'Орындаушы'),
        'total':w('Сумма', 'Сома'),
        'starts_on':w('Начало', 'Басталуы'),
        'ends_on':w('Окончание', 'Аяқталуы'),
        'identifiers':w('Реквизиты', 'Деректемелер'),
        'offer':w('Согласованное предложение', 'Келісілген ұсыныс'),
    }


def change_label(lang, kind):
    return word(lang, *{
        'merged':('Объединено', 'Біріктірілді'), 'omit':('Предложено убрать', 'Алып тастау ұсынылды'),
        'conflict':('Нужно решить: противоречие', 'Шешу қажет: қайшылық'),
        'review':('Сверьте с оригиналом', 'Түпнұсқамен салыстырыңыз'),
    }[kind])


def report(contract, rev):
    """Shared screen / DOCX / PDF representation; always flags proposed facts."""
    lang, snap, details = contract.language, contract.confirmed_snapshot, rev.details
    q = missing(lang)
    rows = [('title', kind_label(lang, contract.agreement.kind)),
            ('body', f'{status(lang)} · ESEPTEP.KZ · {word(lang, "Редакция", "Нұсқа")} {rev.revision}'),
            ('body', word(lang, 'Демонстрационный документ. Не подписан.', 'Сынақ құжаты. Қол қойылмаған.'))]
    labels = headings(lang)
    for key in ('offer', 'date', 'customer', 'provider', 'total', 'starts_on', 'ends_on', 'identifiers'):
        value = details.get(key) or snap.get(key)
        suffix = ''
        if key == 'total':
            if value:
                value = f'{value} ₸'
            if key in details and details[key] != snap.get(key):
                suffix = ' · ' + word(lang,'предложено вручную, не согласовано','қолмен ұсынылған, келісілмеген')
                if snap.get(key):
                    suffix += f' ({word(lang, "согласовано", "келісілген")}: {snap[key]} ₸)'
        rows.append(('body', f'{labels[key]}: {value or q}{suffix}'))
    if snap['description'] or snap['lines']:
        rows.append(('heading', word(lang, 'Согласованный состав', 'Келісілген құрам')))
        if snap['description']:
            rows.append(('body', snap['description']))
        for line in snap['lines']:
            key = line['id']
            proposed = details.get('quantities', {}).get(key)
            remainder = (f' · {word(lang, "предложено", "ұсынылған")}: {proposed} {line["unit"]}' if proposed else '')
            rows.append(('body', f'{line["name"]} · {line["quantity"]} {line["unit"]} × {line["unit_price"]} ₸{remainder}'))
    if snap['deliveries']:
        rows.append(('heading', word(lang, 'Назначенные окна доставки', 'Белгіленген жеткізу уақыты')))
        if snap['delivery_address']:
            rows.append(('body', snap['delivery_address']))
        for delivery in snap['deliveries']:
            qty = '; '.join(f'{line["name"]}: {delivery["quantities"][line["id"]]} {line["unit"]}'
                            for line in snap['lines'] if line['id'] in delivery['quantities'])
            rows.append(('body', f'{delivery["start"]} — {delivery["end"]}' + (f' · {qty}' if qty else '')))
    by_key = {section['key']: section['text'] for section in rev.sections}
    for key in CLAUSES:
        value = details.get(f'clause_{key}') or by_key.get(key)
        if key == 'scope' and not value:
            value = word(lang,'См. согласованный состав выше.', 'Жоғарыдағы келісілген құрамды қараңыз.') if snap['description'] or snap['lines'] else q
        if key == 'dates' and not value:
            value = word(lang,'См. сроки выше.', 'Жоғарыдағы мерзімдерді қараңыз.') if snap['starts_on'] and snap['ends_on'] else q
        rows.append(('heading', clause_label(lang, key)))
        for paragraph in (value or q).splitlines():
            if paragraph.strip():
                rows.append(('body', paragraph))
    open_items = [row for row in rev.changes if row['kind'] in ('conflict','review')]
    if open_items:
        rows.append(('heading', word(lang, 'Вопросы перед согласованием', 'Келісуге дейінгі сұрақтар')))
        for item in open_items:
            refs = ', '.join(str(r) for r in item['refs'])
            rows.append(('body', f'{change_label(lang, item["kind"])}: {item["text"] or q} [{refs}]'))
    return rows


def register_fonts():
    fonts = Path(__file__).resolve().parents[1] / 'calculators/pdf_fonts'
    for suffix, file in [('', 'DejaVuSans.ttf'), ('-Bold', 'DejaVuSans-Bold.ttf')]:
        key = 'ESEPTEP' + suffix
        if key not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(key, str(fonts / file)))


def as_pdf(rows):
    register_fonts()
    colors_map = ['#223650', '#274d79']
    styles = {
        'title': ParagraphStyle('title', fontName='ESEPTEP-Bold', fontSize=19, leading=24, spaceAfter=12, textColor=colors.HexColor(colors_map[1])),
        'heading': ParagraphStyle('heading', fontName='ESEPTEP-Bold', fontSize=11, leading=16, spaceBefore=10, spaceAfter=4,
                                  keepWithNext=True, textColor=colors.HexColor(colors_map[1])),
        'body': ParagraphStyle('body', fontName='ESEPTEP', fontSize=9, leading=14, spaceAfter=4, textColor=colors.HexColor(colors_map[0])),
    }
    stream = BytesIO()
    def footer(canvas, doc):
        canvas.setFont('ESEPTEP', 8)
        canvas.drawRightString(A4[0] - 44, 24, str(doc.page))
    doc = SimpleDocTemplate(stream, pagesize=A4, leftMargin=44, rightMargin=44, topMargin=40, bottomMargin=40)
    doc.build([Paragraph(escape(text), styles[k]) for k,text in rows], onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


def as_docx(rows):
    """Standards-based plain editable DOCX without drawing/office dependencies."""
    stream = BytesIO()
    sizes = {'title':38, 'heading':24, 'body':20}
    def p(kind, text):
        bold = '<w:b/>' if kind in ('title', 'heading') else ''
        flow = '<w:keepNext/>' if kind != 'body' else ''
        return (f'<w:p><w:pPr>{flow}<w:spacing w:after="100"/></w:pPr><w:r>'
                f'<w:rPr><w:rFonts w:ascii="DejaVu Sans" w:hAnsi="DejaVu Sans"/>{bold}<w:sz w:val="{sizes[kind]}"/></w:rPr>'
                f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')
    body = ''.join(p(k, text) for k,text in rows)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           + body + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="800" w:right="900" w:bottom="800" w:left="900"/>'
           '</w:sectPr></w:body></w:document>')
    with ZipFile(stream, 'w', ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml', doc)
    return stream.getvalue()
