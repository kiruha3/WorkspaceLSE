from django.urls import path
from .api import ImportPreviewView,ImportListView,ImportDetailView,ImportRowsView,ImportSourceView

urlpatterns=[path("imports/",ImportListView.as_view()),path("imports/preview/",ImportPreviewView.as_view()),path("imports/<uuid:pk>/",ImportDetailView.as_view()),
    path("imports/<uuid:pk>/rows/",ImportRowsView.as_view()),path("imports/<uuid:pk>/source/",ImportSourceView.as_view())]
