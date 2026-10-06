from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('me/', views.ProfileView.as_view(), name='profile'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    # Admin: members and invites
    path('members/', views.MemberListCreateView.as_view(), name='member-list'),
    path('members/<uuid:pk>/', views.MemberDetailView.as_view(), name='member-detail'),
    path('members/<uuid:pk>/password/', views.MemberPasswordView.as_view(), name='member-password'),
    path('invites/', views.InviteListCreateView.as_view(), name='invite-list'),
    path('invites/<uuid:pk>/', views.InviteDetailView.as_view(), name='invite-detail'),
]
