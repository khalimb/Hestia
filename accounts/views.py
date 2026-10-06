from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from activity.services import record_activity
from core.permissions import IsHouseholdAdmin

from .models import Invite
from .serializers import (
    RegisterSerializer, UserSerializer, UserSummarySerializer, MemberSerializer,
    MemberCreateSerializer, SetPasswordSerializer, InviteSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """GET: whether registration is open (only before the first account) and
    whether a given ?invite= token is valid. POST: register (invite required
    unless bootstrapping)."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        bootstrap = not User.objects.exists()
        token = request.query_params.get('invite', '').strip()
        invite = Invite.objects.filter(token=token).first() if token else None
        return Response({
            'open': bootstrap,
            'invite_required': not bootstrap,
            'invite_valid': bool(invite and invite.is_valid),
            'invite_email': invite.email if invite and invite.is_valid else '',
        })

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        record_activity('create', 'member', user.pk, user.display_name,
                        {'email': {'from': None, 'to': user.email},
                         'via': {'from': None, 'to': 'invite' if serializer._invite else 'first account'}})
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class LogoutView(generics.GenericAPIView):
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class UserListView(generics.ListAPIView):
    """All active family members, for the 'responsible' / 'paid by' selects."""
    serializer_class = UserSummarySerializer
    pagination_class = None
    queryset = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'email')


# --- admin: members -------------------------------------------------------------------

class MemberListCreateView(generics.ListCreateAPIView):
    """GET: every member incl. deactivated (any signed-in user may look).
    POST (admin): create an account with a temporary password."""
    serializer_class = MemberSerializer
    pagination_class = None
    queryset = User.objects.order_by('-is_active', 'first_name', 'last_name', 'email')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsHouseholdAdmin()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = MemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        record_activity('create', 'member', user.pk, user.display_name,
                        {'email': {'from': None, 'to': user.email},
                         'admin': {'from': None, 'to': user.is_staff}})
        return Response(MemberSerializer(user).data, status=status.HTTP_201_CREATED)


class MemberDetailView(generics.RetrieveUpdateAPIView):
    """PATCH (admin): is_active and/or is_staff, with guards."""
    serializer_class = MemberSerializer
    permission_classes = [IsHouseholdAdmin]
    queryset = User.objects.all()

    def update(self, request, *args, **kwargs):
        member = self.get_object()
        serializer = self.get_serializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        wants = serializer.validated_data
        if member == request.user and wants.get('is_active') is False:
            return Response({'detail': 'You cannot deactivate yourself.'}, status=400)
        if member == request.user and wants.get('is_staff') is False:
            return Response({'detail': 'You cannot remove your own admin role.'}, status=400)
        if (wants.get('is_staff') is False or wants.get('is_active') is False) and member.is_staff \
                and member.is_active and User.objects.filter(is_staff=True, is_active=True).count() == 1:
            return Response({'detail': 'There must always be at least one active admin.'}, status=400)
        before = {'active': member.is_active, 'admin': member.is_staff}
        serializer.save()
        after = {'active': member.is_active, 'admin': member.is_staff}
        changes = {k: {'from': before[k], 'to': after[k]} for k in before if before[k] != after[k]}
        if changes:
            record_activity('update', 'member', member.pk, member.display_name, changes)
        return Response(serializer.data)


class MemberPasswordView(APIView):
    """POST (admin): set a temporary password for a member."""
    permission_classes = [IsHouseholdAdmin]

    def post(self, request, pk):
        member = generics.get_object_or_404(User, pk=pk)
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member.set_password(serializer.validated_data['password'])
        member.save(update_fields=['password'])
        record_activity('update', 'member', member.pk, member.display_name,
                        {'password': {'from': None, 'to': 'reset by admin'}})
        return Response({'detail': f'Password updated for {member.display_name}.'})


# --- admin: invites -------------------------------------------------------------------

class InviteListCreateView(generics.ListCreateAPIView):
    """GET: invites, newest first. POST: mint one; the link is returned ONCE."""
    serializer_class = InviteSerializer
    permission_classes = [IsHouseholdAdmin]
    pagination_class = None
    queryset = Invite.objects.select_related('created_by', 'used_by')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite = serializer.save(created_by=request.user)
        data = InviteSerializer(invite).data
        data['link'] = request.build_absolute_uri(f'/register?invite={invite.token}')
        return Response(data, status=status.HTTP_201_CREATED)


class InviteDetailView(generics.DestroyAPIView):
    """DELETE: revoke an unused invite."""
    serializer_class = InviteSerializer
    permission_classes = [IsHouseholdAdmin]
    queryset = Invite.objects.all()
