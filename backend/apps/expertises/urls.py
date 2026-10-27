from django.urls import path
from .api import ExpertiseRegisterView, ExpertiseListView, ExpertiseDetailView, NumberHintView, FilterOptionsView, ComplexGroupView

urlpatterns=[
    path("receipts/<uuid:pk>/expertises/",ExpertiseRegisterView.as_view()),
    path("expertises/",ExpertiseListView.as_view()),
    path("expertises/number-hint/",NumberHintView.as_view()),
    path("expertises/filter-options/",FilterOptionsView.as_view()),
    path("expertises/<uuid:pk>/",ExpertiseDetailView.as_view()),
    path("complex-groups/",ComplexGroupView.as_view()),
]
