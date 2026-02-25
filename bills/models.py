import uuid
from django.conf import settings
from django.db import models


class Bill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(
        'expenses.Expense', on_delete=models.CASCADE, related_name='bills',
    )
    occurrence = models.ForeignKey(
        'expenses.Occurrence', on_delete=models.CASCADE,
        null=True, blank=True, related_name='bills',
    )
    file = models.FileField(upload_to='bills/%Y/%m/')
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bills',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.original_filename
