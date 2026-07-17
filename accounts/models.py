from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class UserProfile(models.Model):
    class Role(models.TextChoices):
        CLIENT = 'client', 'Клиент'
        MASTER = 'master', 'Мастер'
        SUPPLIER = 'supplier', 'Поставщик'
        ADMIN = 'admin', 'Администратор'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    phone = models.CharField(max_length=32, blank=True)
    city = models.CharField(max_length=120, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f'{self.user} ({self.get_role_display()})'


class ClientProject(models.Model):
    class RepairSegment(models.TextChoices):
        ECONOMY = 'economy', 'Эконом'
        COMFORT = 'comfort', 'Комфорт'
        BUSINESS = 'business', 'Бизнес'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Черновик'
        CALCULATED = 'calculated', 'Рассчитан'
        SUBMITTED = 'submitted', 'Отправлен'
        IN_PROGRESS = 'in_progress', 'В работе'
        DONE = 'done', 'Завершен'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_projects')
    title = models.CharField(max_length=255)
    city = models.CharField(max_length=120)
    area_m2 = models.DecimalField(max_digits=10, decimal_places=2)
    rooms = models.PositiveSmallIntegerField()
    repair_segment = models.CharField(
        max_length=20,
        choices=RepairSegment.choices,
        default=RepairSegment.COMFORT,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Проект клиента'
        verbose_name_plural = 'Проекты клиентов'

    def __str__(self):
        return self.title


class Calculation(models.Model):
    project = models.ForeignKey(ClientProject, on_delete=models.CASCADE, related_name='calculations')
    calculator_slug = models.SlugField(max_length=100)
    area_m2 = models.DecimalField(max_digits=10, decimal_places=2)
    rooms = models.PositiveSmallIntegerField()
    thickness = models.DecimalField(max_digits=8, decimal_places=2)
    segment = models.CharField(max_length=20, choices=ClientProject.RepairSegment.choices)
    materials_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    works_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    result_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Расчет'
        verbose_name_plural = 'Расчеты'

    def __str__(self):
        return f'{self.project.title} · {self.calculator_slug}'


class MasterProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='master_profile')
    full_name = models.CharField(max_length=255)
    city = models.CharField(max_length=120)
    specialization = models.CharField(max_length=255)
    experience_years = models.PositiveSmallIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    is_available = models.BooleanField(default=True)
    whatsapp = models.CharField(max_length=32, blank=True)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='masters/', blank=True, null=True)

    class Meta:
        verbose_name = 'Профиль мастера'
        verbose_name_plural = 'Профили мастеров'

    def __str__(self):
        return self.full_name


class SupplierProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='supplier_profile')
    company_name = models.CharField(max_length=255)
    city = models.CharField(max_length=120)
    address = models.CharField(max_length=255)
    whatsapp = models.CharField(max_length=32, blank=True)
    delivery_info = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Профиль поставщика'
        verbose_name_plural = 'Профили поставщиков'

    def __str__(self):
        return self.company_name


class SupplierMaterial(models.Model):
    supplier = models.ForeignKey(SupplierProfile, on_delete=models.CASCADE, related_name='materials')
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=120)
    unit = models.CharField(max_length=30)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock_status = models.CharField(max_length=120)
    delivery_time = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name = 'Материал поставщика'
        verbose_name_plural = 'Материалы поставщиков'

    def __str__(self):
        return f'{self.name} ({self.supplier.company_name})'


class ServiceRequest(models.Model):
    class RequestType(models.TextChoices):
        MASTER = 'master', 'Мастер'
        SUPPLIER = 'supplier', 'Поставщик'
        FULL_REPAIR = 'full_repair', 'Ремонт под ключ'

    class Status(models.TextChoices):
        NEW = 'new', 'Новая'
        VIEWED = 'viewed', 'Просмотрена'
        RESPONDED = 'responded', 'Есть ответ'
        ACCEPTED = 'accepted', 'Принята'
        REJECTED = 'rejected', 'Отклонена'
        CLOSED = 'closed', 'Закрыта'

    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_requests')
    project = models.ForeignKey(ClientProject, on_delete=models.CASCADE, related_name='service_requests')
    calculation = models.ForeignKey(
        Calculation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_requests',
    )
    request_type = models.CharField(max_length=20, choices=RequestType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Заявка на сервис'
        verbose_name_plural = 'Заявки на сервис'

    def __str__(self):
        return f'#{self.pk} {self.project.title}'


class MasterResponse(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        ACCEPTED = 'accepted', 'Принят'
        REJECTED = 'rejected', 'Отклонен'

    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='master_responses')
    master = models.ForeignKey(MasterProfile, on_delete=models.CASCADE, related_name='responses')
    price_from = models.DecimalField(max_digits=12, decimal_places=2)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Ответ мастера'
        verbose_name_plural = 'Ответы мастеров'

    def __str__(self):
        return f'{self.master.full_name} → #{self.request_id}'


class SupplierResponse(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        ACCEPTED = 'accepted', 'Принят'
        REJECTED = 'rejected', 'Отклонен'

    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='supplier_responses')
    supplier = models.ForeignKey(SupplierProfile, on_delete=models.CASCADE, related_name='responses')
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Ответ поставщика'
        verbose_name_plural = 'Ответы поставщиков'

    def __str__(self):
        return f'{self.supplier.company_name} → #{self.request_id}'
