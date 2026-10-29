from django.urls import path
from .api import ImportPreviewView,ImportListView,ImportDetailView,ImportRowsView,ImportSourceView,GoogleSourceView,GooglePreviewView
from .reconciliation_api import ReconciliationOptionsView,ReconciliationView,SelectionView,ApplicationView,ApplicationDetailView
from .update_api import UpdatesView
from .review_api import ReviewView
from .source_settings import GoogleSourceSettingsView

urlpatterns=[path("imports/",ImportListView.as_view()),path("imports/preview/",ImportPreviewView.as_view()),path("imports/google-source/",GoogleSourceView.as_view()),path("imports/google-source/settings/",GoogleSourceSettingsView.as_view()),path("imports/google-preview/",GooglePreviewView.as_view()),path("imports/<uuid:pk>/",ImportDetailView.as_view()),
    path("imports/<uuid:pk>/rows/",ImportRowsView.as_view()),path("imports/<uuid:pk>/source/",ImportSourceView.as_view()),
    path("imports/reconciliation-options/",ReconciliationOptionsView.as_view()),path("imports/<uuid:pk>/reconciliation/",ReconciliationView.as_view()),
    path("imports/<uuid:pk>/rows/<uuid:row_pk>/selection/",SelectionView.as_view()),path("imports/<uuid:pk>/apply/",ApplicationView.as_view()),
    path("imports/<uuid:pk>/updates/",UpdatesView.as_view()),path("imports/<uuid:pk>/review/",ReviewView.as_view()),path("imports/applications/<uuid:pk>/",ApplicationDetailView.as_view())]
