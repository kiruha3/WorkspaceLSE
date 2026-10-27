from django.urls import path
from .api import LetterListView, LetterDetailView, LetterOptionsView, WorkOptionsView, MaterialOptionsView, DraftView, AttachmentView, ExpertiseLettersView

urlpatterns = [
    path("letters/", LetterListView.as_view()),
    path("letters/options/", LetterOptionsView.as_view()),
    path("letters/work-options/", WorkOptionsView.as_view()),
    path("letters/material-options/", MaterialOptionsView.as_view()),
    path("letters/<uuid:pk>/", LetterDetailView.as_view()),
    path("letters/<uuid:pk>/draft/", DraftView.as_view()),
    path("letters/<uuid:pk>/attachments/", AttachmentView.as_view()),
    path("expertises/<uuid:pk>/letters/", ExpertiseLettersView.as_view()),
]
