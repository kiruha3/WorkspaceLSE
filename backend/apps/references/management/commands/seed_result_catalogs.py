from django.core.management.base import BaseCommand
from django.db import transaction
from apps.references.result_seeds import seed_result_catalogs


class Command(BaseCommand):
    help = "Добавить недостающие причины результата без изменения существующих значений и журнала"

    @transaction.atomic
    def handle(self, *args, **options):
        seed_result_catalogs()
