"""One-off spending: a single dated amount in a category, e.g. Deliveroo on
Tuesday. No schedule, no occurrences — the counterpart to the recurring
Expense, sharing its dictionaries so budgets per ExpenseType cover both."""
import uuid

from django.conf import settings
from django.db import models


class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='GBP')
    # Who/what it was: "Deliveroo", "Tesco", "Vet".
    merchant = models.CharField(max_length=255)
    notes = models.TextField(blank=True, default='')
    # Category is the same dictionary recurring expenses use.
    expense_type = models.ForeignKey(
        'expenses.ExpenseType', on_delete=models.PROTECT, related_name='transactions',
        null=True, blank=True,
    )
    subject = models.ForeignKey(
        'expenses.Subject', on_delete=models.PROTECT, related_name='transactions',
        null=True, blank=True,
    )
    payment_method = models.ForeignKey(
        'expenses.PaymentMethod', on_delete=models.PROTECT, related_name='transactions',
        null=True, blank=True,
    )
    account = models.ForeignKey(
        'expenses.PaymentAccount', on_delete=models.PROTECT, related_name='transactions',
        null=True, blank=True,
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='paid_transactions',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.merchant} {self.currency} {self.amount} on {self.date}"
