from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from .admin_localization import RussianAdminMixin


WORKPLACES = {
    'accounts.role': '/roles', 'accounts.rolepermission': '/roles',
    'personnel.employee': '/people', 'personnel.employeespecialty': '/people',
    'personnel.employeeorgassignment': '/people', 'personnel.employeerole': '/access',
    'intake.receipt': '/receipts/{pk}', 'intake.material': '/intake',
    'expertises.expertise': '/expertises/{pk}', 'documents.document': '/expertises',
    'documents.storageroot': '/settings/storage', 'correspondence.letter': '/letters/{pk}',
    'issuance.issuepackage': '/issue-packages/{pk}', 'imports.importbatch': '/imports/{pk}',
    'imports.journalsourcesettings': '/imports/source-settings',
    'reports.stateassignmentplan': '/report-plans?year={year}',
}


class ReadOnlyAdmin(RussianAdminMixin, admin.ModelAdmin):
    """Operational data is maintained by commands, never a raw admin save."""
    actions = None
    list_per_page = 50
    show_full_result_count = False
    list_select_related = True
    change_form_template = 'admin/ais_change_form.html'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return self.localize_columns(tuple('stored_file' if isinstance(field, models.FileField) else field.name
                     for field in (*self.model._meta.fields, *self.model._meta.many_to_many)))

    def get_fields(self, request, obj=None):
        return self.get_readonly_fields(request, obj)

    @admin.display(description='Файл')
    def stored_file(self, obj):
        field = next(f for f in obj._meta.fields if isinstance(f, models.FileField))
        value = getattr(obj, field.name)
        if not value:
            return '—'
        if obj._meta.label_lower == 'documents.fileversion':
            return format_html('<a href="/api/v1/file-versions/{}/download/">{}</a>', obj.pk, obj.original_name)
        return str(value)

    def get_list_display(self, request):
        names = {field.name for field in self.model._meta.fields}
        columns = [name for name in (
            'registration_number', 'full_name', 'name', 'title', 'source_name', 'original_name',
            'action', 'object_type', 'object_id', 'year', 'number', 'state', 'status',
            'direction', 'permission_code', 'scope', 'employee', 'role', 'expertise',
            'document', 'actor', 'is_active', 'created_at',
        ) if name in names]
        return self.localize_columns(tuple(columns[:5]) or ('id',))

    def get_search_fields(self, request):
        fields = []
        for field in self.model._meta.fields:
            if isinstance(field, (models.CharField, models.TextField)) and field.name != 'password':
                fields.append(field.name)
            elif field.is_relation:
                related = {f.name for f in field.related_model._meta.fields}
                for name in ('username', 'full_name', 'registration_number', 'code', 'title', 'name'):
                    if name in related:
                        fields.append(f'{field.name}__{name}')
                        break
        return tuple(fields)

    def get_list_filter(self, request):
        return self.localize_filters(tuple(f.name for f in self.model._meta.fields if f.choices or isinstance(f, models.BooleanField))[:4])

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        path = WORKPLACES.get(self.model._meta.label_lower)
        if obj is not None:
            if path:
                context['workplace_url'] = path.format(pk=obj.pk, year=getattr(obj, 'year', ''))
            elif hasattr(obj, 'expertise_id'):
                context['workplace_url'] = f'/expertises/{obj.expertise_id}'
        return super().render_change_form(request, context, add, change, form_url, obj)
