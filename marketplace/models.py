from django.db import models


class ServiceCategory(models.Model):
    """Категория услуг для будущего маркетплейса ремонта."""

    title = models.CharField('Название', max_length=120)
    slug = models.SlugField('Слаг', unique=True)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'категория услуг'
        verbose_name_plural = 'категории услуг'
        ordering = ['title']

    def __str__(self):
        return self.title


class ServicePackage(models.Model):
    """Базовый пакет ремонта под ключ."""

    category = models.ForeignKey(
        ServiceCategory,
        verbose_name='Категория',
        related_name='packages',
        on_delete=models.PROTECT,
    )
    title = models.CharField('Название', max_length=140)
    slug = models.SlugField('Слаг', unique=True)
    short_description = models.CharField('Краткое описание', max_length=255, blank=True)
    base_price = models.DecimalField('Базовая цена', max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'пакет услуг'
        verbose_name_plural = 'пакеты услуг'
        ordering = ['title']

    def __str__(self):
        return self.title
