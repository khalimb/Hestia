"""Exchange rates to USD with a database cache.

Source: Frankfurter (https://frankfurter.dev), the ECB reference rates,
no API key. A date that falls on a weekend or holiday resolves to the last
published business day. Failures never break analytics: the caller gets the
rates it could find plus a list of currencies left unconverted.
"""
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from urllib.request import Request, urlopen

from django.conf import settings

from .models import FxRate

ONE = Decimal('1')
PRECISION = Decimal('0.00000001')


def _fetch(currencies, on_date):
    """USD -> each currency from the API, inverted to currency -> USD."""
    base = getattr(settings, 'FX_API_BASE', 'https://api.frankfurter.dev/v1').rstrip('/')
    url = f"{base}/{on_date.isoformat()}?from=USD&to={','.join(sorted(currencies))}"
    # The default urllib user agent is refused (403) by the API's CDN.
    request = Request(url, headers={'User-Agent': 'Hestia/1.0 (household expense tracker)',
                                    'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=6) as response:
            payload = json.load(response)
    except Exception:
        return {}
    rates = {}
    for currency, usd_to_cur in (payload.get('rates') or {}).items():
        try:
            value = Decimal(str(usd_to_cur))
            if value > 0:
                rates[currency] = (ONE / value).quantize(PRECISION, rounding=ROUND_HALF_UP)
        except Exception:
            continue
    return rates


def rates_to_usd(currencies, on_date):
    """-> (rates {cur: Decimal}, unconverted [cur], rate_date).

    Cache first; then one API call for what is missing; then the most recent
    cached rate as a stale fallback. USD is always 1."""
    on_date = min(on_date, date.today())
    rates, need = {}, []
    for currency in sorted(set(currencies)):
        if currency == 'USD':
            rates[currency] = ONE
            continue
        row = FxRate.objects.filter(date=on_date, currency=currency).first()
        if row is not None:
            rates[currency] = row.rate_to_usd
        else:
            need.append(currency)

    unconverted = []
    if need:
        fetched = _fetch(need, on_date)
        for currency in need:
            if currency in fetched:
                rates[currency] = fetched[currency]
                FxRate.objects.update_or_create(
                    date=on_date, currency=currency,
                    defaults={'rate_to_usd': fetched[currency]},
                )
                continue
            stale = (FxRate.objects.filter(currency=currency, date__lte=on_date)
                     .order_by('-date').first())
            if stale is not None:
                rates[currency] = stale.rate_to_usd
            else:
                unconverted.append(currency)
    return rates, unconverted, on_date
