"""Read-only options for document selection, using the existing document policy."""
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from apps.accounts.policies import AccessScope,permission_scopes
from .models import Document
from .policies import can_document


class SearchInput(serializers.Serializer):
    search=serializers.CharField(max_length=500,allow_blank=True,required=False,default='')
    kinds=serializers.ListField(child=serializers.ChoiceField(choices=Document._meta.get_field('kind').choices),required=False,default=list)


def document_options(user,params):
    scopes=permission_scopes(user)
    if not scopes.get('documents.view',AccessScope()).rules:
        raise PermissionDenied('Нет права просматривать документы.')
    form=SearchInput(data={'search':params.get('search',''),'kinds':[kind for kind in params.get('kind','').split(',') if kind]})
    form.is_valid(raise_exception=True)
    search=form.validated_data['search'].casefold();kinds=form.validated_data['kinds']
    query=Document.objects.prefetch_related('versions').order_by('title','id')
    if kinds:query=query.filter(kind__in=kinds)
    # Authorization precedes returning metadata/counts, including title probes.
    return [doc for doc in query if can_document(user,'documents.view',doc,scopes)
            and (not search or search in doc.title.casefold()
                 or any(search in version.original_name.casefold() for version in doc.versions.all()))]
