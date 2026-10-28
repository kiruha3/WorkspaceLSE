from django.urls import path
from .api import DocumentListView,DocumentDetailView,DocumentVersionsView,FileVersionView
from .work_api import WorkDocumentsView,WorkDocumentDetachView,WorkDocumentOptionsView

urlpatterns=[
    path('expertises/<uuid:pk>/documents/',WorkDocumentsView.as_view()),
    path('expertises/<uuid:pk>/documents/options/',WorkDocumentOptionsView.as_view()),
    path('expertises/<uuid:pk>/documents/<uuid:link_id>/detach/',WorkDocumentDetachView.as_view()),
    path("documents/",DocumentListView.as_view()),
    path("documents/<uuid:pk>/",DocumentDetailView.as_view()),
    path("documents/<uuid:pk>/versions/",DocumentVersionsView.as_view()),
    path("file-versions/<uuid:pk>/<str:mode>/",FileVersionView.as_view()),
]
