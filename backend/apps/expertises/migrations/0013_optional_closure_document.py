import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('expertises', '0012_optional_construction_evidence')]
    operations = [migrations.AlterField(
        model_name='workclosure', name='document',
        field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                related_name='work_closures', to='documents.document'),
    )]
