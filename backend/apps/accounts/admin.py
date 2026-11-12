from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError
from apps.accounts.services import audit
from .models import User
from apps.common.admin_localization import RussianAdminMixin


ACCOUNT_FIELDS = ('username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser')


class ServiceAdminAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser:
            raise ValidationError('Для этой учётной записи не включён служебный доступ к Django Admin.',
                                  code='service_access_required')


admin.site.login_form = ServiceAdminAuthenticationForm


@admin.register(User)
class AccountAdmin(RussianAdminMixin, UserAdmin):
    actions = None
    list_display = ('username', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Пользователь', {'fields': ('first_name', 'last_name', 'email')}),
        ('Доступ к служебной панели', {'fields': ('is_active', 'is_staff', 'is_superuser'),
            'description': 'Роли АИС и связь с сотрудником настраиваются в разделе «Учётные записи» рабочего интерфейса.'}),
        ('Даты', {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ('last_login', 'date_joined')

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        before = User.objects.filter(pk=obj.pk).values(*ACCOUNT_FIELDS).first() if change else None
        super().save_model(request, obj, form, change)
        after = {name: getattr(obj, name) for name in ACCOUNT_FIELDS}
        audit(request.user, 'admin.user.update' if change else 'admin.user.create', obj,
              {'before': before, 'after': after})

    def log_change(self, request, obj, message):
        super().log_change(request, obj, message)
        if request.path.endswith('/password/'):
            audit(request.user, 'admin.user.password', obj, {'password_changed': True})
