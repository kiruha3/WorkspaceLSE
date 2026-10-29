import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('documents', '0006_work_document_vault'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name='StorageRoot',
        fields=[
            ('year', models.PositiveSmallIntegerField(primary_key=True, serialize=False)),
            ('path', models.CharField(max_length=2000)),
            ('version', models.PositiveIntegerField(default=0)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('updated_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ],
        options={'constraints': [models.CheckConstraint(condition=models.Q(('year__gte', 1900), ('year__lte', 9999)), name='storage_root_year_range')]},
    )]
