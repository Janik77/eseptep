import unicodedata
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


def city_key(value):
    return ' '.join(unicodedata.normalize('NFKC', value).split()).casefold()


class PilotCity(models.Model):
    key = models.CharField(max_length=120, unique=True, editable=False)
    name = models.CharField(max_length=120, verbose_name=_('Город'))
    enabled = models.BooleanField(default=False, verbose_name=_('Пилот включён'))

    class Meta:
        verbose_name = _('Город пилота «Мой ремонт»')
        verbose_name_plural = _('Города пилота «Мой ремонт»')

    def save(self, *args, **kwargs):
        self.name = ' '.join(unicodedata.normalize('NFKC', self.name).split())
        self.key = city_key(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Repair(models.Model):
    project = models.OneToOneField('accounts.ClientProject', on_delete=models.PROTECT, related_name='repair')
    city = models.ForeignKey(PilotCity, on_delete=models.PROTECT)
    enabled = models.BooleanField(default=False, verbose_name=_('Доступ для этого проекта'))
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    # Never included in project timeline, change snapshots, or partner contexts by default.
    delivery_address = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _('Проект пилота «Мой ремонт»')
        verbose_name_plural = _('Проекты пилота «Мой ремонт»')

    def __str__(self):
        return self.project.title


class Agreement(models.Model):
    class Kind(models.TextChoices):
        MATERIALS = 'materials', _('Материалы')
        WORKS = 'works', _('Работы')

    repair = models.ForeignKey(Repair, on_delete=models.PROTECT, related_name='agreements')
    request = models.OneToOneField('accounts.ServiceRequest', on_delete=models.PROTECT)
    supplier_offer = models.OneToOneField('accounts.WholeSupplierOffer', null=True, blank=True, on_delete=models.PROTECT)
    master_response = models.OneToOneField('accounts.MasterResponse', null=True, blank=True, on_delete=models.PROTECT)
    partner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=9, choices=Kind.choices)
    provider = models.CharField(max_length=255)
    original_offer = models.JSONField(editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['repair', 'kind'], name='repair_one_agreement_per_kind'),
            models.CheckConstraint(condition=(
                models.Q(kind='materials', supplier_offer__isnull=False, master_response__isnull=True)
                | models.Q(kind='works', supplier_offer__isnull=True, master_response__isnull=False)
            ), name='repair_exactly_one_offer'),
        ]


class Terms(models.Model):
    agreement = models.ForeignKey(Agreement, on_delete=models.PROTECT, related_name='versions')
    revision = models.PositiveIntegerField()
    total = models.DecimalField(max_digits=12, decimal_places=2)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=2000, blank=True)
    lines = models.JSONField(default=list)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['agreement', 'revision'], name='repair_distinct_revision')]
        ordering = ['-revision']


class Delivery(models.Model):
    agreement = models.ForeignKey(Agreement, on_delete=models.PROTECT, related_name='deliveries')
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    quantities = models.JSONField()
    receipt = models.JSONField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)


class Stage(models.Model):
    class State(models.TextChoices):
        PLANNED = 'planned', _('Запланировано')
        REVIEW = 'review', _('На приёмке')
        FIX = 'fix', _('Нужна доработка')
        ACCEPTED = 'accepted', _('Принято')

    agreement = models.ForeignKey(Agreement, on_delete=models.PROTECT, related_name='stages')
    title = models.CharField(max_length=200)
    due_on = models.DateField()
    state = models.CharField(max_length=10, default=State.PLANNED, choices=State.choices)
    submission = models.PositiveIntegerField(default=0)


class Problem(models.Model):
    agreement = models.ForeignKey(Agreement, on_delete=models.PROTECT, related_name='problems')
    delivery = models.ForeignKey(Delivery, null=True, blank=True, on_delete=models.PROTECT)
    stage = models.ForeignKey(Stage, null=True, blank=True, on_delete=models.PROTECT)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(
            models.Q(delivery__isnull=False, stage__isnull=True) | models.Q(delivery__isnull=True, stage__isnull=False)
        ), name='repair_problem_exact_target')]


class Event(models.Model):
    agreement = models.ForeignKey(Agreement, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=30)
    token = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    data = models.JSONField(default=dict)
    comment = models.CharField(max_length=2000, blank=True)
    delivery = models.ForeignKey(Delivery, null=True, blank=True, on_delete=models.PROTECT, related_name='events')
    stage = models.ForeignKey(Stage, null=True, blank=True, on_delete=models.PROTECT, related_name='events')
    problem = models.ForeignKey(Problem, null=True, blank=True, on_delete=models.PROTECT, related_name='events')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['agreement', 'actor', 'action', 'token'],
                                               name='repair_unique_action_token')]
        ordering = ['pk']


class Photo(models.Model):
    # Size and format are checked and metadata stripped before persisting. Bytes are never
    # served by MEDIA_URL. Keeping this bounded pilot attachment transactional avoids orphans.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.OneToOneField(Event, on_delete=models.PROTECT, related_name='photo')
    jpeg = models.BinaryField(editable=False)
