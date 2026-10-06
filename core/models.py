from django.conf import settings
from django.db import models


class FxRate(models.Model):
    """Daily exchange rate to USD, cached so analytics can normalise across
    currencies without a network call on every request. One row per
    (date, currency). `source` records where it came from: the ECB feed
    (historical, 30 currencies) or the broader daily feed (latest only)."""
    SOURCE_ECB = 'ecb'
    SOURCE_ERAPI = 'erapi'
    SOURCE_CHOICES = [(SOURCE_ECB, 'ECB via Frankfurter'), (SOURCE_ERAPI, 'Exchange Rate API')]

    date = models.DateField()
    currency = models.CharField(max_length=3)
    rate_to_usd = models.DecimalField(max_digits=18, decimal_places=8)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_ECB)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['date', 'currency']
        ordering = ['-date', 'currency']

    def __str__(self):
        return f"{self.currency}→USD {self.rate_to_usd} on {self.date} ({self.source})"


class ManualFxRate(models.Model):
    """A rate the household sets by hand. Wins over every feed for that
    currency, for any date, until removed. Entered as units per USD
    (e.g. 1 USD = 11800 UZS) and stored both ways."""
    currency = models.CharField(max_length=3, unique=True)
    units_per_usd = models.DecimalField(max_digits=18, decimal_places=6)
    rate_to_usd = models.DecimalField(max_digits=18, decimal_places=8)
    note = models.CharField(max_length=255, blank=True, default='')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='manual_fx_rates',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['currency']

    def __str__(self):
        return f"1 USD = {self.units_per_usd} {self.currency} (manual)"
