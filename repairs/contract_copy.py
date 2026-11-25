"""Contract language is independent from the UI language."""

LANGUAGES = ('ru', 'kk')
CLAUSES = {
    'scope': ('Предмет и объём', 'Шарт нысаны және көлемі'),
    'price': ('Цена и оплата', 'Баға және төлем'),
    'dates': ('Сроки', 'Мерзімдер'),
    'delivery': ('Доставка', 'Жеткізу'),
    'acceptance': ('Приёмка', 'Қабылдау'),
    'defects': ('Недостатки', 'Кемшіліктер'),
    'exclusions': ('Исключения', 'Қамтылмайтындар'),
    'appendices': ('Приложения', 'Қосымшалар'),
}


def word(lang, ru, kk):
    return kk if lang == 'kk' else ru


def clause_label(lang, code):
    return word(lang, *CLAUSES[code])


def kind_label(lang, kind):
    return word(lang, *(
        ('Поставка материалов', 'Материал жеткізу') if kind == 'materials'
        else ('Ремонтные работы', 'Жөндеу жұмыстары')
    ))


def missing(lang):
    return word(lang, 'Нужно уточнить', 'Нақтылау қажет')


def status(lang):
    return word(lang, 'Черновик на согласование', 'Келісуге арналған жоба')
