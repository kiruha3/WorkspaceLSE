from copy import copy
import json

from django.contrib import admin
from django.contrib.admin.utils import display_for_field
from django.db import models
from django.core.exceptions import FieldDoesNotExist
from django.urls import reverse, NoReverseMatch
from django.utils.html import format_html, format_html_join

from .admin_labels import FIELD_LABELS, SINGULAR_NAMES, field_label, choice_label


def translated_field(field):
    result = copy(field)
    result.verbose_name = field_label(field)
    if field.choices:
        result.choices = [(code, choice_label(field, code, label)) for code, label in field.flatchoices]
    return result


def record_label(obj):
    for name in ('registration_number', 'full_name', 'username', 'original_name', 'title', 'name', 'subject', 'source_name'):
        value = getattr(obj, name, None)
        if value:
            code = getattr(obj, 'code', None)
            return f'{code} — {value}' if name == 'name' and code else str(value)
    return f'{SINGULAR_NAMES.get(type(obj).__name__, obj._meta.verbose_name)} · {obj.pk}'


class TranslatedFieldFilter(admin.FieldListFilter):
    def __new__(cls, field, request, params, model, model_admin, field_path):
        return admin.FieldListFilter.create(translated_field(field), request, params, model, model_admin, field_path)


class AdminOptions:
    def __init__(self, original):
        from config.admin import APP_NAMES, MODEL_NAMES
        self._original = original
        self.verbose_name = SINGULAR_NAMES.get(original.object_name, original.verbose_name)
        self.verbose_name_plural = MODEL_NAMES.get(original.object_name, original.verbose_name_plural)
        self.app_config = copy(original.app_config)
        self.app_config.verbose_name = APP_NAMES.get(original.app_label, original.app_config.verbose_name)

    def __getattr__(self, name):
        return getattr(self._original, name)


class RussianAdminMixin:
    """Translate admin presentation without mutating shared model metadata."""

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self._admin_fields = {}
        for field in (*model._meta.fields, *model._meta.many_to_many):
            name = f'ru_{field.name}'
            self._admin_fields[name] = field

            def render(obj, field=field):
                value = getattr(obj, field.name)
                if field.many_to_many:
                    return format_html_join(', ', '{}', ((record_label(item),) for item in value.all())) or '—'
                if field.is_relation and value is not None:
                    try:
                        url = reverse(f'{self.admin_site.name}:{value._meta.app_label}_{value._meta.model_name}_change', args=[value.pk])
                    except NoReverseMatch:
                        return record_label(value)
                    return format_html('<a href="{}">{}</a>', url, record_label(value))
                if isinstance(field, models.JSONField):
                    return format_html('<pre>{}</pre>', json.dumps(value, ensure_ascii=False, indent=2))
                return display_for_field(value, translated_field(field), self.get_empty_value_display())

            render.short_description = field_label(field)
            render.admin_order_field = field.name
            setattr(self, name, render)

    def localize_columns(self, names):
        return tuple(f'ru_{name}' if f'ru_{name}' in self._admin_fields else name for name in names)

    def get_list_display(self, request):
        return self.localize_columns(super().get_list_display(request))

    def get_readonly_fields(self, request, obj=None):
        return self.localize_columns(super().get_readonly_fields(request, obj))

    def get_fieldsets(self, request, obj=None):
        readonly = set(self.get_readonly_fields(request, obj))
        def translate(value):
            if isinstance(value, (tuple, list)):
                return tuple(translate(item) for item in value)
            localized = f'ru_{value}'
            return localized if localized in readonly else value
        return [(title, {**options, 'fields': translate(options['fields'])})
                for title, options in super().get_fieldsets(request, obj)]

    def get_form(self, request, obj=None, change=False, **kwargs):
        # Display methods replace read-only fields; still exclude their real fields from editing.
        excluded = list(kwargs.get('exclude') or self.get_exclude(request, obj) or ())
        readonly = self.get_readonly_fields(request, obj)
        excluded += list(readonly)
        excluded += [self._admin_fields[name].name for name in readonly if name in self._admin_fields]
        kwargs['exclude'] = excluded
        form = super().get_form(request, obj, change=change, **kwargs)
        for name, field in form.base_fields.items():
            if name in FIELD_LABELS:
                field.label = FIELD_LABELS[name]
            try:
                source = self.model._meta.get_field(name)
            except FieldDoesNotExist:
                continue
            if source.choices:
                field.choices = [('', '---------'), *translated_field(source).choices]
        return form

    def localize_filters(self, filters):
        return tuple((item, TranslatedFieldFilter) if isinstance(item, str) else item for item in filters)

    def get_list_filter(self, request):
        return self.localize_filters(super().get_list_filter(request))

    def localized_options(self):
        return AdminOptions(self.model._meta)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        if hasattr(response, 'context_data') and response.context_data:
            opts = self.localized_options()
            response.context_data['opts'] = opts
            response.context_data['cl'].opts = opts
            response.context_data['cl'].title = response.context_data['title'] = str(opts.verbose_name_plural)
        return response

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        response = super().render_change_form(request, context, add, change, form_url, obj)
        opts = self.localized_options()
        response.context_data['opts'] = opts
        response.context_data['title'] = f'{"Добавить" if add else "Карточка"}: {opts.verbose_name}'
        if obj is not None:
            response.context_data['subtitle'] = record_label(obj)
        return response

    def history_view(self, request, object_id, extra_context=None):
        response = super().history_view(request, object_id, extra_context)
        if hasattr(response, 'context_data') and response.context_data:
            response.context_data['opts'] = self.localized_options()
            response.context_data['title'] = f'История: {self.localized_options().verbose_name}'
        return response
