from django.urls import path
from .api import ExpertiseRegisterView, ComplexExpertiseRegisterView, ExpertiseListView, ExpertiseDetailView, NumberHintView, FilterOptionsView, ComplexGroupView, AssignmentCandidatesView, AssignView,HistoryActivationView
from .production_api import TransitionView,DeadlineView
from .result_api import ResultOptionsView,ResultView,ClosureView,ReopenView
from .historical_report_api import HistoricalReportView
from .case_api import CaseDetailsView
from .classification_api import ClassificationView
from .timing_api import TimingView
from .export_api import ExpertiseExportView
from .completeness_api import IncompleteExpertisesView

urlpatterns=[
    path("receipts/<uuid:pk>/expertises/",ExpertiseRegisterView.as_view()),
    path("receipts/<uuid:pk>/complex-expertises/",ComplexExpertiseRegisterView.as_view()),
    path("expertises/",ExpertiseListView.as_view()),
    path("expertises/incomplete/",IncompleteExpertisesView.as_view()),
    path("expertises/export.xlsx",ExpertiseExportView.as_view()),
    path("expertises/number-hint/",NumberHintView.as_view()),
    path("expertises/filter-options/",FilterOptionsView.as_view()),
    path("expertises/<uuid:pk>/",ExpertiseDetailView.as_view()),
    path("expertises/<uuid:pk>/activate-history/",HistoryActivationView.as_view()),
    path("expertises/<uuid:pk>/history-report/",HistoricalReportView.as_view()),
    path("expertises/<uuid:pk>/case-details/",CaseDetailsView.as_view()),
    path("expertises/<uuid:pk>/classification/",ClassificationView.as_view()),
    path("expertises/<uuid:pk>/timing/",TimingView.as_view()),
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
    path("expertises/<uuid:pk>/reopen/",ReopenView.as_view()),
    path("complex-groups/",ComplexGroupView.as_view()),
]
