from django.urls import path
from .api import MaterialPackagesView, PackageListView, PackageDetailView, PackageReadinessView, PackageDraftView, IssueOptionsView, DocumentOptionsView

urlpatterns = [
    path("materials/<uuid:pk>/issue-packages/", MaterialPackagesView.as_view()),
    path("issue-packages/", PackageListView.as_view()),
    path("issue-packages/options/", IssueOptionsView.as_view()),
    path("issue-packages/<uuid:pk>/", PackageDetailView.as_view()),
    path("issue-packages/<uuid:pk>/readiness/", PackageReadinessView.as_view()),
    path("issue-packages/<uuid:pk>/draft/", PackageDraftView.as_view()),
    path("issue-packages/<uuid:pk>/document-options/", DocumentOptionsView.as_view()),
]
