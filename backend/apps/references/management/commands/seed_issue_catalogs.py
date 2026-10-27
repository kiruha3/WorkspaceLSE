from django.core.management.base import BaseCommand
from django.db import transaction
from apps.references.models import IssueMethod


class Command(BaseCommand):
    help = "Заполняет ручные способы выдачи, не меняя существующие названия и активность."

    @transaction.atomic
    def handle(self, *args, **options):
        for code, name in [("in_person", "Нарочно"), ("post", "Почтовое отправление"), ("courier", "Курьером"), ("other", "Иной способ")]:
            IssueMethod.objects.get_or_create(code=code, defaults={"name": name})
        self.stdout.write("Способы выдачи подготовлены без изменения существующих настроек.")
