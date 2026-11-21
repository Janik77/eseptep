import uuid
from decimal import Decimal
from django.core import signing
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.whole_views import tr
from .models import Photo, Repair, city_key
from .services import agreement_scope, current_terms, latest_terms, offer_rows, offer_token, perform, receipt_balance, role_of, scoped_repair


EVENTS = {
    'accept_offer': ('Предложение принято', 'Ұсыныс қабылданды'),
    'propose_terms': ('Предложены новые условия', 'Жаңа шарттар ұсынылды'),
    'confirm_terms': ('Новые условия подтверждены', 'Жаңа шарттар расталды'),
    'schedule_delivery': ('Поставка назначена', 'Жеткізу белгіленді'),
    'confirm_delivery': ('Получение отмечено', 'Қабылдау белгіленді'),
    'plan_stage': ('Этап запланирован', 'Кезең жоспарланды'),
    'submit_stage': ('Работа передана на приёмку', 'Жұмыс қабылдауға тапсырылды'),
    'request_fix': ('Запрошено исправление', 'Түзету сұралды'),
    'accept_stage': ('Работа принята', 'Жұмыс қабылданды'),
    'report_issue': ('Сообщено о проблеме', 'Мәселе туралы хабарланды'),
    'issue_reply': ('Ответ по проблеме', 'Мәселе бойынша жауап'),
    'resolve_issue': ('Рассмотрение завершено', 'Қарау аяқталды'),
}
STAGES = {
    'planned': ('Запланировано', 'Жоспарланған'),
    'review': ('На приёмке', 'Қабылдауда'),
    'fix': ('Нужна доработка', 'Түзету қажет'),
    'accepted': ('Принято', 'Қабылданды'),
}


def secure(response):
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def wrap_event(row):
    return {'label': tr(*EVENTS[row.action]), 'comment': row.comment,
            'created_at': row.created_at, 'data': row.data}


def to_lines(row):
    return [{**x, 'line_id': x['id']} for x in row.lines]


def wrap_agreement(a, role):
    terms = current_terms(a)
    latest = latest_terms(a)
    pending = latest if latest and latest.accepted_at is None else None
    events = list(a.events.all())
    # Never load full image BLOBs while enumerating the page. Expose only IDs.
    photo_ids = dict(Photo.objects.filter(event__agreement=a).values_list('event_id', 'pk'))
    def picture(e):
        return {'id': photo_ids[e.pk]} if e.pk in photo_ids else None
    remaining = receipt_balance(a) if a.kind == 'materials' else {}
    outstanding = receipt_balance(a, pending=False) if a.kind == 'materials' else {}
    outstanding_lines = [{**x, 'quantity': outstanding[x['id']]} for x in to_lines(terms)
                         if outstanding.get(x['id'], 0) > 0]
    available_lines = [{**x, 'quantity': remaining[x['id']]} for x in to_lines(terms)
                       if remaining.get(x['id'], 0) > 0]
    stages, deliveries, problems = [], [], []
    for s in a.stages.order_by('due_on', 'pk'):
        st_events = [e for e in events if e.stage_id == s.pk and not e.problem_id]
        stages.append({'id': s.pk, 'title': s.title, 'status': s.state, 'submission': s.submission,
            'due_on': s.due_on, 'label': tr(*STAGES[s.state]),
            'can_submit': role == 'master' and s.state in ('planned','fix'),
            'can_review': role == 'client' and s.state == 'review',
            'can_report': role != 'reviewer', 'comment': next((e.comment for e in reversed(st_events) if e.comment), ''),
            'photos': [picture(e) for e in st_events if picture(e)],
            **{key: uuid.uuid4() for key in ('submit_token','accept_token','fix_token','issue_token')}})
    if a.kind == 'materials':
        for d in a.deliveries.order_by('window_start','pk'):
            rows = []
            for x in to_lines(terms):
                key = x['id']
                if key in d.quantities:
                    recorded = (d.receipt or {}).get(key, {})
                    missing = recorded.get('missing')
                    rows.append({**x, 'quantity': Decimal(d.quantities[key]), 'received': recorded.get('received'),
                         'damaged': recorded.get('damaged'),
                         'remaining': (Decimal(missing) + Decimal(recorded['damaged'])) if missing is not None else None})
            deliveries.append({'id': d.pk, 'window_start': d.window_start, 'window_end': d.window_end,
                 'confirmed': d.receipt is not None, 'lines': rows,
                 'label': tr('Получение отмечено','Қабылдау белгіленді') if d.receipt is not None else tr('Ожидается','Күтілуде'),
                 'address': a.repair.delivery_address if role in ('supplier','client') and d.receipt is None else '',
                 'can_confirm': role == 'client' and d.receipt is None, 'can_report': role != 'reviewer',
                 'confirm_token': uuid.uuid4(), 'issue_token': uuid.uuid4()})
    for p in a.problems.select_related('stage').order_by('pk'):
        related = [e for e in events if e.problem_id == p.pk]
        opening = next(e for e in related if e.action == 'report_issue')
        closed = next((e.comment for e in related if e.action == 'resolve_issue'), '')
        problems.append({'id': p.pk, 'title': p.stage.title if p.stage_id else tr('Поставка','Жеткізу'),
           'label': tr('Рассмотрено','Қаралды') if p.resolved_at else tr('На рассмотрении','Қаралуда'),
           'comment': opening.comment, 'photos': [picture(opening)] if picture(opening) else [],
           'replies': [{**wrap_event(e), 'photo': picture(e)} for e in related if e.action == 'issue_reply'],
           'resolution': closed, 'can_reply': not p.resolved_at,
           'can_resolve': role == 'reviewer' and not p.resolved_at,
           'reply_token': uuid.uuid4(), 'resolve_token': uuid.uuid4()})
    return {'agreement':a, 'terms':terms, 'pending_terms':pending, 'versions':a.versions.all(),
            'deliveries':deliveries, 'stages':stages, 'problems':problems,
            'events':[{**wrap_event(e), 'photo': picture(e)} for e in reversed(events[-200:])],
            'role':role,'available_lines':available_lines, 'outstanding_lines':outstanding_lines, 'can_propose':role in ('supplier','master') and not pending,
            'can_confirm_terms':role=='client' and bool(pending),
            'can_schedule':role=='supplier' and bool(available_lines), 'can_plan':role=='master',
            'actions': {key:uuid.uuid4() for key in ('propose_terms_token','confirm_terms_token','schedule_token','plan_token')}}


def display(request, repair, role, *, error='', status=200):
    entries = [wrap_agreement(a, role) for a in agreement_scope(repair, request.user, role).order_by('kind')]
    offers = [{**x, 'offer_token': offer_token(repair, request.user, x), 'token': uuid.uuid4(), 'start': '', 'end': ''}
              for x in offer_rows(repair)] if role == 'client' else []
    for x in offers:
        for row in x['lines']:
            row['total'] = str((Decimal(row['quantity']) * Decimal(row['unit_price'])).quantize(Decimal('.01')))
    next_action, next_event, current_summary = None, '', ''
    if role == 'client':
        pending = min((d for e in entries for d in e['deliveries'] if d['can_confirm']),
                      key=lambda d: d['window_start'], default=None)
        if pending:
            start, end = (timezone.localtime(pending[k]) for k in ('window_start','window_end'))
            next_event = tr('Ближайшее окно доставки: ', 'Келесі жеткізу уақыты: ') + f"{start:%d.%m.%Y, %H:%M} – {end:%d.%m.%Y, %H:%M}"
        change = next((e for e in entries if e['can_confirm_terms']), None)
        if change:
            current_summary = tr('Партнёр предложил изменить условия', 'Серіктес шарттарды өзгертуді ұсынды')
            next_action = {'anchor': f"terms-{change['agreement'].pk}", 'label': tr('Проверить изменения','Өзгерістерді қарау')}
        else:
            stage = next((row for e in entries for row in e['stages'] if row['can_review']), None)
            if stage:
                current_summary = tr('Мастер передал этап на приёмку: ', 'Шебер қабылдауға тапсырған кезең: ') + stage['title']
                next_action = {'anchor': f"stage-{stage['id']}", 'label': tr('Посмотреть работу','Жұмысты көру')}
            elif pending:
                current_summary = tr('Ожидается поставка','Жеткізу күтілуде')
                next_action = {'anchor': f"delivery-{pending['id']}", 'label': tr('Посмотреть поставку','Жеткізуді көру')}
            elif entries and not offers:
                accepted = [row for e in entries for row in e['stages'] if row['status'] == 'accepted']
                if accepted:
                    current_summary = tr('Этап принят: ', 'Қабылданған кезең: ') + max(accepted, key=lambda row: row['id'])['title']
                elif all(not e['outstanding_lines'] and e['deliveries'] for e in entries):
                    current_summary = tr('Все согласованные материалы получены', 'Келісілген барлық материал алынды')
                else:
                    current_summary = tr('Подтверждение от вас пока не требуется', 'Әзірге сіздің растауыңыз қажет емес')
    return secure(render(request, 'repairs/detail.html', {'repair':repair, 'agreements':entries, 'offers':offers,
                  'city_label':repair.city.name, 'new_token':uuid.uuid4(), 'current_summary':current_summary,
                  'next_event':next_event, 'next_action':next_action, 'error':error}, status=status))


@require_GET
def detail(request, pk):
    return display(request, *scoped_repair(request.user, pk))


@require_POST
def action(request, pk):
    try:
        perform(request.user, pk, request.POST, request.FILES.get('photo'))
    except (ValueError, KeyError, TypeError, signing.BadSignature):
        return display(request, *scoped_repair(request.user, pk), error=tr(
            'Проверьте поля и актуальное состояние. Изменений нет.',
            'Өрістер мен ағымдағы күйді тексеріңіз. Өзгерістер жоқ.'), status=400)
    return secure(redirect('repairs:detail', pk=pk))


@require_GET
def photo(request, photo_id):
    facts = Photo.objects.filter(pk=photo_id).values_list('event__agreement__repair__project_id', 'event__agreement_id').first()
    if not facts:
        raise Http404
    repair, role = scoped_repair(request.user, facts[0])
    if not agreement_scope(repair, request.user, role).filter(pk=facts[1]).exists():
        raise Http404
    image = Photo.objects.filter(pk=photo_id).values_list('jpeg', flat=True).first()
    if image is None:
        raise Http404
    return secure(HttpResponse(bytes(image), content_type='image/jpeg'))

@require_GET
def review_queue(request):
    if not request.user.is_authenticated or not request.user.is_active or role_of(request.user) != 'admin':
        raise Http404
    enabled = Repair.objects.filter(reviewer=request.user, enabled=True, city__enabled=True).select_related(
        'project', 'city').order_by('project_id')
    projects = [row for row in enabled if city_key(row.project.city) == row.city.key]
    return secure(render(request, 'repairs/review_queue.html', {'repairs': projects}))
