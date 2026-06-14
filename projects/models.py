from django.db import models


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
    file = models.FileField('Файл', upload_to='project_uploads/')
    comment = models.TextField('Комментарий', blank=True)
    area = models.DecimalField('Площадь квартиры', max_digits=8, decimal_places=2, null=True, blank=True)
    repair_level = models.CharField('Уровень ремонта', max_length=20, choices=RepairLevel.choices, blank=True)
    ai_status = models.CharField('AI статус', max_length=20, default=AI_ANALYSIS_MODE)
    ai_summary = models.JSONField('AI summary', default=dict, blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'загрузка проекта'
        verbose_name_plural = 'загрузки проектов'
        ordering = ['-created_at']

    def __str__(self):
        return f'Загрузка проекта #{self.pk or "new"}'
