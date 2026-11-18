from django.db import models
from .storage import private_storage


class RenovationProject(models.Model):
    """Заявка пользователя на расчёт ремонта по проекту или плану."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Черновик'
        UPLOADED = 'uploaded', 'Загружен'
        IN_REVIEW = 'in_review', 'На проверке'
        READY = 'ready', 'Готов к расчёту'

    title = models.CharField('Название проекта', max_length=160)
    customer_name = models.CharField('Имя клиента', max_length=120, blank=True)
    phone = models.CharField('Телефон', max_length=40, blank=True)
    area = models.DecimalField('Площадь, м²', max_digits=8, decimal_places=2, null=True, blank=True)
    file = models.FileField('Файл проекта', upload_to='projects/', blank=True)
    status = models.CharField('Статус', max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'проект ремонта'
        verbose_name_plural = 'проекты ремонта'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class ProjectUpload(models.Model):
    """MVP загрузка планировки для demo AI-анализа."""

    class RepairLevel(models.TextChoices):
        ECONOMY = 'economy', 'Эконом'
        STANDARD = 'standard', 'Стандарт'
        PREMIUM = 'premium', 'Премиум'

    AI_ANALYSIS_MODE = 'demo'

    user = models.ForeignKey('auth.User', verbose_name='Пользователь', on_delete=models.SET_NULL, null=True, blank=True, related_name='project_uploads')
    file = models.FileField('Файл', upload_to='project_uploads/', storage=private_storage)
    guest_session_key = models.CharField(max_length=40, blank=True, editable=False, db_index=True)
    comment = models.TextField('Комментарий', blank=True)
    area = models.DecimalField('Площадь квартиры', max_digits=8, decimal_places=2, null=True, blank=True)
    repair_level = models.CharField('Уровень ремонта', max_length=20, choices=RepairLevel.choices, blank=True)
    ai_status = models.CharField('AI статус', max_length=20, default=AI_ANALYSIS_MODE)
    ai_summary = models.JSONField('AI summary', default=dict, blank=True)
    estimate_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'загрузка проекта'
        verbose_name_plural = 'загрузки проектов'
        ordering = ['-created_at']

    def __str__(self):
        return f'Загрузка проекта #{self.pk or "new"}'


class PlanAnalysisBudget(models.Model):
    """Persistent, pessimistic pilot spending reservation. Never automatically refunded."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    reserved_cents = models.PositiveIntegerField(default=0)


class PlanAnalysis(models.Model):
    # Identity includes owner/session; identical file reuploads cannot trigger another charge.
    identity = models.CharField(max_length=64, unique=True)
    upload = models.ForeignKey(ProjectUpload, on_delete=models.CASCADE)
    status = models.CharField(max_length=16, default='running')
    rooms = models.JSONField(default=list)
    model = models.CharField(max_length=80, default='gpt-4.1-mini-2025-04-14')
    usage = models.JSONField(default=dict)
    elapsed_ms = models.PositiveIntegerField(default=0)
    request_id = models.CharField(max_length=160, blank=True)
    error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PlanConfirmation(models.Model):
    upload = models.ForeignKey(ProjectUpload, on_delete=models.CASCADE)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
