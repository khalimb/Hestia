from django.urls import path
from . import views

urlpatterns = [
    path(
        'occurrences/<uuid:occurrence_id>/payments/',
        views.OccurrencePaymentListCreateView.as_view(),
        name='occurrence-payments',
    ),
    path(
        'payments/<uuid:pk>/',
        views.PaymentDetailView.as_view(),
        name='payment-detail',
    ),
]
