from django.db import models


class CalculatorCategory(models.Model):
    """Группа калькуляторов для будущих расчётов ремонта."""

    title = models.CharField('Название', max_length=120)
    slug = models.SlugField('Слаг', unique=True)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активна', default=True)
    sort_order = models.PositiveSmallIntegerField('Порядок', default=0)
    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'категория калькуляторов'
        verbose_name_plural = 'категории калькуляторов'
        ordering = ['sort_order', 'title']

    def __str__(self):
        return self.title


class CalculatorTemplate(models.Model):
    """Заготовка калькулятора: тип, единицы измерения и описание сценария."""

    category = models.ForeignKey(
        CalculatorCategory,
        verbose_name='Категория',
        related_name='templates',
        on_delete=models.PROTECT,
    )
    title = models.CharField('Название', max_length=140)
    slug = models.SlugField('Слаг', unique=True)
    unit = models.CharField('Единица измерения', max_length=40, default='м²')
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'шаблон калькулятора'
        verbose_name_plural = 'шаблоны калькуляторов'
        ordering = ['title']

    def __str__(self):
        return self.title


class PriceBook(models.Model):
    """A manually supplied store price edition, never an inferred market price."""
    store_name = models.CharField(max_length=160)
    version = models.CharField(max_length=60, unique=True)
    source_note = models.CharField(max_length=255)
    price_date = models.DateField()
    is_active = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['is_active'], condition=models.Q(is_active=True), name='one_active_price_book')]

    def __str__(self):
        return f'{self.store_name} / {self.version}'


class MaterialPrice(models.Model):
    book = models.ForeignKey(PriceBook, on_delete=models.PROTECT, related_name='entries')
    calculator_slug = models.CharField(max_length=80)
    variant_key = models.CharField(max_length=30, blank=True)
    material_key = models.CharField(max_length=30)
    unit = models.CharField(max_length=30)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['book', 'calculator_slug', 'variant_key', 'material_key', 'unit'], name='unique_scoped_material_price'),
            models.CheckConstraint(condition=models.Q(price__gt=0), name='positive_material_price'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        from .definitions import CALCULATORS_BY_SLUG
        from .material_keys import BY_KEY
        definition = BY_KEY.get(self.material_key)
        if not definition or definition['unit'] != self.unit:
            raise ValidationError({'material_key': 'Unknown material key or mismatched unit.'})
        if self.calculator_slug not in CALCULATORS_BY_SLUG:
            raise ValidationError({'calculator_slug': 'Unknown calculator key.'})
        if self.book_id and self.book.published_at:
            raise ValidationError('Published prices are immutable. Create a new price book version.')
