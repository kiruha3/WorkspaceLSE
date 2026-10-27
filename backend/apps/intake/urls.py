from django.urls import path
from .api import ReceiptListView,ReceiptDetailView,ReceiptAcceptView,ReceiptAmendView

urlpatterns=[path("receipts/",ReceiptListView.as_view()),path("receipts/<uuid:pk>/",ReceiptDetailView.as_view()),path("receipts/<uuid:pk>/register/",ReceiptAcceptView.as_view()),path("receipts/<uuid:pk>/amend/",ReceiptAmendView.as_view())]
