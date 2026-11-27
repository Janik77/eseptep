"""Signed render intents and database-enforced, atomic POST receipts."""
import hashlib
import json
import uuid

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils.translation import gettext as _

from accounts.models import CalculationSubmission, ServiceRequest, UserProfile

SALT = 'calculators.result-submission.v1'
ERROR = 'Результат изменился или ссылка сохранения недействительна. Выполните расчёт заново.'


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _inputs(data):
    # Variant is selectable after render, and becomes immutable in the receipt.
    return {key: str(value) for key, value in data.items() if key != 'selected_variant'}


def result_token(user, slug, data):
    return signing.dumps({'user': user.pk, 'slug': slug, 'input': _digest(_inputs(data)),
                          'nonce': str(uuid.uuid4())}, salt=SALT)


def submit_result(user, slug, data, post, result, save):
    if not user.is_authenticated or getattr(getattr(user, 'profile', None), 'role', None) != UserProfile.Role.CLIENT:
        raise PermissionDenied('Сохранять расчёты может только клиент.')
    try:
        intent = signing.loads(post.get('submission_token', ''), salt=SALT)
        nonce = uuid.UUID(intent['nonce'])
        if (intent['user'], intent['slug'], intent['input']) != (user.pk, slug, _digest(_inputs(data))):
            raise ValueError
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise ValidationError(_(ERROR))
    action = post.get('action')
    if action not in {'save_estimate', 'request_master', 'request_supplier'}:
        raise ValidationError(_(ERROR))
    fingerprint = _digest({key: post.get(key, '') for key in (
        'project_id', 'selected_variant', 'parameter_version', 'price_book_version', 'recipe_version')})
    return _persist_submission(user, slug, post, result, save, nonce, action, fingerprint)


@transaction.atomic
def _persist_submission(user, slug, post, result, save, nonce, action, fingerprint):
    # Acquire SQLite's write reservation before SELECT; PostgreSQL additionally
    # serializes existing receipts here, with UNIQUE arbitrating new receipts.
    CalculationSubmission.objects.filter(user=user, nonce=nonce, action=action).update(fingerprint=F('fingerprint'))
    # INSERT/unique constraint arbitrates concurrent callers before any snapshot
    # reads (also avoiding SQLite read-to-write upgrades). A failed transaction
    # rolls back the reservation, calculation and service request together.
    receipt, created = CalculationSubmission.objects.get_or_create(
        user=user, nonce=nonce, action=action, defaults={'fingerprint': fingerprint},
    )
    if not created:
        if receipt.fingerprint != fingerprint or receipt.calculation_id is None:
            raise ValidationError(_(ERROR))
        return receipt.calculation
    actual = (result.get('parameter_snapshot') or {}).get('version', '')
    if post.get('parameter_version', '') != actual:
        message = ('Параметр защитной плёнки изменился. Проверьте новый расчёт и сохраните снова.'
                   if slug == 'demontazh' else 'Параметр расхода изменился. Проверьте новый расчёт и сохраните снова.')
        raise ValidationError(_(message))
    if post.get('price_book_version', '') != (result.get('admin_quote') or {}).get('version', ''):
        raise ValidationError(_('Прайс изменился. Проверьте новый расчёт и сохраните снова.'))
    if post.get('recipe_version', '') != (result.get('recipe_snapshot') or {}).get('version', ''):
        raise ValidationError(_('Настройки материалов изменились. Выполните расчёт заново.'))
    project, calculation = save(user, slug, result, post.get('project_id'))
    if action != 'save_estimate':
        ServiceRequest.objects.create(
            client=user, project=project, calculation=calculation,
            request_type=(ServiceRequest.RequestType.MASTER if action == 'request_master'
                          else ServiceRequest.RequestType.SUPPLIER),
            status=ServiceRequest.Status.NEW,
            comment=f'Заявка после расчёта: {slug}',
        )
    receipt.calculation = calculation
    receipt.save(update_fields=['calculation'])
    return calculation
