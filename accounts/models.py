import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name']

    def __str__(self):
        return self.email

    @property
    def display_name(self):
        """Human label for selects and read-only names: full name, else email."""
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.email


def generate_invite_token():
    return secrets.token_urlsafe(24)


def default_invite_expiry():
    return timezone.now() + timedelta(days=7)


class Invite(models.Model):
    """Single-use registration invite created by an admin. Registration is
    closed otherwise (except for the very first account on an empty
    deployment)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=64, unique=True, default=generate_invite_token)
    # Optional: who this is for; shown on the register page, not enforced.
    email = models.EmailField(blank=True, default='')
    note = models.CharField(max_length=100, blank=True, default='')
    make_admin = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invites_sent',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_invite_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invite_used',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invite {self.note or self.email or self.token[:6]}"

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()
