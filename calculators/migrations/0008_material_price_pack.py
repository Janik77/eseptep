from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('calculators', '0007_admin_labels')]
    operations = [
        migrations.AddField(model_name='materialprice', name='price_basis',
            field=models.CharField(choices=[('canonical', 'За расчётную единицу'), ('pack', 'За упаковку')],
                default='canonical', max_length=12, verbose_name='Основа цены')),
        migrations.AddField(model_name='materialprice', name='pack_coverage',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=10, null=True,
                verbose_name='В упаковке, в расчётных единицах')),
        migrations.AddConstraint(model_name='materialprice',
            constraint=models.CheckConstraint(
                condition=(models.Q(price_basis='canonical', pack_coverage__isnull=True)
                           | models.Q(price_basis='pack', unit__in=['м²', 'м'],
                                      pack_coverage__isnull=False, pack_coverage__gt=0)),
                name='valid_material_price_basis')),
    ]
