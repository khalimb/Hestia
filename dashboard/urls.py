from django.urls import path
from . import views

urlpatterns = [
    path('summary/', views.DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('upcoming/', views.DashboardUpcomingView.as_view(), name='dashboard-upcoming'),
    path('overdue/', views.DashboardOverdueView.as_view(), name='dashboard-overdue'),
]
