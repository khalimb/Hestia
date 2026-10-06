import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from agents.models import McpToken
from core.models import FxRate
from expenses.models import ExpenseType, Subject, Expense, Occurrence
from payments.models import Payment
from transactions.models import Transaction
from .analytics import spend_summary, breakdown_items

User = get_user_model()


class SpendSummaryTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='bk@example.com', username='bk', first_name='B', password='supersecret123')
        self.rent = ExpenseType.objects.create(name='Rent')
        self.takeaway = ExpenseType.objects.create(name='Takeaway')
        self.flat = Subject.objects.create(name='Flat')
        expense = Expense.objects.create(
            name='Flat rent', amount='1000.00', currency='GBP', recurrence_type='monthly',
            start_date=date(2026, 7, 1), expense_type=self.rent, subject=self.flat, created_by=self.user)
        for month in (7, 8, 9, 10):
            Occurrence.objects.create(expense=expense, due_date=date(2026, month, 1),
                                      expected_amount='1000.00', currency='GBP')
        # September paid in full, October partly.
        Payment.objects.create(occurrence=expense.occurrences.get(due_date=date(2026, 9, 1)),
                               amount_paid='1000.00', currency='GBP', paid_date=date(2026, 9, 2), logged_by=self.user)
        Payment.objects.create(occurrence=expense.occurrences.get(due_date=date(2026, 10, 1)),
                               amount_paid='400.00', currency='GBP', paid_date=date(2026, 10, 2), logged_by=self.user)
        euro = Expense.objects.create(
            name='Spanish water', amount='30.00', currency='EUR', recurrence_type='monthly',
            start_date=date(2026, 9, 5), created_by=self.user)
        Occurrence.objects.create(expense=euro, due_date=date(2026, 9, 5), expected_amount='30.00', currency='EUR')
        Transaction.objects.create(date=date(2026, 9, 3), amount='23.40', currency='GBP', merchant='Deliveroo',
                                   expense_type=self.takeaway, created_by=self.user)
        Transaction.objects.create(date=date(2026, 9, 20), amount='10.00', currency='GBP', merchant='Pizza',
                                   expense_type=self.takeaway, subject=self.flat, created_by=self.user)
        Transaction.objects.create(date=date(2026, 8, 15), amount='5.00', currency='GBP', merchant='Coffee',
                                   created_by=self.user)
        Transaction.objects.create(date=date(2026, 11, 1), amount='99.00', currency='GBP', merchant='Outside',
                                   created_by=self.user)

    def test_quarter_totals_per_currency(self):
        data = spend_summary(date(2026, 7, 1), date(2026, 9, 30))
        self.assertEqual(data['period']['months'], ['2026-07', '2026-08', '2026-09'])
        by_cur = {c['currency']: c for c in data['currencies']}
        gbp = by_cur['GBP']
        self.assertEqual(str(gbp['recurring_expected']), '3000.00')
        self.assertEqual(gbp['recurring_count'], 3)
        self.assertEqual(str(gbp['recurring_paid']), '1000.00')      # only September paid
        self.assertEqual(str(gbp['one_off']), '38.40')               # 23.40 + 10 + 5; November excluded
        self.assertEqual(gbp['one_off_count'], 3)
        self.assertEqual(str(gbp['total']), '3038.40')
        self.assertEqual(str(by_cur['EUR']['total']), '30.00')      # never mixed into GBP

    def test_breakdowns_and_zero_filled_months(self):
        gbp = {c['currency']: c for c in spend_summary(date(2026, 7, 1), date(2026, 9, 30))['currencies']}['GBP']
        cats = {c['name']: c for c in gbp['by_category']}
        self.assertEqual(str(cats['Rent']['recurring']), '3000.00')
        self.assertEqual(str(cats['Takeaway']['one_off']), '33.40')
        self.assertEqual(str(cats['Uncategorised']['one_off']), '5.00')
        self.assertEqual([c['name'] for c in gbp['by_category']], ['Rent', 'Takeaway', 'Uncategorised'])
        self.assertAlmostEqual(cats['Rent']['share'], 98.7, places=1)
        subjects = {s['name']: s for s in gbp['by_subject']}
        self.assertEqual(str(subjects['Flat']['total']), '3010.00')
        self.assertEqual(str(subjects['No subject']['total']), '28.40')
        months = {m['month']: m for m in gbp['by_month']}
        self.assertEqual([m['month'] for m in gbp['by_month']], ['2026-07', '2026-08', '2026-09'])
        self.assertEqual(str(months['2026-07']['one_off']), '0.00')
        self.assertEqual(str(months['2026-09']['total']), '1033.40')

    def test_empty_window_and_reversed_dates(self):
        data = spend_summary(date(2030, 2, 1), date(2030, 1, 1))
        self.assertEqual(data['period']['date_from'], '2030-01-01')
        self.assertEqual(data['currencies'], [])
        self.assertEqual(data['period']['months'], ['2030-01', '2030-02'])

    def test_endpoint_defaults_validates_and_requires_auth(self):
        self.assertEqual(self.client.get(reverse('dashboard-analytics')).status_code, 401)
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse('dashboard-analytics'), {'date_from': '2026-09-01', 'date_to': '2026-09-30'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        gbp = next(c for c in resp.json()['currencies'] if c['currency'] == 'GBP')
        self.assertEqual(float(gbp['total']), 1033.40)              # the API renders decimals as numbers
        resp = self.client.get(reverse('dashboard-analytics'), {'date_from': 'nope'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        resp = self.client.get(reverse('dashboard-analytics'), {'date_from': '2020-01-01', 'date_to': '2026-01-01'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        resp = self.client.get(reverse('dashboard-analytics'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['period']['months']), 1)    # defaults to this month

    def test_mcp_spend_summary_tool(self):
        token = McpToken.objects.create(user=self.user, name='t')
        message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': 'spend_summary',
                              'arguments': {'date_from': '2026-07-01', 'date_to': '2026-09-30'}}}
        result = self.client.post(f'/mcp/{token.token}/', json.dumps(message),
                                  content_type='application/json').json()['result']
        self.assertFalse(result['isError'], result)
        data = json.loads(result['content'][0]['text'])
        gbp = next(c for c in data['currencies'] if c['currency'] == 'GBP')
        self.assertEqual(gbp['total'], '3038.40')


class NormalisationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='bk@example.com', username='bk', first_name='B', password='supersecret123')
        rent = ExpenseType.objects.create(name='Rent')
        gbp = Expense.objects.create(name='Rent', amount='1000.00', currency='GBP', recurrence_type='monthly',
                                     start_date=date(2026, 9, 1), expense_type=rent, created_by=self.user)
        Occurrence.objects.create(expense=gbp, due_date=date(2026, 9, 1), expected_amount='1000.00', currency='GBP')
        Transaction.objects.create(date=date(2026, 9, 3), amount='10.00', currency='EUR', merchant='Tapas',
                                   created_by=self.user)
        Transaction.objects.create(date=date(2026, 9, 4), amount='7.00', currency='USD', merchant='App',
                                   created_by=self.user)
        # Cached rates for the window end, so no network is touched.
        FxRate.objects.create(date=date(2026, 9, 30), currency='GBP', rate_to_usd='1.25000000')
        FxRate.objects.create(date=date(2026, 9, 30), currency='EUR', rate_to_usd='1.10000000')

    def test_normalised_bucket_merges_at_cached_rates_and_keeps_per_currency(self):
        data = spend_summary(date(2026, 9, 1), date(2026, 9, 30), normalise_to='USD')
        self.assertEqual([c['currency'] for c in data['currencies']], ['EUR', 'GBP', 'USD'])  # untouched
        n = data['normalised']
        self.assertTrue(n['normalised'])
        self.assertEqual(n['rates'], {'EUR': '1.10000000', 'GBP': '1.25000000', 'USD': '1'})
        self.assertEqual(n['rate_sources'], {'EUR': 'ecb', 'GBP': 'ecb', 'USD': 'USD'})
        self.assertEqual(n['unconverted'], [])
        self.assertEqual(str(n['recurring_expected']), '1250.00')
        self.assertEqual(str(n['one_off']), '18.00')                 # 10*1.10 + 7
        self.assertEqual(str(n['total']), '1268.00')
        self.assertEqual(n['one_off_count'], 2)
        cats = {c['name']: str(c['total']) for c in n['by_category']}
        self.assertEqual(cats, {'Rent': '1250.00', 'Uncategorised': '18.00'})
        self.assertEqual(str(n['by_month'][0]['total']), '1268.00')

    @override_settings(FX_API_BASE='http://127.0.0.1:9', FX_FALLBACK_API_BASE='http://127.0.0.1:9')
    def test_missing_rate_is_reported_not_guessed(self):
        FxRate.objects.filter(currency='EUR').delete()
        data = spend_summary(date(2026, 9, 1), date(2026, 9, 30), normalise_to='USD')
        n = data['normalised']
        self.assertEqual(n['unconverted'], ['EUR'])
        self.assertEqual(str(n['one_off']), '7.00')                  # EUR left out, not silently 1:1
        self.assertEqual(str(n['total']), '1257.00')

    @override_settings(FX_API_BASE='http://127.0.0.1:9', FX_FALLBACK_API_BASE='http://127.0.0.1:9')
    def test_stale_cached_rate_used_as_fallback(self):
        FxRate.objects.filter(currency='EUR').update(date=date(2026, 9, 25))
        n = spend_summary(date(2026, 9, 1), date(2026, 9, 30), normalise_to='USD')['normalised']
        self.assertEqual(n['unconverted'], [])
        self.assertEqual(str(n['one_off']), '18.00')

    def test_endpoint_and_tool_accept_normalise(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse('dashboard-analytics'),
                               {'date_from': '2026-09-01', 'date_to': '2026-09-30', 'normalise': 'usd'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(float(resp.json()['normalised']['total']), 1268.00)
        resp = self.client.get(reverse('dashboard-analytics'), {'normalise': 'EUR'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        token = McpToken.objects.create(user=self.user, name='t')
        message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': 'spend_summary', 'arguments': {
                       'date_from': '2026-09-01', 'date_to': '2026-09-30', 'normalise_to': 'USD'}}}
        result = self.client.post(f'/mcp/{token.token}/', json.dumps(message),
                                  content_type='application/json').json()['result']
        self.assertFalse(result['isError'], result)
        self.assertEqual(json.loads(result['content'][0]['text'])['normalised']['total'], '1268.00')


class BreakdownItemsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='bk@example.com', username='bk', first_name='B', password='supersecret123')
        self.takeaway = ExpenseType.objects.create(name='Takeaway')
        self.rent = ExpenseType.objects.create(name='Rent')
        self.flat = Subject.objects.create(name='Flat')
        expense = Expense.objects.create(name='Flat rent', amount='1000.00', currency='GBP', recurrence_type='monthly',
                                         start_date=date(2026, 9, 1), expense_type=self.rent, subject=self.flat,
                                         created_by=self.user)
        self.occ = Occurrence.objects.create(expense=expense, due_date=date(2026, 9, 1),
                                             expected_amount='1000.00', currency='GBP')
        Payment.objects.create(occurrence=self.occ, amount_paid='400.00', currency='GBP',
                               paid_date=date(2026, 9, 2), logged_by=self.user)
        Occurrence.objects.create(expense=expense, due_date=date(2026, 10, 1), expected_amount='1000.00', currency='GBP')
        Transaction.objects.create(date=date(2026, 9, 3), amount='23.40', currency='GBP', merchant='Deliveroo',
                                   expense_type=self.takeaway, subject=self.flat, created_by=self.user)
        Transaction.objects.create(date=date(2026, 9, 9), amount='12.00', currency='EUR', merchant='Tapas',
                                   expense_type=self.takeaway, created_by=self.user)
        Transaction.objects.create(date=date(2026, 9, 5), amount='5.00', currency='GBP', merchant='Coffee',
                                   created_by=self.user)
        FxRate.objects.create(date=date(2026, 9, 30), currency='GBP', rate_to_usd='1.25')
        FxRate.objects.create(date=date(2026, 9, 30), currency='EUR', rate_to_usd='1.10')

    def test_breakdown_rows_carry_ids(self):
        gbp = {c['currency']: c for c in spend_summary(date(2026, 9, 1), date(2026, 9, 30))['currencies']}['GBP']
        cats = {c['name']: c for c in gbp['by_category']}
        self.assertEqual(cats['Rent']['id'], str(self.rent.id))
        self.assertIsNone(cats['Uncategorised']['id'])
        subjects = {s['name']: s for s in gbp['by_subject']}
        self.assertEqual(subjects['Flat']['id'], str(self.flat.id))

    def test_category_items_mix_both_kinds_window_and_currency(self):
        data = breakdown_items(date(2026, 9, 1), date(2026, 9, 30), 'category', self.takeaway.id)
        self.assertEqual([(i['kind'], i['name']) for i in data['items']],
                         [('one_off', 'Tapas'), ('one_off', 'Deliveroo')])           # newest first
        self.assertEqual({k: str(v) for k, v in data['totals'].items()}, {'EUR': '12.00', 'GBP': '23.40'})
        data = breakdown_items(date(2026, 9, 1), date(2026, 9, 30), 'category', self.takeaway.id, currency='GBP')
        self.assertEqual([i['name'] for i in data['items']], ['Deliveroo'])

        data = breakdown_items(date(2026, 9, 1), date(2026, 9, 30), 'category', self.rent.id)
        self.assertEqual(data['count'], 1)                                           # October occurrence excluded
        occ = data['items'][0]
        self.assertEqual((occ['kind'], occ['status'], str(occ['paid']), occ['expense_id']),
                         ('recurring', 'pending', '400.00', str(self.occ.expense_id)))

        data = breakdown_items(date(2026, 9, 1), date(2026, 9, 30), 'category', None)
        self.assertEqual([i['name'] for i in data['items']], ['Coffee'])

    def test_subject_items_and_usd_column(self):
        data = breakdown_items(date(2026, 9, 1), date(2026, 9, 30), 'subject', self.flat.id, normalise_to='USD')
        self.assertEqual([(i['kind'], i['name']) for i in data['items']],
                         [('one_off', 'Deliveroo'), ('recurring', 'Flat rent')])
        self.assertEqual(str(data['items'][1]['amount_usd']), '1250.00')
        self.assertEqual(str(data['total_usd']), '1279.25')
        self.assertEqual(data['unconverted'], [])
        with self.assertRaises(ValueError):
            breakdown_items(date(2026, 9, 1), date(2026, 9, 30), 'bogus', None)

    def test_endpoint(self):
        self.client.force_authenticate(self.user)
        base = {'date_from': '2026-09-01', 'date_to': '2026-09-30'}
        resp = self.client.get(reverse('dashboard-analytics-items'), {**base, 'group': 'subject', 'id': str(self.flat.id)})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['count'], 2)
        resp = self.client.get(reverse('dashboard-analytics-items'), {**base, 'group': 'category', 'id': 'none'})
        self.assertEqual([i['name'] for i in resp.json()['items']], ['Coffee'])
        for params in ({**base, 'group': 'category'},
                       {**base, 'group': 'bogus', 'id': 'none'}):
            self.assertEqual(self.client.get(reverse('dashboard-analytics-items'), params).status_code, 400, params)
        resp = self.client.get(reverse('dashboard-analytics-items'),
                               {**base, 'group': 'category', 'id': '00000000-0000-0000-0000-000000000000'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.get(reverse('dashboard-analytics-items'), {**base, 'group': 'category', 'id': 'not-a-uuid'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
