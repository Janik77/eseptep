import re

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from accounts.whole_views import tr
from .contract_copy import CLAUSES, clause_label, kind_label, missing, status
from .contract_export import as_docx, as_pdf, change_label, headings, report
from .contract_service import (
    allowed, apply_ai, contract_in_scope, create_ai_request, get_agreement,
    initialize_contract, latest, manual_save, safe_budget, source_from_upload,
    save_template, source_patch, source_selection, source_text, template_current, use_source,
)
from .contract_service import ContractError
from .contract_files import ContractFileError, read_source
from .views import secure

DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
NEW = ('Демо договора', 'Шарт демосы')
OPEN = ('Открыть договор', 'Шартты ашу')
ERRORS = {
    'offline_fixture_only': ('В офлайн-показе используйте комплектный ESEPTEP_original_DEMO-01.docx. Никакие данные не отправлены в OpenAI.',
                             'Офлайн көрсетілімде жинақтағы ESEPTEP_original_DEMO-01.docx файлын пайдаланыңыз. OpenAI-ға дерек жіберілген жоқ.'),
    'scan': ('Не удалось извлечь читаемый текст. Загрузите DOCX или PDF с текстовым слоем. Вызова ИИ не было.',
             'Оқылатын мәтін алынбады. DOCX немесе мәтін қабаты бар PDF жүктеңіз. ЖИ шақырылған жоқ.'),
    'file_type': ('Допустимы только читаемые DOCX или PDF. Вызова ИИ не было.',
                  'Тек оқылатын DOCX немесе PDF жарайды. ЖИ шақырылған жоқ.'),
    'file_pages': ('Нужен PDF до 15 страниц без пароля. Вызова ИИ не было.',
                   'Құпиясөзсіз, 15 бетке дейінгі PDF керек. ЖИ шақырылған жоқ.'),
    'file_size': ('Документ слишком большой. Допустимо до 5 МБ и 22 000 знаков текста.',
                  'Құжат тым үлкен. Шегі — 5 МБ және 22 000 мәтін таңбасы.'),
    'stale': ('Редакция уже изменилась. Откройте текущую и проверьте условия.',
              'Нұсқа өзгерді. Ағымдағы нұсқаны ашып, шарттарды тексеріңіз.'),
    'invalid': ('Проверьте заполненные поля.', 'Толтырылған өрістерді тексеріңіз.'),
    'budget_limit': ('Лимита пилота на новый вызов не хватает. Ручная правка и скачивание работают.',
                     'Пилот лимиті жаңа сұрауға жетпейді. Қолмен түзету мен жүктеу қолжетімді.'),
    'budget_missing': ('Нельзя проверить общий лимит пилота. Платный вызов отключён.',
                       'Пилоттың ортақ лимитін тексеру мүмкін емес. Ақылы сұрау өшірілген.'),
    'ai_disabled': ('Платный ИИ не подключён на этом стенде. Шаблон и ручные правки доступны.',
                    'Бұл стендте ақылы ЖИ қосылмаған. Үлгі мен қолмен түзету қолжетімді.'),
    'bad_response': ('Не удалось проверить структуру ответа ИИ. Черновик сохранён без изменений; можно открыть оригинал и продолжить вручную.',
                     'ЖИ жауабының құрылымы тексерілмеді. Нұсқа өзгерген жоқ; түпнұсқаны ашып, қолмен жалғастыруға болады.'),
    'provider_output_limit': ('ИИ не успел закончить ответ в заданном объёме. Повтора не будет. Откройте оригинал или заполните черновик вручную.',
                              'ЖИ белгіленген көлемде жауапты аяқтай алмады. Сұрау қайталанбайды. Түпнұсқаны ашыңыз немесе жобаны қолмен толтырыңыз.'),
    'provider_filtered': ('Провайдер не завершил ответ из-за ограничения содержимого. Текущая редакция сохранена.',
                          'Провайдер мазмұн шектеуіне байланысты жауапты аяқтамады. Ағымдағы нұсқа сақталды.'),
    'provider_incomplete': ('Провайдер не завершил ответ. Повтора не будет; черновик сохранён.',
                            'Провайдер жауапты аяқтамады. Сұрау қайталанбайды; жоба сақталды.'),
    'provider_unavailable': ('Ответ провайдера недоступен. Повтора не будет; черновик сохранён.',
                             'Провайдердің жауабы қолжетімсіз. Сұрау қайталанбайды; жоба сақталды.'),
}


def error_copy(code):
    return tr(*ERRORS.get(code, (
        'Запрос не завершён. Автоматического повтора нет; текущая редакция сохранена.',
        'Сұрау аяқталмады. Автоматты қайталау жоқ, ағымдағы нұсқа сақталды.',
    )))


def entry_for(user, project):
    try:
        repair = allowed(user, project)
    except Http404:
        return None
    return {'label': tr(*(OPEN if has_contract(repair) else NEW))}


def has_contract(repair):
    return repair.agreements.filter(demo_contract__isnull=False).exists()


def form_display(request, project, kind='', *, error='', status_code=200):
    repair = allowed(request.user, project)
    choices = [{'key':key, 'label':tr(kind_label('ru',key), kind_label('kk',key)),
                'agreement':repair.agreements.filter(kind=key).first()} for key in ('works','materials')]
    for item in choices:
        item['saved'] = bool(item['agreement'] and getattr(item['agreement'], 'demo_contract', None))
    ctx = {'project_id':project,'project_title':repair.project.title,'choices':choices,
           'kind':kind,'error':error_copy(error) if error else '', 'labels':ui_labels(),
           'can_manage_templates':request.user.is_superuser,
           'upload_error':error.startswith(('scan','file_', 'offline_fixture_only'))}
    if kind:
        agreement = get_agreement(repair, kind)
        contract = getattr(agreement, 'demo_contract', None)
        ctx.update(agreement=agreement)
        if contract is None:
            return secure(render(request,'repairs/contract.html',ctx,status=status_code))
        revnum = request.GET.get('version')
        previous = latest(contract)
        version = previous if not revnum else contract.versions.select_related('source').defer('source__original').filter(
            revision=positive(revnum)).first()
        if not version:
            raise Http404
        req_id = request.GET.get('proposal')
        prop = None if not req_id else contract.ai_requests.select_related('source').defer('source__original').filter(pk=positive(req_id)).first()
        if req_id and not prop:
            raise Http404
        if prop and prop.status == 'failed' and not error:
            ctx['error'] = error_copy(prop.result.get('error'))
        src_id = request.GET.get('source')
        source = None if not src_id else contract.sources.defer('original').filter(pk=positive(src_id)).first()
        if src_id and not source:
            raise Http404
        lang = contract.language
        prevnum = request.GET.get('compare')
        compare = None if not prevnum else contract.versions.select_related('source').defer('source__original').filter(
            revision=positive(prevnum)).first()
        if prevnum and not compare:
            raise Http404
        displayed_sources = contract.sources.defer('original','excerpts').order_by('-pk')[:12]
        latest_calls = list(contract.ai_requests.defer('result').only('id','operation','status').order_by('-pk')[:12])
        fields = headings(lang)
        curr_values = [{ 'key':key, 'label':fields[key], 'value':version.details.get(key,''),
                        'placeholder': contract.confirmed_snapshot.get(key, '') or missing(lang)}
                       for key in ('date','customer','provider','total','identifiers', 'delivery_cost')
                       if key != 'delivery_cost' or kind == 'materials']
        qtys = [{**l,'value':version.details.get('quantities', {}).get(l['id'],'')} for l in contract.confirmed_snapshot['lines']]
        sections = [{**section, 'label':clause_label(lang, section['key']),
                     'value':version.details.get(f'clause_{section["key"]}','')} for section in version.sections]
        source_basis = bool(version.details.get('_source_basis') and version.source_id)
        source_points = []
        source_selected = None
        if source_basis:
            source_points = [{'key':f"p{r['id']}", 'label':str(r['id']), 'text':source_text(version, r)}
                             for r in version.source.excerpts]
            selection = request.GET.get('source_edit')
            if selection:
                pointed = source_selection(version, selection)
                if not pointed:
                    raise Http404
                source_selected = {'key':selection, 'label':pointed['id'], 'text':source_text(version, pointed)}
        changes = [{**row, 'label':change_label(lang,row['kind'])} for row in version.changes]
        current_pages = report(contract, version)
        diff_before = report(contract,compare) if compare else []
        differences = []
        if compare:
            import difflib
            matcher = difflib.SequenceMatcher(a=[x[1] for x in diff_before],b=[x[1] for x in current_pages],autojunk=False)
            for action, a, b, c, d in matcher.get_opcodes():
                if action != 'equal':
                    differences.append({'before':[text for _,text in diff_before[a:b]],'after':[text for _,text in current_pages[c:d]]})
        ctx.update(contract=contract,version=version,contract_status=status(lang),source=source,proposal=prop,
                   sources=displayed_sources,calls=latest_calls,manual_fields=curr_values,qtys=qtys,
                   sections=sections,changes=changes,rows=current_pages,compare=compare,differences=differences,
                   source_basis=source_basis, source_points=source_points, source_selected=source_selected,
                   ai_enabled=contract_ai_visible(request.user),
                   revisions=contract.versions.order_by('-revision').values_list('revision',flat=True)[:40],
                   waiting_status=prop and prop.status == 'pending',
                   pending_is_current=bool(prop and prop.status=='ready' and not prop.applied_revision
                                            and previous.revision == prop.base_revision))
        if request.user.is_staff or request.user.get_username() in getattr(settings, 'CONTRACT_BUDGET_VIEWERS', ()):
            ctx['budget']=safe_budget()
            ctx['budget_viewer']=True
    return secure(render(request,'repairs/contract.html',ctx,status=status_code))


def positive(value):
    if not isinstance(value,str) or not re.fullmatch(r'[1-9]\d{0,8}',value):
        raise Http404
    return int(value)


def contract_ai_visible(user):
    if not settings.CONTRACT_AI_ENABLED:
        return False
    if not getattr(settings, 'ESEPTEP_CLOSED_PILOT', False):
        return True
    from core.closed_pilot import pilot_member
    return pilot_member(user, paid=True)


@require_GET
def choose(request, pk):
    repair = allowed(request.user, pk)
    # A single accepted order can reach the two actions without a chooser.
    # The historical offline walkthrough retains its original navigation.
    if not getattr(settings, 'CONTRACT_OFFLINE_MOCK', False):
        kinds = list(repair.agreements.values_list('kind', flat=True)[:2])
        if len(kinds) == 1 and not has_contract(repair):
            return secure(redirect('repairs:contract_show', pk=pk, kind=kinds[0]))
    return form_display(request,pk)


@require_GET
def show(request, pk, kind):
    return form_display(request,pk,kind)


@require_POST
def operate(request, pk, kind):
    allowed(request.user,pk)
    action = request.POST.get('action')
    kwargs = {'pk':pk,'kind':kind}
    try:
        if action == 'create':
            if request.POST.get('style') not in ('source','template'):
                raise ContractError('invalid')
            initialize_contract(request.user,pk,kind,request.POST.get('language'), request.POST.get('style'))
            query={'upload':'1'} if request.POST.get('style')=='source' else {}
        elif action == 'upload':
            source = source_from_upload(request.user,pk,kind,request.FILES.get('source'))
            query={'source':source.pk}
        elif action == 'use_source':
            use_source(request.user, pk, kind, positive(request.POST.get('source')), request.POST.get('revision'))
            query={}
        elif action == 'source_patch':
            source_patch(request.user, pk, kind, request.POST)
            query={}
        elif action == 'manual':
            manual_save(request.user,pk,kind,request.POST)
            query={}
        elif action in ('shorten','amend'):
            if action == 'shorten':
                positive(request.POST.get('source'))
            req=create_ai_request(request.user,pk,kind,action,request.POST)
            query={'proposal':req.pk}
        elif action == 'apply':
            apply_ai(request.user,pk,kind,positive(request.POST.get('proposal')))
            query={}
        else:
            raise ContractError('invalid')
    except (ContractError,ContractFileError) as exc:
        return form_display(request,pk,kind,error=str(exc),status_code=409 if str(exc)=='stale' else 400)
    from django.urls import reverse
    from urllib.parse import urlencode
    url=reverse('repairs:contract_show',kwargs=kwargs)
    return secure(redirect(url+('?' + urlencode(query) if query else '')))


@require_GET
def download(request, pk, kind, revision, extension):
    contract=contract_in_scope(request.user,pk,kind)
    version=contract.versions.filter(revision=revision).first()
    if not version or extension not in ('pdf','docx'):
        raise Http404
    result=report(contract,version)
    data,mime=(as_docx(result),DOCX_MIME) if extension=='docx' else (as_pdf(result),'application/pdf')
    response=HttpResponse(data,content_type=mime,headers={
        'Content-Disposition': f'attachment; filename="ESEPTEP-contract-{pk}-{kind}-v{revision}.{extension}"'})
    return secure(response)


@require_GET
def original(request, pk, kind, source):
    contract=contract_in_scope(request.user,pk,kind)
    doc=contract.sources.filter(pk=source).first()
    if not doc:
        raise Http404
    return secure(HttpResponse(bytes(doc.original),content_type='application/octet-stream',headers={
          'Content-Disposition': f'attachment; filename="ESEPTEP-source-{doc.pk}.{doc.extension}"'}))


@require_http_methods(['GET', 'POST'])
def library(request):
    if not request.user.is_superuser or not settings.CONTRACT_DEMO_ENABLED:
        raise Http404
    kind = request.GET.get('kind', 'materials')
    lang = request.GET.get('lang', 'ru')
    latest_version = template_current(kind, lang)
    if not latest_version:
        raise Http404
    error, source, code = '', [], 200
    if request.method == 'POST':
        try:
            operation = request.POST.get('action')
            if operation == 'save':
                save_template(request.user, kind, lang, request.POST)
                return secure(redirect(request.get_full_path()))
            if operation != 'sample':
                raise Http404
            if getattr(settings, 'CONTRACT_OFFLINE_MOCK', False):
                raise ContractError('offline_fixture_only')
            _, _, source = read_source(request.FILES.get('sample'))
        except (ContractError, ContractFileError) as exc:
            error, code = error_copy(str(exc)), (409 if str(exc) == 'stale' else 400)
    rev = request.GET.get('version')
    shown = latest_version if not rev else type(latest_version).objects.filter(
        kind=kind, language=lang, revision=positive(rev)).first()
    if not shown:
        raise Http404
    rows = [{**row, 'label':clause_label(lang, row['key'])} for row in shown.sections]
    return secure(render(request, 'repairs/contract_library.html', {
        'kind':kind, 'lang':lang, 'title':kind_label(lang,kind), 'latest':latest_version,
        'shown':shown, 'rows':rows, 'source':source, 'error':error,
        'versions':type(shown).objects.filter(kind=kind, language=lang).order_by('-revision')[:30],
        'is_current':shown.pk == latest_version.pk,
    }, status=code))


def ui_labels():
    return {key:tr(*value) for key,value in {
        'demo':NEW,'open':OPEN,
        'repair':('Мой ремонт','Менің жөндеуім'),
        'private':('Закрытый пилот · учебные данные','Жабық пилот · сынақ деректері'),
        'select':('Выберите тип договора','Шарт түрін таңдаңыз'),
        'none':('Сначала подтвердите предложение в проекте. Смета калькулятора не станет ценой договора.',
                'Алдымен жобадағы ұсынысты растаңыз. Калькулятор сметасы шарт бағасына айналмайды.'),
        'template':('Создать по шаблону','Үлгі бойынша жасау'), 'upload':('Загрузить свой договор','Өз шартыңызды жүктеу'),
        'doclang':('Язык договора','Шарт тілі'), 'back':('К договорам проекта','Жоба шарттарына қайту'),
        'use_source':('Использовать как основу','Негіз ретінде пайдалану'),
        'edit_source':('Изменить этот пункт','Осы тармақты өзгерту'),
        'library':('Библиотека шаблонов','Үлгілер кітапханасы'),
        'proposal':('Предложить правку','Түзету ұсыну'), 'download':('Скачать','Жүктеу'),
        'amend':('Предложить через ИИ','ЖИ көмегімен ұсыну'),
        'shorten':('Подготовить краткую редакцию','Қысқа нұсқасын дайындау'),
        'changes':('Что изменилось','Не өзгерді'), 'source':('Оригинал','Түпнұсқа'),
        'source_help':('Выберите DOCX или PDF с текстовым слоем. Скан без текста не обрабатывается.',
                       'DOCX немесе мәтін қабаты бар PDF таңдаңыз. Мәтінсіз скан өңделмейді.'),
        'send':(('Это учебный ответ. Текст не отправляется в OpenAI.', 'Бұл оқу жауабы. Мәтін OpenAI-ға жіберілмейді.')
                if getattr(settings, 'CONTRACT_OFFLINE_MOCK', False)
                else ('При нажатии на кнопку анализа выбранный текст передаётся в OpenAI. Используйте только обезличенный пример.',
                      'Талдау түймесін басқанда таңдалған мәтін OpenAI-ға жіберіледі. Тек дербестендірілмеген мысалды пайдаланыңыз.')),
        'check':('Сохранить и проверить исходник','Түпнұсқаны сақтау және тексеру'),
        'saved_sources':('Сохранённые оригиналы','Сақталған түпнұсқалар'),
        'save':('Сохранить без ИИ','ЖИ қолданбай сақтау'), 'manual':('Изменить вручную','Қолмен өзгерту'),
        'field_hints':('Пустое поле означает «Нужно уточнить» или сохраняет исходное условие. Ручная правка не меняет условия заказа.',
                       'Бос өріс нақтылауды қажет етеді немесе бастапқы шартты сақтайды. Қолмен түзету тапсырыс шарттарын өзгертпейді.'),
        'clauses':('Изменить пункты','Тармақтарды өзгерту'),
        'before':('Было','Бұрын'), 'after':('Стало','Кейін'), 'apply':('Применить к черновику','Жобаға қолдану'),
        'pending':('Запрос принят. Откройте страницу позже, не отправляйте повторно.',
                   'Сұрау қабылданды. Қайта жібермей, бетті кейінірек ашыңыз.'),
        'applied':('Предложение уже применено.','Ұсыныс бұрын қолданылған.'),
        'obsolete':('Текущая редакция изменилась. Предложение больше нельзя применить.',
                    'Ағымдағы нұсқа өзгерді. Ұсынысты енді қолдану мүмкін емес.'),
        'section':('Раздел','Бөлім'), 'instruction':('Что изменить?','Нені өзгерту керек?'),
        'review':('Проверьте важные условия и спорные пункты перед применением.','Қолданбас бұрын маңызды шарттар мен даулы тармақтарды тексеріңіз.'),
        'preview':('Предложенная краткая редакция','Ұсынылған қысқа нұсқа'),
        'versions':('Редакции и сравнение','Нұсқалар мен салыстыру'),
        'current':('Открыть текущую редакцию','Ағымдағы нұсқаны ашу'),
        'compare':('Сравнить','Салыстыру'),
        'budget':('Общий лимит плана и договора · консервативная оценка, не счёт провайдера',
                  'Жоспар мен шарттың ортақ лимиті · бұл сақтық бағасы, провайдер шоты емес'),
        'usage':('Журнал запросов по договору','Шарт сұрауларының журналы'),
        'estimate':('Оценка для успешного ответа, ¢','Сәтті жауаптың бағасы, ¢'),
        'verify':('Сверьте этот пункт в оригинале.','Бұл тармақты түпнұсқамен салыстырыңыз.'),
        'paragraph':('Фрагмент','Үзінді'),
    }.items()}
