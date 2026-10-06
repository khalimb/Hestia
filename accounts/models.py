import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

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
