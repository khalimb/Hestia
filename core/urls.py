from django.urls import path
from . import views

urlpatterns = [
    path('fx/manual/', views.ManualFxRateListCreateView.as_view(), name='fx-manual-list'),
    path('fx/manual/<str:currency>/', views.ManualFxRateDetailView.as_view(), name='fx-manual-detail'),
]
