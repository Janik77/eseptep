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
