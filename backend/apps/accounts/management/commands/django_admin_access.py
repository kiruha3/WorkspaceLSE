from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.accounts.services import audit


class Command(BaseCommand):
    help = 'Явно включить/отозвать служебный Django Admin у существующей учётной записи, сохранив пароль и роли АИС.'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--revoke', action='store_true', help='Отозвать доступ к служебной панели')

    @transaction.atomic
    def handle(self, *args, **options):
        user = get_user_model().objects.select_for_update().filter(username=options['username']).first()
        if user is None:
            raise CommandError('Учётная запись не найдена. Сначала создайте пользователя.')
        revoke = options['revoke']
        if not revoke and not user.is_active:
            raise CommandError('Учётная запись неактивна. Автоматическое включение не выполняется.')
        before = {'is_staff': user.is_staff, 'is_superuser': user.is_superuser}
        after = {'is_staff': not revoke, 'is_superuser': not revoke}
        if before != after:
            user.is_staff = user.is_superuser = not revoke
            user.save(update_fields=['is_staff', 'is_superuser'])
            # No web actor exists for a local maintenance command.
            audit(None, 'admin.access.revoke' if revoke else 'admin.access.grant', user,
                  {'before': before, 'after': after}, reason='Локальная команда django_admin_access')
        self.stdout.write('Доступ к Django Admin отозван.' if revoke else 'Доступ к Django Admin включён. Пароль и роли АИС сохранены.')
