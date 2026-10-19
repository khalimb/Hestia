"""The dashboard app is mostly aggregation views; its one table is the set
of manual marks on the coverage grid."""
import uuid

from django.conf import settings
from django.db import models


class CoverageMark(models.Model):
    """A note on an empty coverage cell: the expense for this (subject,
    category) is coming soon, or is deliberately not needed. Superseded by a
    real active expense whenever one exists."""
    IN_PROGRESS = 'in_progress'
    NOT_NEEDED = 'not_needed'
    STATUS_CHOICES = [(IN_PROGRESS, 'In progress'), (NOT_NEEDED, 'Not needed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey('expenses.Subject', on_delete=models.CASCADE, related_name='coverage_marks')
    expense_type = models.ForeignKey('expenses.ExpenseType', on_delete=models.CASCADE,
                                     related_name='coverage_marks')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coverage_marks',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['subject', 'expense_type']

    def __str__(self):
        return f"{self.subject} × {self.expense_type}: {self.status}"
