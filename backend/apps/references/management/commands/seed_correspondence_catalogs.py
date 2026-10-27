from django.core.management.base import BaseCommand
from django.db import transaction
from apps.references.correspondence_seeds import seed_correspondence_catalogs


class Command(BaseCommand):
    help = "Создать отсутствующие виды писем, каналы и основания контроля, сохранив настройки. Без журналов и писем."

    @transaction.atomic
    def handle(self, *args, **options):
        seed_correspondence_catalogs()
