import hashlib
import io
import json
import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core import signing
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.utils import timezone
from PIL import Image, ImageOps

from accounts.models import MasterResponse, ServiceRequest, UserProfile, WholeSupplierOffer
from .models import Agreement, Delivery, Event, Photo, Problem, Repair, Stage, Terms, city_key


OPEN = ('new', 'viewed', 'responded')
MONEY_MAX = Decimal('9999999999.99')
QUANTITY_MAX = Decimal('9999999.9999')


class InvalidAction(ValueError):
    pass


def role_of(user):
    return getattr(getattr(user, 'profile', None), 'role', None)


def scoped_repair(user, pk, *, lock=False):
    if not user.is_authenticated or not user.is_active:
        raise Http404
    if lock:
        scoped_repair(user, pk)
        # The no-op write serializes SQLite writes before any reads within this
        # transaction, and holds the project row lock in PostgreSQL.
        Repair.objects.filter(project_id=pk, enabled=True).update(enabled=F('enabled'))
    repair = (Repair.objects.filter(project_id=pk, enabled=True, city__enabled=True)
              .select_related('project', 'city').first())
    if not repair or city_key(repair.project.city) != repair.city.key:
        raise Http404
    if lock:
        from .models import PilotCity
        if not PilotCity.objects.select_for_update().filter(pk=repair.city_id, enabled=True).exists():
            raise Http404
    role = role_of(user)
    if role == UserProfile.Role.CLIENT and repair.project.user_id == user.pk:
        return repair, 'client'
    if role == UserProfile.Role.ADMIN and repair.reviewer_id == user.pk:
        return repair, 'reviewer'
    kinds = {UserProfile.Role.SUPPLIER: Agreement.Kind.MATERIALS, UserProfile.Role.MASTER: Agreement.Kind.WORKS}
    if role in kinds and agreement_scope(repair, user, role).exists():
        return repair, role
    raise Http404


def agreement_scope(repair, user, role):
    qs = repair.agreements.all()
    if role == 'supplier':
        return qs.filter(partner=user, kind='materials', supplier_offer__supplier__is_active=True)
    if role == 'master':
        return qs.filter(partner=user, kind='works')
    if role in ('client', 'reviewer'):
        return qs
    return qs.none()


def for_agreement(repair, user, role, pk):
    row = agreement_scope(repair, user, role).filter(pk=pk).first()
    if not row:
        raise Http404
    return row


def number(value, max_value, places=2):
    value = str(value).strip().replace(',', '.')
    if not re.fullmatch(r'\d{1,10}(?:\.\d{1,' + str(places) + r'})?', value):
        raise InvalidAction
    try:
        out = Decimal(value)
    except InvalidOperation as exc:
        raise InvalidAction from exc
    if not 0 <= out <= max_value:
        raise InvalidAction
    return out


def field(data, key, maximum, *, required=True):
    value = data.get(key, '').strip()
    if len(value) > maximum or (required and not value):
        raise InvalidAction
    return value


def iso_date(data, key, *, required=False):
    value = field(data, key, 10, required=required)
    return date.fromisoformat(value) if value else None


def iso_time(data, key):
    value = field(data, key, 32)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', value):
        raise InvalidAction
    return timezone.make_aware(datetime.fromisoformat(value))


def checked_image(upload):
    if not upload:
        return b''
    if not 0 < upload.size <= 4 * 1024 * 1024:
        raise InvalidAction
    try:
        with Image.open(upload) as img:
            if (img.format not in ('PNG', 'JPEG', 'WEBP') or img.width * img.height > 12_000_000
                    or getattr(img, 'n_frames', 1) != 1):
                raise InvalidAction
            img = ImageOps.exif_transpose(img).convert('RGB')
            img.thumbnail((1400, 1400))
            # Reconstruct pixels without any inherited EXIF/ICC metadata.
            safe = Image.new('RGB', img.size)
            safe.paste(img)
            stream = io.BytesIO()
            safe.save(stream, format='JPEG', quality=82)
            result = stream.getvalue()
            if len(result) > 1024 * 1024:
                raise InvalidAction
            return result
    except (Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise InvalidAction from exc


def normalized_lines(rows):
    out = []
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise InvalidAction
    for row in rows:
        ident = str(row['line_id'])
        if not re.fullmatch(r'\d{1,5}', ident) or any(x['id'] == ident for x in out):
            raise InvalidAction
        qty = number(row.get('purchase_quantity', row['quantity']), QUANTITY_MAX, 4)
        if not qty or row.get('availability') != 'available':
            raise InvalidAction
        price = number(row.get('unit_price'), MONEY_MAX)
        # Current supplier replies keep the procurement title; early pilot
        # snapshots used name. The stored agreement always has a canonical name.
        name = row.get('name') or row.get('title')
        if not isinstance(name, str) or not name.strip():
            raise InvalidAction
        out.append({'id': ident, 'name': name[:255],
                    'unit': str(row.get('purchase_unit') or row.get('unit', ''))[:30],
                    'quantity': str(qty), 'unit_price': str(price)})
    return out


def line_total(lines):
    return sum((Decimal(x['quantity']) * Decimal(x['unit_price'])).quantize(Decimal('.01'),
               rounding=ROUND_HALF_UP) for x in lines)


def offer_rows(repair):
    identity = {'request__project': repair.project, 'request__client_id': repair.project.user_id,
                'request__status__in': OPEN}
    if not repair.agreements.filter(kind='materials').exists():
        candidates = WholeSupplierOffer.objects.filter(**identity, request__request_type='supplier',
            request__target_supplier_id=F('supplier_id'), request__whole_estimate__project=repair.project,
            supplier__is_active=True, supplier__user__is_active=True,
            supplier__user__profile__role='supplier').select_related('supplier', 'request').order_by('-pk')[:30]
        for row in candidates:
            try:
                lines = normalized_lines(row.snapshot['lines'])
                total = number(row.snapshot['total'], MONEY_MAX)
                if total != line_total(lines):
                    continue
            except (KeyError, TypeError, InvalidAction):
                continue
            yield {'kind': 'materials', 'id': row.pk, 'provider': row.supplier.company_name,
                   'partner': row.supplier.user_id, 'request': row.request_id, 'total': str(total),
                   'lines': lines, 'description': str(row.snapshot.get('message') or '')[:2000]}
    if not repair.agreements.filter(kind='works').exists():
        candidates = MasterResponse.objects.filter(**identity,
            request__request_type__in=('master', 'full_repair'), request__target_master_id=F('master_id'),
            master__user__is_active=True, master__user__profile__role='master', status='pending').select_related('master', 'request').order_by('-pk')[:30]
        for row in candidates:
            if not 0 < row.price_from <= MONEY_MAX:
                continue
            snapshot = row.request.request_snapshot
            # Work scope is not inferred from the original price estimate; only the
            # reply text and original package/area reference are preserved.
            area = str(snapshot.get('area', ''))[:20] if isinstance(snapshot, dict) else ''
            package = str(snapshot.get('package', ''))[:30] if isinstance(snapshot, dict) else ''
            yield {'kind': 'works', 'id': row.pk, 'provider': row.master.full_name,
                   'partner': row.master.user_id, 'request': row.request_id, 'total': str(row.price_from),
                   'lines': [], 'description': row.message[:2000], 'source_area': area, 'source_package': package}


def offer_token(repair, user, value):
    return signing.dumps({'project': repair.project_id, 'user': user.pk, 'offer': value}, salt='repairs.offer.v1')


def current_terms(agreement):
    return agreement.versions.filter(accepted_at__isnull=False).first()


def latest_terms(agreement):
    return agreement.versions.first()


def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def receipt_balance(agreement, *, pending=True):
    terms = current_terms(agreement)
    balance = {str(x['id']): Decimal(x['quantity']) for x in terms.lines}
    for delivery in agreement.deliveries.all():
        for key, quantity in delivery.quantities.items():
            if delivery.receipt is None:
                deducted = Decimal(quantity) if pending else Decimal(0)
            else:
                deducted = Decimal(delivery.receipt[key]['received']) - Decimal(delivery.receipt[key]['damaged'])
            balance[key] -= deducted
    return balance


def reference_row(repair, user, role, action, data):
    if action in ('propose_terms', 'confirm_terms', 'schedule_delivery', 'plan_stage'):
        return for_agreement(repair, user, role, data.get('agreement_id')), {}
    if action == 'report_issue':
        key = data.get('target_kind')
        if key not in ('delivery', 'stage'):
            raise InvalidAction
        model = Delivery if key == 'delivery' else Stage
        pk = data.get('target_id')
    elif action == 'confirm_delivery':
        key, model, pk = 'delivery', Delivery, data.get('delivery_id')
    elif action in ('submit_stage', 'accept_stage', 'request_fix'):
        key, model, pk = 'stage', Stage, data.get('stage_id')
    elif action in ('issue_reply', 'resolve_issue'):
        key, model, pk = 'problem', Problem, data.get('problem_id')
    else:
        raise InvalidAction
    row = model.objects.filter(agreement__in=agreement_scope(repair, user, role), pk=pk).first()
    if not row:
        raise Http404
    return row.agreement, {key: row}


def actions_for_role(role, action):
    return action in {
        'client': {'accept_offer', 'confirm_terms', 'confirm_delivery', 'accept_stage', 'request_fix',
                   'report_issue', 'issue_reply'},
        'supplier': {'propose_terms', 'schedule_delivery', 'report_issue', 'issue_reply'},
        'master': {'propose_terms', 'plan_stage', 'submit_stage', 'report_issue', 'issue_reply'},
        'reviewer': {'issue_reply', 'resolve_issue'},
    }.get(role, ())


@transaction.atomic
def perform(user, project_id, data, upload=None):
    repair, role = scoped_repair(user, project_id, lock=True)
    action = data.get('action', '')
    if not actions_for_role(role, action):
        raise Http404
    token = uuid.UUID(data.get('token', ''))
    image = checked_image(upload) if action in ('submit_stage', 'report_issue', 'issue_reply') else b''
    fingerprint = json_digest({'data': {k: v for k, v in data.lists() if k not in ('token', 'csrfmiddlewaretoken')},
                               'image': hashlib.sha256(image).hexdigest()})
    prior = Event.objects.filter(agreement__in=agreement_scope(repair, user, role), actor=user,
                                 action=action, token=token).first()
    if prior:
        if prior.fingerprint != fingerprint:
            raise InvalidAction
        return prior
    payload, related, comment = {}, {}, ''
    if action == 'accept_offer':
        if data.get('confirm') != 'yes':
            raise InvalidAction
        signed = signing.loads(data.get('offer_token', ''), salt='repairs.offer.v1', max_age=3600)
        match = next((x for x in offer_rows(repair) if x['kind'] == data.get('kind')
                      and str(x['id']) == data.get('offer_id')), None)
        if not match or signed != {'project': repair.project_id, 'user': user.pk, 'offer': match}:
            raise InvalidAction
        request = ServiceRequest.objects.select_for_update().filter(pk=match['request'], status__in=OPEN,
                    project_id=repair.project_id, client=user).first()
        if not request:
            raise InvalidAction
        # Re-read after locking against legacy request mutation.
        if match not in list(offer_rows(repair)):
            raise InvalidAction
        config = {'supplier_offer_id': match['id']} if match['kind'] == 'materials' else {'master_response_id': match['id']}
        a = Agreement.objects.create(repair=repair, partner_id=match['partner'], request=request,
             provider=match['provider'], kind=match['kind'], original_offer=match, **config)
        if a.master_response_id:
            MasterResponse.objects.filter(pk=a.master_response_id).update(status='accepted')
        request.status = 'accepted'
        request.save(update_fields=['status'])
        Terms.objects.create(agreement=a, revision=1, total=match['total'], lines=match['lines'],
            description=match['description'], proposed_by_id=match['partner'], accepted_by=user, accepted_at=timezone.now())
        payload = {'revision': 1}
    else:
        a, related = reference_row(repair, user, role, action, data)
        if action == 'propose_terms':
            active = current_terms(a)
            latest = latest_terms(a)
            if latest.accepted_at is None:
                raise InvalidAction
            total = number(data.get('total', ''), MONEY_MAX)
            starts, ends = iso_date(data, 'starts_on'), iso_date(data, 'ends_on')
            if starts and ends and starts > ends:
                raise InvalidAction
            lines = [dict(x) for x in active.lines]
            if lines:
                used = receipt_balance(a)
                for line in lines:
                    k = line['id']
                    qty = number(data.get('qty_' + k, line['quantity']), QUANTITY_MAX, 4)
                    if not qty or qty < Decimal(line['quantity']) - used[k]:
                        raise InvalidAction
                    line['quantity'] = str(qty)
                    line['unit_price'] = str(number(data.get('price_' + k, line['unit_price']), MONEY_MAX))
                if total != line_total(lines):
                    raise InvalidAction
            p = Terms.objects.create(agreement=a, revision=latest.revision+1, total=total,
                     starts_on=starts, ends_on=ends, description=field(data, 'description', 2000, required=False),
                     lines=lines, proposed_by=user)
            payload = {'revision': p.revision}
        elif action == 'confirm_terms':
            p = latest_terms(a)
            if not p or p.accepted_at or str(p.pk) != data.get('revision_id'):
                raise InvalidAction
            if p.lines:
                active = current_terms(a)
                used = receipt_balance(a)
                after = {x['id']: Decimal(x['quantity']) for x in p.lines}
                if any(after[x['id']] < Decimal(x['quantity']) - used[x['id']] for x in active.lines):
                    raise InvalidAction
            p.accepted_at, p.accepted_by = timezone.now(), user
            p.save(update_fields=['accepted_at', 'accepted_by'])
            payload = {'revision': p.revision}
        elif action == 'schedule_delivery':
            if a.kind != 'materials':
                raise Http404
            start, end = iso_time(data, 'window_start'), iso_time(data, 'window_end')
            if end <= start:
                raise InvalidAction
            quantities = {}
            for key, remaining in receipt_balance(a).items():
                qty = number(data.get('qty_' + key, '0') or '0', QUANTITY_MAX, 4)
                if qty > remaining:
                    raise InvalidAction
                if qty:
                    quantities[key] = str(qty)
            if not quantities:
                raise InvalidAction
            related['delivery'] = Delivery.objects.create(agreement=a, window_start=start, window_end=end, quantities=quantities)
        elif action == 'confirm_delivery':
            delivery = related['delivery']
            if delivery.receipt is not None:
                raise InvalidAction
            receipt = {}
            for key, expected in delivery.quantities.items():
                actual = number(data.get('received_' + key, ''), QUANTITY_MAX, 4)
                damaged = number(data.get('damaged_' + key, '0') or '0', QUANTITY_MAX, 4)
                if not 0 <= damaged <= actual <= Decimal(expected):
                    raise InvalidAction
                receipt[key] = {'received': str(actual), 'damaged': str(damaged), 'missing': str(Decimal(expected)-actual)}
            delivery.receipt, delivery.confirmed_at = receipt, timezone.now()
            delivery.save(update_fields=['receipt', 'confirmed_at'])
        elif action == 'plan_stage':
            if a.kind != 'works':
                raise Http404
            related['stage'] = Stage.objects.create(agreement=a, title=field(data, 'title', 200),
                                                    due_on=iso_date(data, 'due_on', required=True))
        elif action in ('submit_stage', 'accept_stage', 'request_fix'):
            stage = related['stage']
            if action == 'submit_stage':
                if stage.state not in ('planned', 'fix') or not image:
                    raise InvalidAction
                stage.state, stage.submission = 'review', stage.submission + 1
            else:
                if stage.state != 'review':
                    raise InvalidAction
                # A form opened on a prior submission cannot approve the next one.
                if str(stage.submission) != data.get('submission'):
                    raise InvalidAction
                stage.state = 'accepted' if action == 'accept_stage' else 'fix'
            stage.save(update_fields=['state', 'submission'])
            comment = field(data, 'comment', 2000, required=action=='request_fix')
            payload = {'submission': stage.submission}
        elif action == 'report_issue':
            comment = field(data, 'comment', 2000)
            related['problem'] = Problem.objects.create(agreement=a, opened_by=user, **related)
        elif action in ('issue_reply', 'resolve_issue'):
            problem = related['problem']
            if problem.resolved_at:
                raise InvalidAction
            comment = field(data, 'comment', 2000)
            if action == 'resolve_issue':
                problem.resolved_at = timezone.now()
                problem.save(update_fields=['resolved_at'])
    event = Event.objects.create(agreement=a, actor=user, action=action, token=token,
                                 fingerprint=fingerprint, data=payload, comment=comment, **related)
    if image:
        Photo.objects.create(event=event, jpeg=image)
    return event
