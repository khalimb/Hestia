from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'subjects', views.SubjectViewSet)
router.register(r'expense-types', views.ExpenseTypeViewSet)
router.register(r'expenses', views.ExpenseViewSet)
router.register(r'occurrences', views.OccurrenceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
