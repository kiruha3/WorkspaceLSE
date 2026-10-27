from django.urls import path
from .api import ExpertiseRegisterView, ExpertiseListView, ExpertiseDetailView, NumberHintView, FilterOptionsView, ComplexGroupView, AssignmentCandidatesView, AssignView
from .production_api import TransitionView

urlpatterns=[
    path("receipts/<uuid:pk>/expertises/",ExpertiseRegisterView.as_view()),
    path("expertises/",ExpertiseListView.as_view()),
    path("expertises/number-hint/",NumberHintView.as_view()),
    path("expertises/filter-options/",FilterOptionsView.as_view()),
    path("expertises/<uuid:pk>/",ExpertiseDetailView.as_view()),
    path("expertises/<uuid:pk>/assignment-candidates/",AssignmentCandidatesView.as_view()),
    path("expertises/<uuid:pk>/assignments/",AssignView.as_view()),
    path("expertises/<uuid:pk>/reassign/",AssignView.as_view(reassign=True)),
    path("expertises/<uuid:pk>/suspend/",TransitionView.as_view(kind="suspend")),
    path("expertises/<uuid:pk>/resume/",TransitionView.as_view(kind="resume")),
    path("complex-groups/",ComplexGroupView.as_view()),
]
