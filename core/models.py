from django.db import models


class FxRate(models.Model):
    """Daily exchange rate to USD, cached from the ECB feed (via Frankfurter)
    so analytics can normalise across currencies without a network call on
    every request. One row per (date, currency)."""
    date = models.DateField()
    currency = models.CharField(max_length=3)
    rate_to_usd = models.DecimalField(max_digits=18, decimal_places=8)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['date', 'currency']
        ordering = ['-date', 'currency']

    def __str__(self):
        return f"{self.currency}→USD {self.rate_to_usd} on {self.date}"
