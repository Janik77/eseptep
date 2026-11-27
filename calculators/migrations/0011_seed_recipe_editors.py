from django.db import migrations

WORK = [
    ('demontazh', 'Демонтаж'), ('elektrika', 'Электрика'), ('santehnika', 'Сантехника'),
    ('shtukaturka', 'Штукатурные работы'), ('gipsokarton-potolok', 'Гипсокартон'),
    ('nalivnoy-pol', 'Наливной пол'), ('plitka-keramogranit', 'Плитка / Керамогранит'),
    ('laminat-spc-parket', 'Напольное покрытие'), ('malyarka', 'Малярка'),
    ('natyazhnoy-potolok', 'Натяжной потолок'), ('dveri', 'Двери'), ('teplyy-pol', 'Тёплый пол'),
]


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    calcs = apps.get_model('calculators', 'RecipeCalculator').objects.using(alias)
    calcs.bulk_create([calcs.model(slug=key, title=title) for key,title in WORK], ignore_conflicts=True)
    types = apps.get_model('contenttypes', 'ContentType').objects.using(alias)
    content, _ = types.get_or_create(app_label='calculators', model='recipecalculator')
    permissions = apps.get_model('auth', 'Permission').objects.using(alias)
    group, _ = apps.get_model('auth','Group').objects.using(alias).get_or_create(name='Редактор калькуляторов')
    for action in ('view','change'):
        permission, _ = permissions.get_or_create(content_type=content, codename=f'{action}_recipecalculator',
                                                     defaults={'name':f'Can {action} recipe calculator'})
        group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [('calculators','0010_recipecalculator_recipeedition_and_more'),
                    ('auth','0012_alter_user_first_name_max_length')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
