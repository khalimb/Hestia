import uuid
from django.conf import settings
from django.db import models


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence = models.ForeignKey(
        'expenses.Occurrence', on_delete=models.CASCADE, related_name='payments',
    )
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    paid_date = models.DateField()
    payment_method = models.CharField(max_length=100, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_date']

    def __str__(self):
        return f"Payment of {self.currency} {self.amount_paid} on {self.paid_date}"
