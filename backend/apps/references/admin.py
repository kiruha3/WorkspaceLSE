from django import forms
from django.contrib import admin
from rest_framework.exceptions import APIException
from apps.accounts.policies import can
from apps.accounts.services import check_version
from .api import (CATALOGS, ReferenceCreate, ReferenceUpdate, LetterJournalCreate,
                  ClosureReasonCreate, AuthorityTypeCreate, AuthorityTypeUpdate,
                  DelayReasonCreate, DelayReasonUpdate)
from .commands import create_reference, update_reference
from .models import LetterJournal, ControlClosureReason, AuthorityType, DelayReason
from apps.common.admin_localization import RussianAdminMixin


class ReferenceForm(forms.ModelForm):
    expected_version = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        fields = '__all__'
        labels = {'code': 'Код', 'name': 'Название', 'is_active': 'Активно',
                  'direction': 'Направление', 'department': 'Отдел', 'rule': 'Правило',
                  'report_group': 'Группа отчёта'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance._state.adding:
            self.fields['expected_version'].initial = self.instance.version

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        model = type(self.instance)
        creating = self.instance._state.adding
        if creating:
            serializer_class = {LetterJournal: LetterJournalCreate, ControlClosureReason: ClosureReasonCreate,
                                AuthorityType: AuthorityTypeCreate, DelayReason: DelayReasonCreate}.get(model, ReferenceCreate)
            values = {name: cleaned.get(name) for name in ('code', 'name')}
            if model is LetterJournal:
                values.update(direction=cleaned.get('direction'), department_id=getattr(cleaned.get('department'), 'pk', None))
            if model is ControlClosureReason:
                values['rule'] = cleaned.get('rule')
        else:
            self.locked_item = model.objects.select_for_update().get(pk=self.instance.pk)
            serializer_class = {AuthorityType: AuthorityTypeUpdate, DelayReason: DelayReasonUpdate}.get(model, ReferenceUpdate)
            values = {name: cleaned.get(name) for name in ('name', 'is_active', 'expected_version')}
        if model in (AuthorityType, DelayReason):
            values['report_group'] = cleaned.get('report_group') or None
        serializer = serializer_class(data=values)
        try:
            serializer.is_valid(raise_exception=True)
            if not creating:
                check_version(self.locked_item, serializer.validated_data['expected_version'])
            department = serializer.validated_data.get('department')
            if department is not None and not department.is_active:
                raise forms.ValidationError('Новый журнал нельзя связать с неактивным отделом.')
        except APIException as error:
            raise forms.ValidationError(str(error.detail)) from error
        self.command_values = serializer.validated_data
        return cleaned


class ReferenceAdmin(RussianAdminMixin, admin.ModelAdmin):
    form = ReferenceForm
    actions = None
    list_display = ('code', 'name', 'is_active', 'version')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')
    list_per_page = 50
    show_full_result_count = False

    def has_add_permission(self, request):
        return can(request.user, 'references.manage')

    def has_change_permission(self, request, obj=None):
        return can(request.user, 'references.manage')

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return self.localize_columns(('version', 'is_active'))
        immutable = tuple(name for name in ('direction', 'department', 'rule')
                          if any(f.name == name for f in self.model._meta.fields))
        return self.localize_columns(('code', 'version', *immutable))

    def save_model(self, request, obj, form, change):
        catalog = next(code for code, model in CATALOGS.items() if model is self.model)
        if change:
            item = update_reference(actor=request.user, catalog=catalog, item=form.locked_item,
                                    values=form.command_values, key=None, payload={})
        else:
            item = create_reference(actor=request.user, catalog=catalog, model=self.model,
                                    values=form.command_values, key=None, payload={})
        for field in obj._meta.concrete_fields:
            setattr(obj, field.attname, getattr(item, field.attname))
        obj._state.adding = False
        obj._state.db = item._state.db


for model in CATALOGS.values():
    admin.site.register(model, ReferenceAdmin)
