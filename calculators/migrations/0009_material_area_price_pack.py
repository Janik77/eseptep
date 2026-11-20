from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('calculators', '0008_material_price_pack')]
    operations = [
        migrations.RemoveConstraint(model_name='materialprice', name='valid_material_price_basis'),
        migrations.AddConstraint(
            model_name='materialprice',
            constraint=models.CheckConstraint(
                condition=(models.Q(price_basis='canonical', pack_coverage__isnull=True)
                    | models.Q(price_basis__in=['canonical', 'pack'], unit__in=['м²', 'м'],
                               pack_coverage__isnull=False, pack_coverage__gt=0)),
                name='valid_material_price_basis',
            ),
        ),
    ]
