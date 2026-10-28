"""Optional-key commands preserve old catalogue clients and audited versions."""
from django.db import transaction, IntegrityError
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once, CommandConflict
from apps.accounts.policies import require
from apps.accounts.services import audit, check_version


def once(actor, catalog, kind, key, payload, operation):
    if key is None:
        return operation()
    return execute_once(actor=actor, action=f'reference.{catalog}.{kind}', key=key,
                        payload=payload, operation=operation)


def create_reference(*, actor, catalog, model, values, key, payload):
    from .api import reference_data
    try:
        with transaction.atomic():
            require(actor, 'references.manage')
            def operation():
                require(actor, 'references.manage')
                department = values.get('department')
                if department is not None:
                    department = type(department).objects.select_for_update().get(pk=department.pk)
                    if not department.is_active:
                        raise ValidationError({'department_id': 'Новый журнал нельзя связать с неактивным отделом.'})
                if model.objects.filter(code=values['code']).exists():
                    raise ValidationError({'code': 'Этот код уже существует.'})
                item = model.objects.create(**values)
                audit(actor, 'reference.create', item, reference_data(item))
                return {'id': str(item.pk)}
            result = once(actor, catalog, 'create', key, payload, operation)
            return model.objects.get(pk=result['id'])
    except IntegrityError as error:
        if getattr(error.__cause__, 'sqlstate', None) == '23505':
            raise CommandConflict('Код уже занят другой командой. Обновите справочник.') from error
        raise


@transaction.atomic
def update_reference(*, actor, catalog, item, values, key, payload):
    from .api import reference_data
    require(actor, 'references.manage')
    def operation():
        require(actor, 'references.manage')
        data = values.copy()
        check_version(item, data.pop('expected_version'))
        before = reference_data(item)
        for name, value in data.items():
            setattr(item, name, value)
        item.version += 1
        item.save()
        audit(actor, 'reference.update', item, {'before': before, 'after': reference_data(item)})
        return {'id': str(item.pk)}
    once(actor, catalog, 'update', key, {'id': str(item.pk), 'data': payload}, operation)
    item.refresh_from_db()
    return item
