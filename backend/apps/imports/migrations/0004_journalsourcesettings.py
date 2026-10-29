from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies=[('imports','0003_journal_application'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(
        name='JournalSourceSettings',
        fields=[
            ('id',models.PositiveSmallIntegerField(default=1,editable=False,primary_key=True,serialize=False)),
            ('spreadsheet_id',models.CharField(max_length=200)),
            ('gid',models.CharField(max_length=10)),
            ('sheet_name',models.CharField(max_length=255)),
            ('version',models.PositiveIntegerField(default=0)),
            ('updated_at',models.DateTimeField(auto_now=True)),
            ('updated_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
        ],
        options={'constraints':[models.CheckConstraint(condition=models.Q(id=1),name='single_journal_source_settings')]},
    )]
