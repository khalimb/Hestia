"""Exchange rates to USD with a database cache and a source chain.

Order of precedence for each currency, on a given date (capped at today):

1. Manual rate set in Settings (ManualFxRate) — explicit household intent.
2. Cached rate for that exact date (FxRate).
3. ECB reference rate for that date via Frankfurter (30 currencies,
   historical; weekends resolve to the last business day).
4. Today's rate from the Exchange Rate API (open.er-api.com, ~160
   currencies, latest only) — used for any date, and labelled as such.
5. The most recent cached rate of any source (stale fallback).
6. Otherwise the currency is reported as unconverted — never assumed 1:1.

Failures never break analytics: the caller gets what could be found plus
the list of currencies left unconverted and the source used for each.
"""
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from urllib.request import Request, urlopen

from django.conf import settings

from .models import FxRate, ManualFxRate

ONE = Decimal('1')
PRECISION = Decimal('0.00000001')
# Both CDNs refuse urllib's default User-Agent with a 403.
HEADERS = {'User-Agent': 'Hestia/1.0 (household expense tracker)', 'Accept': 'application/json'}


def _get_json(url):
    with urlopen(Request(url, headers=HEADERS), timeout=6) as response:
        return json.load(response)


def _invert(usd_to_cur):
    try:
        value = Decimal(str(usd_to_cur))
    except Exception:
        return None
    if value <= 0:
        return None
    return (ONE / value).quantize(PRECISION, rounding=ROUND_HALF_UP)


def _fetch_ecb(currencies, on_date):
    """currency -> USD for a date, from the ECB feed. {} on any failure."""
    base = getattr(settings, 'FX_API_BASE', 'https://api.frankfurter.dev/v1').rstrip('/')
    url = f"{base}/{on_date.isoformat()}?from=USD&to={','.join(sorted(currencies))}"
    try:
        payload = _get_json(url)
    except Exception:
        return {}
    rates = {}
    for currency, value in (payload.get('rates') or {}).items():
        rate = _invert(value)
        if rate is not None:
            rates[currency] = rate
    return rates


def _fetch_erapi(currencies):
    """currency -> USD, today's rates, from the Exchange Rate API. {} on failure."""
    base = getattr(settings, 'FX_FALLBACK_API_BASE', 'https://open.er-api.com/v6').rstrip('/')
    try:
        payload = _get_json(f"{base}/latest/USD")
    except Exception:
        return {}
    if payload.get('result') != 'success':
        return {}
    all_rates = payload.get('rates') or {}
    rates = {}
    for currency in currencies:
        rate = _invert(all_rates.get(currency))
        if rate is not None:
            rates[currency] = rate
    return rates


def rates_to_usd(currencies, on_date):
    """-> (rates {cur: Decimal}, unconverted [cur], rate_date, sources {cur: label})."""
    today = date.today()
    on_date = min(on_date, today)
    wanted = sorted(set(currencies))
    rates, sources = {}, {}

    manual = {m.currency: m for m in ManualFxRate.objects.filter(currency__in=wanted)}
    need = []
    for currency in wanted:
        if currency == 'USD':
            rates[currency], sources[currency] = ONE, 'USD'
        elif currency in manual:
            rates[currency], sources[currency] = manual[currency].rate_to_usd, 'manual'
        else:
            need.append(currency)

    cached = {r.currency: r for r in FxRate.objects.filter(date=on_date, currency__in=need)}
    for currency in list(need):
        row = cached.get(currency)
        if row is not None:
            rates[currency] = row.rate_to_usd
            sources[currency] = 'ecb' if row.source == FxRate.SOURCE_ECB else 'latest'
            need.remove(currency)

    if need:
        for currency, rate in _fetch_ecb(need, on_date).items():
            rates[currency], sources[currency] = rate, 'ecb'
            FxRate.objects.update_or_create(
                date=on_date, currency=currency,
                defaults={'rate_to_usd': rate, 'source': FxRate.SOURCE_ECB})
        need = [c for c in need if c not in rates]

    if need:
        # Today's row from the broad feed may already be cached.
        for row in FxRate.objects.filter(date=today, currency__in=need, source=FxRate.SOURCE_ERAPI):
            rates[row.currency], sources[row.currency] = row.rate_to_usd, 'latest'
        need = [c for c in need if c not in rates]
    if need:
        for currency, rate in _fetch_erapi(need).items():
            rates[currency], sources[currency] = rate, 'latest'
            FxRate.objects.update_or_create(
                date=today, currency=currency,
                defaults={'rate_to_usd': rate, 'source': FxRate.SOURCE_ERAPI})
        need = [c for c in need if c not in rates]

    unconverted = []
    for currency in need:
        stale = FxRate.objects.filter(currency=currency).order_by('-date').first()
        if stale is not None:
            rates[currency], sources[currency] = stale.rate_to_usd, f'cached {stale.date.isoformat()}'
        else:
            unconverted.append(currency)
    return rates, unconverted, on_date, sources
