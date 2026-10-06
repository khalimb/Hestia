import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Invite

User = get_user_model()


def unique_username(base):
    """Derive a username from an email's local part, de-duplicated."""
    stem = re.sub(r'[^a-z0-9_.-]', '', base.split('@')[0].lower()) or 'member'
    candidate, n = stem, 2
    while User.objects.filter(username=candidate).exists():
        candidate = f'{stem}{n}'
        n += 1
    return candidate


class RegisterSerializer(serializers.ModelSerializer):
    """Self-registration. Requires a valid invite token unless the deployment
    has no users yet (first-run bootstrap, which also makes that user admin)."""
    password = serializers.CharField(write_only=True, min_length=8)
    invite = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'password', 'invite']

    def validate(self, attrs):
        token = (attrs.pop('invite', '') or '').strip()
        self._bootstrap = not User.objects.exists()
        self._invite = None
        if self._bootstrap:
            return attrs
        if not token:
            raise serializers.ValidationError(
                {'invite': 'Registration is by invitation. Ask a household admin for an invite link.'})
        invite = Invite.objects.filter(token=token).first()
        if invite is None or not invite.is_valid:
            raise serializers.ValidationError({'invite': 'This invite link is invalid, used, or expired.'})
        self._invite = invite
        return attrs

    def create(self, validated_data):
        from django.utils import timezone
        user = User.objects.create_user(**validated_data)
        if self._bootstrap or (self._invite and self._invite.make_admin):
            user.is_staff = True
            user.save(update_fields=['is_staff'])
        if self._invite:
            self._invite.used_at = timezone.now()
            self._invite.used_by = user
            self._invite.save(update_fields=['used_at', 'used_by'])
        return user


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'display_name',
                  'is_staff', 'is_active', 'date_joined']
        read_only_fields = ['id', 'email', 'display_name', 'is_staff', 'is_active', 'date_joined']


class UserSummarySerializer(serializers.ModelSerializer):
    """Minimal, read-only view of a family member for 'responsible' selects."""
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'display_name']
        read_only_fields = fields


# --- admin: member management ----------------------------------------------------------

class MemberSerializer(serializers.ModelSerializer):
    """Admin view of a member. is_active / is_staff are the editable fields;
    the guards (not yourself, not the last admin) live in the view."""
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'display_name',
                  'is_staff', 'is_active', 'date_joined', 'last_login']
        read_only_fields = ['id', 'email', 'username', 'first_name', 'last_name',
                            'display_name', 'date_joined', 'last_login']


class MemberCreateSerializer(serializers.Serializer):
    """Admin creates an account directly with a temporary password."""
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    username = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    password = serializers.CharField(write_only=True, min_length=8)
    is_staff = serializers.BooleanField(required=False, default=False)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A member with this email already exists.')
        return value

    def validate_username(self, value):
        value = value.strip()
        if value and User.objects.filter(username=value).exists():
            raise serializers.ValidationError('This username is taken.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        username = validated_data.pop('username') or unique_username(validated_data['email'])
        is_staff = validated_data.pop('is_staff')
        user = User.objects.create_user(username=username, **validated_data)
        if is_staff:
            user.is_staff = True
            user.save(update_fields=['is_staff'])
        return user


class SetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_password(self, value):
        validate_password(value)
        return value


class InviteSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.display_name', read_only=True)
    used_by_name = serializers.CharField(source='used_by.display_name', read_only=True, default=None)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invite
        fields = ['id', 'email', 'note', 'make_admin', 'created_by_name', 'created_at',
                  'expires_at', 'used_at', 'used_by_name', 'is_valid']
        read_only_fields = ['id', 'created_by_name', 'created_at', 'expires_at', 'used_at',
                            'used_by_name', 'is_valid']
