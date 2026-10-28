from django.db import migrations,models


class Migration(migrations.Migration):
    dependencies=[('intake','0002_historical_work')]
    operations=[migrations.AddField(model_name='material',name='is_demo',field=models.BooleanField(default=False))]
