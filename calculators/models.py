from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


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
    store_name = models.CharField(_('Магазин'), max_length=160)
    version = models.CharField(_('Версия'), max_length=60, unique=True)
    source_note = models.CharField(_('Источник и область применения'), max_length=255)
    price_date = models.DateField(_('Дата цен'))
    is_active = models.BooleanField(_('Действует'), default=False)
    published_at = models.DateTimeField(_('Опубликовано'), null=True, blank=True, editable=False)

    class Meta:
        verbose_name = _('прайс магазина')
        verbose_name_plural = _('прайсы магазина')
        constraints = [models.UniqueConstraint(fields=['is_active'], condition=models.Q(is_active=True), name='one_active_price_book')]

    def __str__(self):
        return f'{self.store_name} / {self.version}'


class MaterialPrice(models.Model):
    book = models.ForeignKey(PriceBook, verbose_name=_('Прайс'), on_delete=models.PROTECT, related_name='entries')
    calculator_slug = models.CharField(_('Калькулятор'), max_length=80)
    variant_key = models.CharField(_('Вариант'), max_length=30, blank=True)
    material_key = models.CharField(_('Материал'), max_length=30)
    unit = models.CharField(_('Единица'), max_length=30)
    price = models.DecimalField(_('Цена за единицу, ₸'), max_digits=12, decimal_places=2)
    price_basis = models.CharField(_('Основа цены'), max_length=12,
        choices=[('canonical', _('За расчётную единицу')), ('pack', _('За упаковку'))], default='canonical')
    pack_coverage = models.DecimalField(_('В упаковке, в расчётных единицах'),
        max_digits=10, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name = _('цена материала')
        verbose_name_plural = _('цены материалов')
        constraints = [
            models.UniqueConstraint(fields=['book', 'calculator_slug', 'variant_key', 'material_key', 'unit'], name='unique_scoped_material_price'),
            models.CheckConstraint(condition=models.Q(price__gt=0), name='positive_material_price'),
            models.CheckConstraint(
                condition=(models.Q(price_basis='canonical', pack_coverage__isnull=True)
                           | models.Q(price_basis='pack', unit__in=['м²', 'м'],
                                      pack_coverage__isnull=False, pack_coverage__gt=0)),
                name='valid_material_price_basis',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        from .definitions import CALCULATORS_BY_SLUG
        from .material_keys import BY_KEY
        definition = BY_KEY.get(self.material_key)
        if not definition or definition['unit'] != self.unit:
            raise ValidationError({'material_key': _('Материал не найден или единица не совпадает со справочником.')})
        if self.calculator_slug not in CALCULATORS_BY_SLUG:
            raise ValidationError({'calculator_slug': _('Выберите существующий калькулятор.')})
        if self.price_basis == 'pack' and (
            self.unit not in ('м²', 'м') or self.pack_coverage is None
            or not isinstance(self.pack_coverage, Decimal) or not self.pack_coverage.is_finite() or self.pack_coverage <= 0
        ):
            raise ValidationError({'pack_coverage': _('Укажите положительное количество м² или м в упаковке.')})
        if self.price_basis == 'canonical' and self.pack_coverage is not None:
            raise ValidationError({'pack_coverage': _('Для цены за расчётную единицу оставьте поле пустым.')})
        from .material_keys import variant_keys
        if self.variant_key not in variant_keys(self.calculator_slug):
            raise ValidationError({'variant_key': _('Этот вариант не относится к выбранному калькулятору.')})
        if self.book_id and self.book.published_at:
            raise ValidationError(_('Опубликованный прайс нельзя изменить. Создайте новую версию.'))


class PriceConfigurationLock(models.Model):
    """Singleton serialization row for publication and estimate persistence."""
    revision = models.PositiveIntegerField(default=0)


class RenovationRateEdition(models.Model):
    """Typed whole-project KZT/m² rates, not material consumption norms."""
    version = models.CharField(_('Версия'), max_length=60, unique=True)
    source_note = models.CharField(_('Источник и область применения'), max_length=255)
    effective_date = models.DateField(_('Дата действия'))
    economy_rate = models.DecimalField(_('Эконом, ₸/м²'), max_digits=12, decimal_places=2)
    standard_rate = models.DecimalField(_('Стандарт, ₸/м²'), max_digits=12, decimal_places=2)
    premium_rate = models.DecimalField(_('Премиум, ₸/м²'), max_digits=12, decimal_places=2)
    is_active = models.BooleanField(_('Действует'), default=False)
    published_at = models.DateTimeField(_('Опубликовано'), null=True, blank=True, editable=False)

    class Meta:
        verbose_name = _('ставки ремонта под ключ')
        verbose_name_plural = _('ставки ремонта под ключ')
        constraints = [
            models.UniqueConstraint(fields=['is_active'], condition=models.Q(is_active=True), name='one_active_renovation_rate_edition'),
            models.CheckConstraint(condition=models.Q(economy_rate__gt=0, standard_rate__gt=0, premium_rate__gt=0), name='positive_typed_renovation_rates'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        from core.renovation_rates import LEGACY_VERSION
        if self.version == LEGACY_VERSION:
            raise ValidationError({'version': _('Это обозначение зарезервировано для исторических расчётов.')})

    def __str__(self):
        return self.version


class SelfLevelMixEdition(models.Model):
    """One preliminary consumption parameter; fixed cm input and 25 kg bag."""
    version = models.CharField(_('Версия'), max_length=60, unique=True)
    source_note = models.CharField(_('Источник и область применения'), max_length=255)
    source_date = models.DateField(_('Дата источника'))
    unit = models.CharField(_('Единица'), max_length=24, choices=[('kg_per_m2_cm', 'кг/(м²·см)')], default='kg_per_m2_cm', editable=False)
    consumption = models.DecimalField(_('Расход смеси, кг/(м²·см)'), max_digits=4, decimal_places=2, default=15)
    is_active = models.BooleanField(_('Действует'), default=False)
    published_at = models.DateTimeField(_('Опубликовано'), null=True, blank=True, editable=False)

    class Meta:
        verbose_name = _('расход смеси наливного пола')
        verbose_name_plural = _('расход смеси наливного пола')
        constraints = [
            models.UniqueConstraint(fields=['is_active'], condition=models.Q(is_active=True), name='one_active_selflevel_mix_edition'),
            models.CheckConstraint(condition=models.Q(consumption__gte='0.01', consumption__lte='99.99', unit='kg_per_m2_cm'), name='typed_selflevel_consumption_unit_range'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        from .self_level_parameters import LEGACY_VERSION
        if self.version == LEGACY_VERSION:
            raise ValidationError({'version': _('Это обозначение зарезервировано для исторических расчётов.')})

    def __str__(self):
        return self.version


class DemolitionFilmEdition(models.Model):
    """One preliminary protective film ratio; square metres per square metre."""
    version = models.CharField(_('Версия'), max_length=60, unique=True)
    source_note = models.CharField(_('Источник и область применения'), max_length=255)
    source_date = models.DateField(_('Дата источника'))
    unit = models.CharField(_('Единица'), max_length=24, choices=[('m2_per_m2', 'м²/м²')], default='m2_per_m2', editable=False)
    consumption = models.DecimalField(_('Расход защитной плёнки, м²/м²'), max_digits=4, decimal_places=2, default='1.20')
    is_active = models.BooleanField(_('Действует'), default=False)
    published_at = models.DateTimeField(_('Опубликовано'), null=True, blank=True, editable=False)

    class Meta:
        verbose_name = _('коэффициент защитной плёнки')
        verbose_name_plural = _('коэффициенты защитной плёнки')
        constraints = [
            models.UniqueConstraint(fields=['is_active'], condition=models.Q(is_active=True), name='one_active_demolition_film_edition'),
            models.CheckConstraint(condition=models.Q(consumption__gte='0.01', consumption__lte='99.99', unit='m2_per_m2'), name='typed_demolition_film_unit_range'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        from .demolition_parameters import LEGACY_VERSION
        if self.version == LEGACY_VERSION:
            raise ValidationError({'version': _('Это обозначение зарезервировано для исторических расчётов.')})

    def __str__(self):
        return self.version
