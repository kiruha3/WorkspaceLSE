from django.urls import path
from .api import ExpertiseRegisterView, ExpertiseListView, ExpertiseDetailView, NumberHintView, FilterOptionsView, ComplexGroupView, AssignmentCandidatesView, AssignView
from .production_api import TransitionView,DeadlineView
from .result_api import ResultOptionsView,ResultView,ClosureView

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
    path("expertises/<uuid:pk>/deadline-events/",DeadlineView.as_view()),
    path("expertises/<uuid:pk>/result-options/",ResultOptionsView.as_view()),
    path("expertises/<uuid:pk>/result/",ResultView.as_view()),
    path("expertises/<uuid:pk>/complete/",ClosureView.as_view()),
    path("expertises/<uuid:pk>/return-without-execution/",ClosureView.as_view(kind="return")),
    path("expertises/<uuid:pk>/correct/",ClosureView.as_view(kind="correct")),
    path("complex-groups/",ComplexGroupView.as_view()),
]
