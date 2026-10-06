"""Spend analytics for an arbitrary date window: recurring occurrences
(expected and paid) plus one-off transactions, per currency, broken down by
category, subject and month. One function, used by the API view and the
MCP `spend_summary` tool so both answer identically.

Recurring spend is cash-basis: an occurrence counts in the month it is due,
whatever its status; `recurring_paid` shows how much of that was actually
paid. Currencies are never summed together.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth

from core.fx import rates_to_usd
from expenses.models import Occurrence
from payments.models import Payment
from transactions.models import Transaction

ZERO = Decimal('0.00')
CENT = Decimal('0.01')


def _q(value):
    return (value if value is not None else ZERO).quantize(CENT)
UNCATEGORISED = 'Uncategorised'
NO_SUBJECT = 'No subject'


def _months_between(date_from, date_to):
    months = []
    cursor = date_from.replace(day=1)
    while cursor <= date_to:
        months.append(cursor.strftime('%Y-%m'))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return months


def _bucket(store, currency, months):
    if currency not in store:
        store[currency] = {
            'currency': currency,
            'recurring_expected': ZERO, 'recurring_paid': ZERO, 'recurring_count': 0,
            'one_off': ZERO, 'one_off_count': 0,
            'by_category': {}, 'by_subject': {},
            'by_month': {m: {'month': m, 'recurring': ZERO, 'one_off': ZERO} for m in months},
        }
    return store[currency]


def _add(group, key, field, amount):
    row = group.setdefault(key, {'name': key, 'recurring': ZERO, 'one_off': ZERO})
    row[field] += _q(amount)


def spend_summary(date_from, date_to, normalise_to=None):
    """`normalise_to='USD'` adds a `normalised` bucket: every currency
    converted at its rate on `date_to` (capped at today) and merged."""
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    months = _months_between(date_from, date_to)
    occurrences = Occurrence.objects.filter(due_date__gte=date_from, due_date__lte=date_to)
    transactions = Transaction.objects.filter(date__gte=date_from, date__lte=date_to)
    store = {}

    # --- recurring (occurrences due in the window) ---
    for row in occurrences.values('currency').annotate(total=Sum('expected_amount'), count=Count('id')):
        b = _bucket(store, row['currency'], months)
        b['recurring_expected'] += _q(row['total'])
        b['recurring_count'] += row['count']
    for row in (Payment.objects.filter(occurrence__in=occurrences)
                .values('occurrence__currency').annotate(total=Sum('amount_paid'))):
        _bucket(store, row['occurrence__currency'], months)['recurring_paid'] += _q(row['total'])
    for row in occurrences.values('currency', 'expense__expense_type__name').annotate(total=Sum('expected_amount')):
        _add(_bucket(store, row['currency'], months)['by_category'],
             row['expense__expense_type__name'] or UNCATEGORISED, 'recurring', row['total'])
    for row in occurrences.values('currency', 'expense__subject__name').annotate(total=Sum('expected_amount')):
        _add(_bucket(store, row['currency'], months)['by_subject'],
             row['expense__subject__name'] or NO_SUBJECT, 'recurring', row['total'])
    for row in (occurrences.annotate(m=TruncMonth('due_date'))
                .values('currency', 'm').annotate(total=Sum('expected_amount'))):
        key = row['m'].strftime('%Y-%m')
        _bucket(store, row['currency'], months)['by_month'][key]['recurring'] += _q(row['total'])

    # --- one-off (transactions dated in the window) ---
    for row in transactions.values('currency').annotate(total=Sum('amount'), count=Count('id')):
        b = _bucket(store, row['currency'], months)
        b['one_off'] += _q(row['total'])
        b['one_off_count'] += row['count']
    for row in transactions.values('currency', 'expense_type__name').annotate(total=Sum('amount')):
        _add(_bucket(store, row['currency'], months)['by_category'],
             row['expense_type__name'] or UNCATEGORISED, 'one_off', row['total'])
    for row in transactions.values('currency', 'subject__name').annotate(total=Sum('amount')):
        _add(_bucket(store, row['currency'], months)['by_subject'],
             row['subject__name'] or NO_SUBJECT, 'one_off', row['total'])
    for row in (transactions.annotate(m=TruncMonth('date'))
                .values('currency', 'm').annotate(total=Sum('amount'))):
        key = row['m'].strftime('%Y-%m')
        _bucket(store, row['currency'], months)['by_month'][key]['one_off'] += _q(row['total'])

    # --- optional normalisation into one currency (USD) ---
    normalised = None
    if normalise_to == 'USD' and store:
        rates, unconverted, rate_date, sources = rates_to_usd(list(store), date_to)
        merged = _bucket({}, 'USD', months)
        merged.update({'normalised': True, 'rate_date': rate_date.isoformat(),
                       'rates': {c: str(r) for c, r in rates.items()},
                       'rate_sources': sources, 'unconverted': unconverted})
        for b in store.values():
            rate = rates.get(b['currency'])
            if rate is None:
                continue
            for field in ('recurring_expected', 'recurring_paid', 'one_off'):
                merged[field] += _q(b[field] * rate)
            merged['recurring_count'] += b['recurring_count']
            merged['one_off_count'] += b['one_off_count']
            for group in ('by_category', 'by_subject'):
                for key, row in b[group].items():
                    _add(merged[group], key, 'recurring', row['recurring'] * rate)
                    _add(merged[group], key, 'one_off', row['one_off'] * rate)
            for key, row in b['by_month'].items():
                merged['by_month'][key]['recurring'] += _q(row['recurring'] * rate)
                merged['by_month'][key]['one_off'] += _q(row['one_off'] * rate)
        normalised = merged

    # --- finalise: totals, shares, ordering ---
    def finalise(b):
        total = b['recurring_expected'] + b['one_off']
        b['total'] = total

        def finish(group):
            rows = []
            for row in group.values():
                row['total'] = row['recurring'] + row['one_off']
                row['share'] = float(row['total'] / total * 100) if total else 0.0
                rows.append(row)
            return sorted(rows, key=lambda r: -r['total'])

        b['by_category'] = finish(b['by_category'])
        b['by_subject'] = finish(b['by_subject'])
        b['by_month'] = [{**m, 'total': m['recurring'] + m['one_off']}
                         for m in b['by_month'].values()]
        return b

    currencies = [finalise(b) for b in sorted(store.values(), key=lambda x: x['currency'])]
    result = {
        'period': {'date_from': date_from.isoformat(), 'date_to': date_to.isoformat(),
                   'months': months},
        'currencies': currencies,
    }
    if normalised is not None:
        result['normalised'] = finalise(normalised)
    return result


def parse_window(date_from, date_to):
    """Parse YYYY-MM-DD strings; default to the current month."""
    today = date.today()
    if not date_from and not date_to:
        first = today.replace(day=1)
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        return first, last
    try:
        start = date.fromisoformat(date_from) if date_from else date.fromisoformat(date_to)
        end = date.fromisoformat(date_to) if date_to else start
    except ValueError:
        raise ValueError('dates must be YYYY-MM-DD')
    return start, end
