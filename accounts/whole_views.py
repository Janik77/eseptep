"""Local closed-pilot flow. No provider calls, repricing or external notifications."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from types import SimpleNamespace
from django.core import signing
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.utils.translation import get_language
from .models import ClientProject, SavedWholeEstimate, WholeSupplierOffer, ServiceRequest, UserProfile
from .views import role_required, _meeting_supplier
from projects.models import WholePlanEstimate, ProjectUpload
from .identifiers import parse_positive_id


def tr(ru, kk):
    return kk if (get_language() or '').startswith('kk') else ru


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


@role_required(UserProfile.Role.CLIENT)
@require_http_methods(['GET','POST'])
def save_whole(request, estimate_id):
    source = get_object_or_404(WholePlanEstimate.objects.select_related('upload'), pk=estimate_id, upload__user=request.user)
    if request.method == 'GET':
        return render(request,'accounts/whole_choose_project.html',{'source':source,'projects':ClientProject.objects.filter(user=request.user), 'next_action':'save' if request.GET.get('next')=='save' else 'quote'})
    project = get_object_or_404(ClientProject, pk=parse_positive_id(request.POST.get('project_id')) or 0, user=request.user)
    # First statement inside the transaction is a write: no SQLite lock upgrade race.
    with transaction.atomic():
        ClientProject.objects.filter(pk=project.pk).update(title=F('title'))
        project = get_object_or_404(ClientProject,pk=project.pk,user=request.user)
        ProjectUpload.objects.filter(pk=source.upload_id,user=request.user).update(ai_status=F('ai_status'))
        source = get_object_or_404(WholePlanEstimate.objects.select_related('upload'),pk=source.pk,upload__user=request.user)
        saved = SavedWholeEstimate.objects.filter(project=project,source=source).first()
        if not saved:
            if source.upload.ai_summary.get('whole_estimate_id') != source.pk:
                return HttpResponseBadRequest(tr('Расчёт изменился. Откройте текущую версию.', 'Есеп өзгерді. Ағымдағы нұсқаны ашыңыз.'))
            saved = SavedWholeEstimate.objects.create(project=project,source=source,snapshot=deepcopy(source.snapshot))
    return redirect('accounts:whole_preview' if request.POST.get('next') == 'quote' else 'accounts:whole_saved', pk=saved.pk)


def owned_saved(request, pk):
    return get_object_or_404(SavedWholeEstimate.objects.select_related('project','source'),pk=pk,project__user=request.user)


@role_required(UserProfile.Role.CLIENT)
@require_GET
def whole_saved(request, pk):
    saved = owned_saved(request,pk)
    requests = saved.requests.filter(client=request.user).select_related('target_supplier','whole_offer').order_by('-pk')
    latest_answer = requests.filter(whole_offer__supplier_id=F('target_supplier_id')).first()
    answer_lines = latest_answer.whole_offer.snapshot.get('lines',[]) if latest_answer else []
    available = [row for row in answer_lines if row.get('availability') == 'available']
    unavailable = [row for row in answer_lines if row.get('availability') == 'unavailable']
    return render(request,'accounts/whole_saved.html',{'saved':saved,'supplier':_meeting_supplier(),
        'requests':requests, 'latest_answer':latest_answer, 'available':available, 'unavailable':unavailable, 'priced_positions':sum(
            row.get('line_total') is not None for row in saved.snapshot.get('procurement',[]))})


@role_required(UserProfile.Role.CLIENT)
@require_http_methods(['GET','POST'])
def whole_preview(request, pk):
    saved = owned_saved(request,pk)
    supplier = _meeting_supplier()
    if not supplier or supplier.user_id == request.user.pk:
        raise Http404
    snapshot = {'schema':'whole-offer-v1','demo':True,'saved_id':saved.pk,'project_title':saved.project.title,
        'city':saved.project.city,'supplier_name':supplier.company_name}
    # Suppliers receive only reviewed procurement rows, not drawing or room evidence.
    fields = ('title','unit','quantity','unit_price','line_total','material_key','calculator_slug','variant','specification',
        'purchase_quantity','purchase_unit','pack_coverage','price_basis')
    all_lines = [{**{key:deepcopy(row[key]) for key in fields if key in row},'line_id':str(i)}
                 for i,row in enumerate(saved.snapshot['procurement'])]
    if not all_lines:
        return HttpResponseBadRequest(tr('Сначала уточните площади комнат.', 'Алдымен бөлмелердің ауданын нақтылаңыз.'))
    if request.method == 'GET':
        existing = saved.requests.filter(client=request.user,target_supplier=supplier).first()
        if existing:
            return redirect('accounts:whole_request',pk=existing.pk)
    valid_ids = {row['line_id'] for row in all_lines}
    reviewing = request.method == 'GET' and request.GET.get('select') == '1'
    posted = None
    try:
        if request.method == 'POST':
            posted = signing.loads(request.POST.get('token',''),salt='whole-request-v1',max_age=3600)
            ids = posted.get('ids') if isinstance(posted,dict) else None
        else:
            ids = request.GET.getlist('line') if reviewing else list(valid_ids)
        if (not isinstance(ids,list) or not ids or len(ids)>len(valid_ids)
                or any(not isinstance(i,str) or i not in valid_ids for i in ids)
                or len(set(ids))!=len(ids)):
            raise ValueError
    except (signing.BadSignature,ValueError):
        if request.method == 'POST':
            return HttpResponseBadRequest(tr('Проверьте состав и подтвердите запрос заново.', 'Құрамын тексеріп, сұранысты қайта растаңыз.'))
        snapshot['lines'] = all_lines
        return render(request,'accounts/whole_preview.html',{'saved':saved,'snapshot':snapshot,'reviewing':False,
            'selection_error':tr('Выберите хотя бы одну позицию.', 'Кемінде бір позицияны таңдаңыз.')},status=400)
    selected_ids = set(ids)
    snapshot['lines'] = [row for row in all_lines if row['line_id'] in selected_ids]
    priced_lines = [Decimal(row['line_total']) for row in snapshot['lines'] if row.get('line_total') is not None]
    snapshot['priced_subtotal'] = str(sum(priced_lines, Decimal(0))) if priced_lines else None
    snapshot['unpriced_positions'] = len(snapshot['lines']) - len(priced_lines)
    payload = {'user':request.user.pk,'saved':saved.pk,'supplier':supplier.pk,
        'ids':[row['line_id'] for row in snapshot['lines']],'digest':digest(snapshot)}
    if request.method == 'POST':
        if posted != payload or request.POST.get('confirm') != 'yes':
            return HttpResponseBadRequest(tr('Проверьте состав и подтвердите запрос заново.', 'Құрамын тексеріп, сұранысты қайта растаңыз.'))
        with transaction.atomic():
            SavedWholeEstimate.objects.filter(pk=saved.pk).update(snapshot=F('snapshot'))
            locked = owned_saved(request,pk)
            current_supplier = _meeting_supplier()
            if not current_supplier or current_supplier.pk != supplier.pk:
                raise Http404
            if locked.snapshot != saved.snapshot:
                return HttpResponseBadRequest(tr('Смета изменилась.', 'Смета өзгерді.'))
            req,_ = ServiceRequest.objects.get_or_create(whole_estimate=locked,target_supplier=supplier,
                defaults={'client':request.user,'project':locked.project,'request_type':'supplier','request_snapshot':snapshot})
        # A retry or second tab opens the immutable original, not a pretend new request.
        return redirect('accounts:whole_request',pk=req.pk)
    return render(request,'accounts/whole_preview.html',{'saved':saved,'snapshot':snapshot,'reviewing':reviewing,
        'token':signing.dumps(payload,salt='whole-request-v1') if reviewing else None})


def accessible_request(request, pk):
    qs=ServiceRequest.objects.filter(whole_estimate__isnull=False,request_type='supplier',project__user=F('client'),project_id=F('whole_estimate__project_id')).select_related('project','target_supplier','whole_estimate')
    role=getattr(getattr(request.user,'profile',None),'role',None)
    if role == 'client':
        qs=qs.filter(client=request.user)
    elif role == 'supplier':
        qs=qs.filter(target_supplier__user=request.user,target_supplier__is_active=True)
    else:
        raise Http404
    return get_object_or_404(qs,pk=pk), role == 'supplier'


def offer_snapshot(post, snapshot):
    rows=[]
    for row in snapshot['lines']:
        key=row['line_id']
        availability=post.get('availability_'+key,'unknown')
        if availability not in ('available','unavailable','unknown'):
            raise ValueError
        raw=post.get('price_'+key,'').strip().replace(',','.')
        price=None
        if raw:
            if len(raw)>12:
                raise ValueError
            try:
                price=Decimal(raw)
                if not price.is_finite() or price<0 or price>Decimal('999999999.99') or price.as_tuple().exponent < -2:
                    raise ValueError
            except InvalidOperation:
                raise ValueError
        # Price alone is not a confirmed offer when stock is unknown/unavailable.
        total=(price*Decimal(row.get('purchase_quantity', row['quantity']))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) if price is not None and availability=='available' else None
        rows.append({**deepcopy(row),'unit_price':str(price) if price is not None else None,
            'availability':availability,'line_total':str(total) if total is not None else None})
    known=sum(Decimal(r['line_total']) for r in rows if r['line_total'] is not None)
    complete=bool(rows) and all(r['line_total'] is not None for r in rows)
    return {'schema':'whole-supplier-offer-v1','lines':rows,'confirmed_subtotal':str(known) if any(r['line_total'] is not None for r in rows) else None,
        'total':str(known) if complete else None,'unconfirmed':sum(r['line_total'] is None for r in rows),
        'message':post.get('message','').strip()[:2000]}


@login_required
@require_http_methods(['GET','POST'])
def whole_request(request, pk):
    req, recipient=accessible_request(request,pk)
    error=''
    if request.method=='POST':
        if not recipient:
            return HttpResponseForbidden()
        try:
            token=signing.loads(request.POST.get('token',''),salt='whole-response-v1',max_age=3600)
            if token != {'request':req.pk,'supplier':req.target_supplier_id,'digest':digest(req.request_snapshot)}:
                raise ValueError
            result=offer_snapshot(request.POST,req.request_snapshot)
        except (signing.BadSignature,ValueError):
            error=tr('Проверьте цены и наличие. Суммы должны быть неотрицательными, до двух знаков после запятой.', 'Баға мен қолжетімділікті тексеріңіз. Сома теріс болмауы және үтірден кейін екі таңбадан аспауы тиіс.')
        else:
            with transaction.atomic():
                ServiceRequest.objects.filter(pk=req.pk).update(status=F('status'))
                req,recipient=accessible_request(request,pk)
                if not recipient:
                    return HttpResponseForbidden()
                if digest(req.request_snapshot)!=token['digest']:
                    return HttpResponseBadRequest(tr('Состав запроса изменился.', 'Сұраныс құрамы өзгерді.'))
                existing=WholeSupplierOffer.objects.filter(request=req,supplier_id=req.target_supplier_id).first()
                if not existing:
                    if req.status not in ('new','viewed','responded'):
                        return HttpResponseBadRequest(tr('Заявка закрыта.', 'Өтінім жабылды.'))
                    WholeSupplierOffer.objects.create(request=req,supplier=req.target_supplier,snapshot=result)
                    req.status='responded';req.save(update_fields=['status'])
            return redirect('accounts:whole_request',pk=pk)
    offer=WholeSupplierOffer.objects.filter(request=req,supplier_id=req.target_supplier_id).first()
    quote_lines = [{**row, 'entered_price': request.POST.get('price_'+row['line_id'],'')[:12] if error else '',
                    'entered_availability': request.POST.get('availability_'+row['line_id'],'unknown') if error else 'unknown'}
                   for row in req.request_snapshot['lines']]
    return render(request,'accounts/whole_request.html',{'service_request':req,'snapshot':req.request_snapshot,
        'offer':offer,'is_recipient':recipient,'error':error,'quote_lines':quote_lines, 'entered_message':request.POST.get('message','')[:2000] if error else '',
        'token':signing.dumps({'request':req.pk,'supplier':req.target_supplier_id,'digest':digest(req.request_snapshot)},salt='whole-response-v1')})


@role_required(UserProfile.Role.CLIENT)
@require_GET
def saved_whole_pdf(request, pk):
    saved=owned_saved(request,pk)
    from projects.whole_pdf import build_pdf
    response=HttpResponse(build_pdf(SimpleNamespace(snapshot=saved.snapshot,pk=saved.pk,created_at=saved.created_at)),content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="saved-floor-{pk}.pdf"'
    response['Cache-Control']='private, no-store'
    return response


@login_required
@require_GET
def whole_offer_pdf(request, pk):
    req,_=accessible_request(request,pk)
    offer=get_object_or_404(WholeSupplierOffer,request=req,supplier_id=req.target_supplier_id)
    from .whole_pdf import offer_pdf
    response=HttpResponse(offer_pdf(req,offer),content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="supplier-offer-{pk}.pdf"'
    response['Cache-Control']='private, no-store'
    return response
