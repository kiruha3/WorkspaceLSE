from django.urls import path
from .api import DocumentListView,DocumentDetailView,DocumentVersionsView,FileVersionView

urlpatterns=[
    path("documents/",DocumentListView.as_view()),
    path("documents/<uuid:pk>/",DocumentDetailView.as_view()),
    path("documents/<uuid:pk>/versions/",DocumentVersionsView.as_view()),
    path("file-versions/<uuid:pk>/<str:mode>/",FileVersionView.as_view()),
]
