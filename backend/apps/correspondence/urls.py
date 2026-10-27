from django.urls import path
from .api import LetterListView, LetterDetailView, LetterOptionsView, WorkOptionsView, MaterialOptionsView, DraftView, AttachmentView, ExpertiseLettersView
from .command_api import LetterCommandView

urlpatterns = [
    path("letters/", LetterListView.as_view()),
    path("letters/options/", LetterOptionsView.as_view()),
    path("letters/work-options/", WorkOptionsView.as_view()),
    path("letters/material-options/", MaterialOptionsView.as_view()),
    path("letters/<uuid:pk>/", LetterDetailView.as_view()),
    path("letters/<uuid:pk>/draft/", DraftView.as_view()),
    path("letters/<uuid:pk>/attachments/", AttachmentView.as_view()),
    path("letters/<uuid:pk>/register/", LetterCommandView.as_view(kind="register")),
    path("letters/<uuid:pk>/mark-sent/", LetterCommandView.as_view(kind="send")),
    path("letters/<uuid:pk>/mark-received/", LetterCommandView.as_view(kind="receive")),
    path("letters/<uuid:pk>/mark-delivered/", LetterCommandView.as_view(kind="deliver")),
    path("letters/<uuid:pk>/assign/", LetterCommandView.as_view(kind="assign")),
    path("letters/<uuid:pk>/control/", LetterCommandView.as_view(kind="control")),
    path("letters/<uuid:pk>/control/deadline/", LetterCommandView.as_view(kind="deadline")),
    path("letters/<uuid:pk>/control/close/", LetterCommandView.as_view(kind="close")),
    path("letters/<uuid:pk>/control/reopen/", LetterCommandView.as_view(kind="reopen")),
    path("expertises/<uuid:pk>/letters/", ExpertiseLettersView.as_view()),
]
