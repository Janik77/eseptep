from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('projects', '0006_wholeplanestimate')]

    operations = [
        migrations.AddField(
            model_name='projectupload',
            name='source_sha256',
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
    ]
