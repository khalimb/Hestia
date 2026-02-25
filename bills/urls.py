from django.urls import path
from . import views

urlpatterns = [
    path(
        'expenses/<uuid:expense_id>/bills/',
        views.ExpenseBillListCreateView.as_view(),
        name='expense-bills',
    ),
    path(
        'bills/<uuid:pk>/',
        views.BillDetailView.as_view(),
        name='bill-detail',
    ),
]
